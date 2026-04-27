"""DuckDuckGo search-provider adapter — no API key required.

Uses the DuckDuckGo HTML endpoint (html.duckduckgo.com/html/?q=...) which
is free and rate-limited only by the network. Results are parsed from the
HTML response using simple string operations so there is no dependency on
an HTML parser library beyond the stdlib.

This is intended for development / testing where no paid search key is
available. For production use the Tavily, Exa, or Perplexity adapters.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from urllib.parse import unquote

import httpx

from app.agents.tools.providers.base import SearchResult

# DuckDuckGo HTML lite endpoint — no JS required, stable for scraping.
_DDG_URL = "https://html.duckduckgo.com/html/"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


class DuckDuckGoProvider:
    """Free web search via DuckDuckGo HTML endpoint. Requires no API key."""

    def __init__(self) -> None:
        pass

    async def search(self, query: str, k: int) -> list[SearchResult]:
        if not query.strip() or k <= 0:
            return []

        async with httpx.AsyncClient(
            timeout=20.0,
            follow_redirects=True,
            headers=_HEADERS,
        ) as client:
            try:
                resp = await client.post(
                    _DDG_URL,
                    data={"q": query, "b": "", "kl": "us-en"},
                )
                resp.raise_for_status()
                html = resp.text
            except httpx.HTTPError:
                # Fallback: GET request.
                try:
                    resp = await client.get(
                        _DDG_URL,
                        params={"q": query, "kl": "us-en"},
                    )
                    resp.raise_for_status()
                    html = resp.text
                except httpx.HTTPError:
                    return []

        return _parse_results(html, k)


def _parse_results(html: str, k: int) -> list[SearchResult]:
    """Extract up to k results from DuckDuckGo HTML page."""
    results: list[SearchResult] = []

    # Each result block is wrapped in <div class="result ...">
    # Extract title, URL, and snippet via regex patterns.
    result_blocks = re.findall(
        r'<div class="result[^"]*".*?</div>\s*</div>\s*</div>',
        html,
        re.DOTALL,
    )

    for block in result_blocks:
        if len(results) >= k:
            break

        # Title and URL — inside <a class="result__a" href="...">
        title_match = re.search(
            r'<a class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
            block,
            re.DOTALL,
        )
        if not title_match:
            continue

        raw_url = title_match.group(1)
        raw_title = re.sub(r"<[^>]+>", "", title_match.group(2)).strip()

        # DuckDuckGo wraps URLs in a redirect; extract the real URL.
        url = _extract_real_url(raw_url)
        if not url:
            continue

        # Snippet — inside <a class="result__snippet">
        snippet_match = re.search(
            r'<a class="result__snippet"[^>]*>(.*?)</a>',
            block,
            re.DOTALL,
        )
        snippet = ""
        if snippet_match:
            snippet = re.sub(r"<[^>]+>", "", snippet_match.group(1)).strip()

        if not raw_title and not snippet:
            continue

        results.append(
            SearchResult(
                title=_html_unescape(raw_title) or url,
                url=url,
                snippet=_html_unescape(snippet),
                published_at=datetime.now(UTC),
                source="duckduckgo",
            )
        )

    return results


def _extract_real_url(raw: str) -> str:
    """Unwrap DDG redirect URLs to the real destination."""
    if raw.startswith("http") and "duckduckgo.com/y.js" not in raw:
        return raw
    # DDG redirect format: //duckduckgo.com/l/?uddg=<encoded_url>&...
    match = re.search(r"uddg=([^&]+)", raw)
    if match:
        return unquote(match.group(1))
    # Return as-is if we can't parse it.
    return raw if raw.startswith("http") else ""


_HTML_ENTITIES = {
    "&amp;": "&",
    "&lt;": "<",
    "&gt;": ">",
    "&quot;": '"',
    "&#x27;": "'",
    "&nbsp;": " ",
}


def _html_unescape(text: str) -> str:
    for entity, char in _HTML_ENTITIES.items():
        text = text.replace(entity, char)
    return text


__all__ = ["DuckDuckGoProvider"]
