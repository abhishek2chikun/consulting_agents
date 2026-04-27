"use client";

import { useEffect, useRef, useState } from "react";
import { ExternalLink, Globe, FileText } from "lucide-react";

import { ApiRequestError, getRunEvidence } from "@/lib/api";
import type { RunEvent } from "@/lib/sse";
import type { EvidenceItem } from "@/lib/types";
import { cn } from "@/lib/utils";

interface SourcesSidebarProps {
  runId: string;
  events: RunEvent[];
  highlightedSrcId?: string | null;
}

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
    <div className="panel flex flex-col">
      <div className="panel-header">
        <span>Sources</span>
        <span className="text-[10px] font-medium tracking-normal text-stone-500 normal-case">
          {items.length}
        </span>
      </div>
      <div className="scroll-thin max-h-[36rem] flex-1 overflow-y-auto p-3">
        {loading && items.length === 0 && (
          <p className="text-xs text-stone-500">Loading sources…</p>
        )}
        {error && <p className="text-xs text-rose-400">{error}</p>}
        {!loading && !error && items.length === 0 && (
          <p className="text-xs text-stone-500">No sources cited yet.</p>
        )}
        <ul className="space-y-2">
          {items.map((item) => (
            <SourceCard
              key={item.src_id}
              item={item}
              highlighted={highlightedSrcId === item.src_id}
            />
          ))}
        </ul>
      </div>
    </div>
  );
}

function SourceCard({
  item,
  highlighted,
}: {
  item: EvidenceItem;
  highlighted: boolean;
}) {
  const ref = useRef<HTMLLIElement>(null);

  useEffect(() => {
    if (highlighted && ref.current) {
      ref.current.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }, [highlighted]);

  const Icon = item.kind === "web" ? Globe : FileText;
  const tone =
    item.kind === "web"
      ? "text-sky-300 bg-sky-500/10"
      : "text-violet-300 bg-violet-500/10";

  return (
    <li
      ref={ref}
      id={`source-${item.src_id}`}
      className={cn(
        "rounded-lg border p-2.5 text-xs transition-all",
        highlighted
          ? "border-amber-400/60 bg-amber-500/5 ring-1 ring-amber-400/30"
          : "border-white/5 bg-white/[0.02] hover:bg-white/[0.04]",
      )}
    >
      <div className="mb-1.5 flex items-center gap-1.5">
        <span className={cn("flex size-5 shrink-0 items-center justify-center rounded-md", tone)}>
          <Icon className="size-3" />
        </span>
        <code className="rounded bg-white/[0.06] px-1.5 py-0.5 font-mono text-[9px] text-stone-300">
          {item.src_id}
        </code>
        <span className="ml-auto truncate text-[9px] text-stone-500">
          {item.provider}
        </span>
      </div>
      <div className="mb-1 truncate font-medium text-stone-100">
        {item.url ? (
          <a
            href={item.url}
            target="_blank"
            rel="noreferrer noopener"
            className="inline-flex items-center gap-1 hover:text-sky-300"
          >
            {item.title}
            <ExternalLink className="size-2.5 shrink-0 opacity-60" />
          </a>
        ) : (
          item.title
        )}
      </div>
      <p className="line-clamp-3 leading-relaxed text-stone-400">{item.snippet}</p>
    </li>
  );
}
