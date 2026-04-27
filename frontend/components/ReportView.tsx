"use client";

import { useEffect, useState } from "react";
import { FileText, Loader2 } from "lucide-react";

import { ApiRequestError, getRunArtifact } from "@/lib/api";
import type { RunEvent } from "@/lib/sse";

const REPORT_PATH = "final_report.md";

interface ReportViewProps {
  runId: string;
  events: RunEvent[];
  onCitationClick?: (srcId: string) => void;
}

export function ReportView({ runId, events, onCitationClick }: ReportViewProps) {
  const [content, setContent] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const reportEventId = latestReportEventId(events);

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

  if (loading && content === null) {
    return (
      <div className="flex h-40 items-center justify-center gap-2 text-sm text-stone-400">
        <Loader2 className="size-4 animate-spin" />
        Loading report…
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-rose-500/30 bg-rose-500/5 p-4 text-sm text-rose-300">
        {error}
      </div>
    );
  }

  if (content === null) {
    return (
      <div className="flex h-60 flex-col items-center justify-center gap-2 text-center">
        <div className="flex size-12 items-center justify-center rounded-full bg-white/[0.04]">
          <FileText className="size-5 text-stone-500" />
        </div>
        <p className="text-sm font-medium text-stone-400">Report pending</p>
        <p className="max-w-xs text-xs text-stone-500">
          The final report appears here once synthesis finishes.
        </p>
      </div>
    );
  }

  return (
    <article className="report-prose">
      <MarkdownBody source={content} onCitationClick={onCitationClick} />
    </article>
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
// Tiny markdown renderer
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
      i++;
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
      <pre className="my-4 overflow-x-auto rounded-lg border border-white/5 bg-black/40 p-3 font-mono text-xs text-stone-200">
        <code>{block.text}</code>
      </pre>
    );
  }
  if (block.kind === "heading") {
    if (block.level === 1)
      return (
        <h1 className="mt-2 mb-3 text-2xl font-semibold tracking-tight text-white">
          <Inline text={block.text} onCitationClick={onCitationClick} />
        </h1>
      );
    if (block.level === 2)
      return (
        <h2 className="mt-6 mb-2 border-b border-white/5 pb-2 text-lg font-semibold tracking-tight text-white">
          <Inline text={block.text} onCitationClick={onCitationClick} />
        </h2>
      );
    if (block.level === 3)
      return (
        <h3 className="mt-5 mb-2 text-sm font-semibold tracking-wide text-stone-200 uppercase">
          <Inline text={block.text} onCitationClick={onCitationClick} />
        </h3>
      );
    return (
      <h4 className="mt-4 mb-1.5 text-sm font-semibold text-stone-300">
        <Inline text={block.text} onCitationClick={onCitationClick} />
      </h4>
    );
  }
  if (block.kind === "list") {
    return (
      <ul className="my-2 ml-5 list-disc space-y-1 text-sm text-stone-300 marker:text-stone-600">
        {block.items.map((item, i) => (
          <li key={i} className="leading-relaxed">
            <Inline text={item} onCitationClick={onCitationClick} />
          </li>
        ))}
      </ul>
    );
  }
  return (
    <p className="my-2 text-sm leading-relaxed text-stone-300">
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
  const re = new RegExp(CITATION_RE.source, CITATION_RE.flags);
  let match: RegExpExecArray | null;
  while ((match = re.exec(text)) !== null) {
    if (match.index > lastIdx) parts.push(text.slice(lastIdx, match.index));
    const srcId = match[1];
    if (srcId === undefined) continue;
    const chipProps: { srcId: string; onClick?: CitationHandler } = { srcId };
    if (onCitationClick) chipProps.onClick = onCitationClick;
    parts.push(<CitationChip key={`${match.index}-${srcId}`} {...chipProps} />);
    lastIdx = match.index + match[0].length;
  }
  if (lastIdx < text.length) parts.push(text.slice(lastIdx));
  return <>{parts}</>;
}

function CitationChip({
  srcId,
  onClick,
}: {
  srcId: string;
  onClick?: CitationHandler;
}) {
  const cls =
    "mx-0.5 inline-flex items-center rounded-md bg-sky-500/15 px-1.5 py-0 align-baseline font-mono text-[10px] font-medium text-sky-300 ring-1 ring-sky-500/20 transition hover:bg-sky-500/25 hover:text-sky-200";
  if (!onClick) return <span className={cls}>{srcId}</span>;
  return (
    <button type="button" className={cls + " cursor-pointer"} onClick={() => onClick(srcId)}>
      {srcId}
    </button>
  );
}
