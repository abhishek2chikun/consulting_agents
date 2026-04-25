"use client";

/**
 * SourcesSidebar — list of citable sources for a run (M7.4).
 *
 * Renders one card per `Evidence` row from
 * `GET /runs/{id}/evidence`. The list is fetched on mount and
 * refetched whenever a new `artifact_update` event lands (synthesis
 * writes evidence rows just before producing `final_report.md`, so
 * piggybacking on the report-update signal keeps us in sync without
 * a dedicated `evidence_update` event in V1).
 *
 * The parent page passes `highlightedSrcId` (driven by clicks on
 * `[^src_id]` chips inside `<ReportView />`); the matching card gets
 * scrolled into view and visually emphasized.
 */

import { useEffect, useMemo, useRef, useState } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiRequestError, getRunEvidence } from "@/lib/api";
import type { RunEvent } from "@/lib/sse";
import type { EvidenceItem } from "@/lib/types";

interface SourcesSidebarProps {
  runId: string;
  events: RunEvent[];
  /** `src_id` to scroll into view + highlight. */
  highlightedSrcId?: string | null;
}

/**
 * Latest `artifact_update` event id — used to invalidate the cached
 * evidence list when the worker writes a new artifact (typically
 * `final_report.md`, written immediately after evidence rows are
 * inserted).
 */
function latestArtifactEventId(events: RunEvent[]): number | null {
  for (let i = events.length - 1; i >= 0; i -= 1) {
    const ev = events[i];
    if (ev && ev.type === "artifact_update") return ev.id;
  }
  return null;
}

export function SourcesSidebar({
  runId,
  events,
  highlightedSrcId,
}: SourcesSidebarProps) {
  const [items, setItems] = useState<EvidenceItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const artifactEventId = latestArtifactEventId(events);

  useEffect(() => {
    let cancelled = false;
    const fetchEvidence = async () => {
      setLoading(true);
      try {
        const res = await getRunEvidence(runId);
        if (!cancelled) {
          setItems(res.evidence);
          setError(null);
        }
      } catch (err) {
        if (cancelled) return;
        if (err instanceof ApiRequestError && err.status === 404) {
          setItems([]);
          setError(null);
        } else {
          setError(err instanceof Error ? err.message : "Failed to load sources");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    void fetchEvidence();
    return () => {
      cancelled = true;
    };
  }, [runId, artifactEventId]);

  return (
    <Card className="flex h-full flex-col">
      <CardHeader>
        <CardTitle className="text-base">Sources</CardTitle>
      </CardHeader>
      <CardContent className="flex-1 overflow-y-auto">
        {loading && items.length === 0 && (
          <p className="text-sm text-muted-foreground">Loading sources…</p>
        )}
        {error && (
          <p className="text-sm text-rose-600 dark:text-rose-400">{error}</p>
        )}
        {!loading && !error && items.length === 0 && (
          <p className="text-sm text-muted-foreground">
            No sources cited yet.
          </p>
        )}
        <ul className="space-y-3">
          {items.map((item) => (
            <SourceCard
              key={item.src_id}
              item={item}
              highlighted={highlightedSrcId === item.src_id}
            />
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}

interface SourceCardProps {
  item: EvidenceItem;
  highlighted: boolean;
}

function SourceCard({ item, highlighted }: SourceCardProps) {
  const ref = useRef<HTMLLIElement>(null);

  // Scroll into view whenever this card becomes the highlight target.
  useEffect(() => {
    if (highlighted && ref.current) {
      ref.current.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }, [highlighted]);

  const ringClass = highlighted
    ? "ring-2 ring-amber-400 dark:ring-amber-500"
    : "ring-1 ring-border";

  const kindBadge = useMemo(() => {
    const cls =
      item.kind === "web"
        ? "bg-sky-100 text-sky-900 dark:bg-sky-900/40 dark:text-sky-200"
        : "bg-violet-100 text-violet-900 dark:bg-violet-900/40 dark:text-violet-200";
    return (
      <span
        className={`inline-flex shrink-0 items-center rounded px-1.5 py-0.5 text-xs font-medium ${cls}`}
      >
        {item.kind}
      </span>
    );
  }, [item.kind]);

  const titleNode = item.url ? (
    <a
      href={item.url}
      target="_blank"
      rel="noreferrer noopener"
      className="font-medium text-foreground underline-offset-2 hover:underline"
    >
      {item.title}
    </a>
  ) : (
    <span className="font-medium text-foreground">{item.title}</span>
  );

  return (
    <li
      ref={ref}
      id={`source-${item.src_id}`}
      className={`rounded-md bg-card p-3 text-sm transition-shadow ${ringClass}`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <code className="rounded bg-muted px-1 py-0.5 text-xs">
              {item.src_id}
            </code>
            {kindBadge}
          </div>
          <div className="mt-1 truncate">{titleNode}</div>
        </div>
      </div>
      <p className="mt-2 line-clamp-3 text-muted-foreground">{item.snippet}</p>
      <div className="mt-2 text-xs text-muted-foreground">
        provider: {item.provider}
      </div>
    </li>
  );
}
