"use client";

/**
 * ReportView — renders the final synthesis report (M7.3).
 *
 * V1 deliberately hand-rolls a tiny markdown subset (headings,
 * paragraphs, unordered lists, fenced code blocks) instead of pulling
 * in `react-markdown` + a remark plugin chain. The synthesis prompt
 * controls the report shape end-to-end, so we only need to render
 * what we ourselves produce.
 *
 * The interesting bit is the citation chip: `[^src_id]` substrings
 * inside inline text become small clickable buttons that surface the
 * source via `onCitationClick(srcId)` (handled by the parent page,
 * which owns the SourcesSidebar).
 *
 * Loading / empty / error states are handled inline so the parent
 * layout can drop this component into a pane without a wrapper card.
 */

import { useEffect, useState } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiRequestError, getRunArtifact } from "@/lib/api";
import type { RunEvent } from "@/lib/sse";

const REPORT_PATH = "final_report.md";

interface ReportViewProps {
  runId: string;
  /**
   * SSE events from the parent page. We watch for an
   * `artifact_update` whose payload.path === "final_report.md" and
   * (re)fetch the artifact when it lands.
   */
  events: RunEvent[];
  /** Called when a `[^src_id]` chip is clicked. */
  onCitationClick?: (srcId: string) => void;
}

export function ReportView({ runId, events, onCitationClick }: ReportViewProps) {
  const [content, setContent] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Latest report-update event id is what triggers a refetch. Compute
  // it once per render so the effect dependency list stays
  // statically analyzable.
  const reportEventId = latestReportEventId(events);

  // Trigger a fetch whenever a final_report.md artifact_update lands.
  // We also do an initial fetch on mount in case the report was
  // already produced before this component subscribed.
  useEffect(() => {
    let cancelled = false;

    const fetchReport = async () => {
      setLoading(true);
      try {
        const artifact = await getRunArtifact(runId, REPORT_PATH);
        if (!cancelled) {
          setContent(artifact.content);
          setError(null);
        }
      } catch (err) {
        if (cancelled) return;
        if (err instanceof ApiRequestError && err.status === 404) {
          // Report not produced yet — not an error, just empty state.
          setContent(null);
          setError(null);
        } else {
          setError(err instanceof Error ? err.message : "Failed to load report");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    void fetchReport();

    return () => {
      cancelled = true;
    };
  }, [runId, reportEventId]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Final report</CardTitle>
      </CardHeader>
      <CardContent>
        {loading && content === null ? (
          <p className="text-sm text-muted-foreground">Loading report…</p>
        ) : null}
        {error ? (
          <p className="text-sm text-rose-700">{error}</p>
        ) : null}
        {content === null && !loading && !error ? (
          <p className="text-sm text-muted-foreground">
            The report will appear here once synthesis completes.
          </p>
        ) : null}
        {content !== null ? (
          <article className="prose prose-sm max-w-none">
            <MarkdownBody source={content} onCitationClick={onCitationClick} />
          </article>
        ) : null}
      </CardContent>
    </Card>
  );
}

function latestReportEventId(events: RunEvent[]): number {
  for (let i = events.length - 1; i >= 0; i--) {
    const e = events[i];
    if (e && e.type === "artifact_update" && e.payload.path === REPORT_PATH) {
      return e.id;
    }
  }
  return 0;
}

// ---------------------------------------------------------------------------
// Tiny markdown renderer — block-level
// ---------------------------------------------------------------------------

type CitationHandler = (srcId: string) => void;

interface MarkdownBodyProps {
  source: string;
  onCitationClick: CitationHandler | undefined;
}

function MarkdownBody({ source, onCitationClick }: MarkdownBodyProps) {
  const blocks = parseBlocks(source);
  return (
    <>
      {blocks.map((block, i) => (
        <RenderBlock key={i} block={block} onCitationClick={onCitationClick} />
      ))}
    </>
  );
}

type Block =
  | { kind: "heading"; level: 1 | 2 | 3 | 4; text: string }
  | { kind: "paragraph"; text: string }
  | { kind: "list"; items: string[] }
  | { kind: "code"; text: string };

function parseBlocks(source: string): Block[] {
  const lines = source.split("\n");
  const blocks: Block[] = [];
  let i = 0;
  const peek = (idx: number): string => lines[idx] ?? "";
  while (i < lines.length) {
    const line = peek(i);
    if (/^```/.test(line)) {
      const buf: string[] = [];
      i++;
      while (i < lines.length && !/^```/.test(peek(i))) {
        buf.push(peek(i));
        i++;
      }
      i++; // consume closing fence
      blocks.push({ kind: "code", text: buf.join("\n") });
      continue;
    }
    const headingMatch = line.match(/^(#{1,4})\s+(.*)$/);
    if (headingMatch && headingMatch[1] && headingMatch[2] !== undefined) {
      const level = headingMatch[1].length as 1 | 2 | 3 | 4;
      blocks.push({ kind: "heading", level, text: headingMatch[2] });
      i++;
      continue;
    }
    if (/^\s*[-*]\s+/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^\s*[-*]\s+/.test(peek(i))) {
        items.push(peek(i).replace(/^\s*[-*]\s+/, ""));
        i++;
      }
      blocks.push({ kind: "list", items });
      continue;
    }
    if (line.trim() === "") {
      i++;
      continue;
    }
    // Accumulate consecutive non-empty lines into a paragraph.
    const buf: string[] = [];
    while (
      i < lines.length &&
      peek(i).trim() !== "" &&
      !/^(#{1,4})\s+/.test(peek(i)) &&
      !/^\s*[-*]\s+/.test(peek(i)) &&
      !/^```/.test(peek(i))
    ) {
      buf.push(peek(i));
      i++;
    }
    blocks.push({ kind: "paragraph", text: buf.join(" ") });
  }
  return blocks;
}

function RenderBlock({
  block,
  onCitationClick,
}: {
  block: Block;
  onCitationClick: CitationHandler | undefined;
}) {
  if (block.kind === "code") {
    return (
      <pre className="overflow-x-auto rounded bg-slate-100 p-3 text-xs">
        <code>{block.text}</code>
      </pre>
    );
  }
  if (block.kind === "heading") {
    const Tag = `h${block.level}` as "h1" | "h2" | "h3" | "h4";
    return (
      <Tag>
        <Inline text={block.text} onCitationClick={onCitationClick} />
      </Tag>
    );
  }
  if (block.kind === "list") {
    return (
      <ul>
        {block.items.map((item, i) => (
          <li key={i}>
            <Inline text={item} onCitationClick={onCitationClick} />
          </li>
        ))}
      </ul>
    );
  }
  return (
    <p>
      <Inline text={block.text} onCitationClick={onCitationClick} />
    </p>
  );
}

// ---------------------------------------------------------------------------
// Inline renderer — citation chips
// ---------------------------------------------------------------------------

const CITATION_RE = /\[\^([^\]]+)\]/g;

function Inline({
  text,
  onCitationClick,
}: {
  text: string;
  onCitationClick: CitationHandler | undefined;
}) {
  const parts: React.ReactNode[] = [];
  let lastIdx = 0;
  // Use a per-call regex instance to avoid mutating shared state
  // (the global flag means `lastIndex` would leak across calls).
  const re = new RegExp(CITATION_RE.source, CITATION_RE.flags);
  let match: RegExpExecArray | null;

  while ((match = re.exec(text)) !== null) {
    if (match.index > lastIdx) {
      parts.push(text.slice(lastIdx, match.index));
    }
    const srcId = match[1];
    if (srcId === undefined) continue;
    const chipProps: { srcId: string; onClick?: CitationHandler } = {
      srcId,
    };
    if (onCitationClick) chipProps.onClick = onCitationClick;
    parts.push(<CitationChip key={`${match.index}-${srcId}`} {...chipProps} />);
    lastIdx = match.index + match[0].length;
  }
  if (lastIdx < text.length) {
    parts.push(text.slice(lastIdx));
  }
  return <>{parts}</>;
}

function CitationChip({
  srcId,
  onClick,
}: {
  srcId: string;
  onClick?: CitationHandler;
}) {
  if (!onClick) {
    return (
      <span className="mx-0.5 inline-flex items-center rounded bg-sky-100 px-1.5 py-0.5 align-baseline font-mono text-[10px] text-sky-900">
        {srcId}
      </span>
    );
  }
  return (
    <button
      type="button"
      onClick={() => onClick(srcId)}
      className="mx-0.5 inline-flex items-center rounded bg-sky-100 px-1.5 py-0.5 align-baseline font-mono text-[10px] text-sky-900 hover:bg-sky-200"
    >
      {srcId}
    </button>
  );
}
