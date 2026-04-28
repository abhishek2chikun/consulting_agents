"""Read-side artifact path aliases for known V1 path drift."""

from __future__ import annotations

from pathlib import PurePosixPath

_DIR_ALIASES = {
    "stage_3_risk": "stage3_risk",
    "stage3_risk": "stage_3_risk",
}
_BASENAME_ALIASES = {
    "risk.md": "findings.md",
    "findings.md": "risk.md",
}


def normalize_artifact_path(path: str) -> set[str]:
    """Return the original path plus known aliases for read-side artifact lookup."""
    original = PurePosixPath(path)
    paths = {path}

    candidates = [original]
    parts = original.parts
    if parts:
        swapped_parts = tuple(_DIR_ALIASES.get(part, part) for part in parts)
        if swapped_parts != parts:
            candidates.append(PurePosixPath(*swapped_parts))

    for candidate in candidates:
        paths.add(candidate.as_posix())
        basename_alias = _BASENAME_ALIASES.get(candidate.name)
        if basename_alias is not None:
            paths.add(candidate.with_name(basename_alias).as_posix())

    return paths


__all__ = ["normalize_artifact_path"]
