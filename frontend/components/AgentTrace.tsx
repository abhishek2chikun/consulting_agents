"use client";

/**
 * AgentTrace — chronological narrative of agent activity.
 * Filters to message / artifact / verdict events only.
 */

import { useMemo } from "react";

import type { RunEvent } from "@/lib/sse";
import { cn } from "@/lib/utils";

const TRACE_TYPES = new Set(["agent_message", "gate_verdict", "artifact_update"]);

const AGENT_COLOR: Record<string, string> = {
  framing: "from-violet-500 to-fuchsia-500",
  research: "from-sky-500 to-cyan-500",
  reviewer: "from-amber-500 to-orange-500",
  synthesis: "from-emerald-500 to-teal-500",
  audit: "from-rose-500 to-pink-500",
  system: "from-stone-500 to-stone-600",
};

const AGENT_INITIAL: Record<string, string> = {
  framing: "F",
  research: "R",
  reviewer: "Rv",
  synthesis: "S",
  audit: "A",
  system: "·",
};

interface AgentTraceProps {
  events: RunEvent[];
}

export function AgentTrace({ events }: AgentTraceProps) {
  const traceEvents = useMemo(
    () => events.filter((e) => TRACE_TYPES.has(e.type)),
    [events],
  );

  if (traceEvents.length === 0) {
    return (
      <div className="flex h-40 flex-col items-center justify-center gap-1 text-center">
        <p className="text-sm font-medium text-stone-400">No activity yet</p>
        <p className="text-xs text-stone-500">Agent messages will appear here as they stream.</p>
      </div>
    );
  }

  return (
    <ol className="relative space-y-3 border-l border-white/5 pl-5">
      {traceEvents.map((evt) => (
        <TraceEntry key={evt.id} event={evt} />
      ))}
    </ol>
  );
}

function TraceEntry({ event }: { event: RunEvent }) {
  const agent = (event.agent ?? "system").toLowerCase();
  const grad = AGENT_COLOR[agent] ?? AGENT_COLOR.system;
  const initial = AGENT_INITIAL[agent] ?? agent.slice(0, 1).toUpperCase();

  return (
    <li className="relative">
      {/* Avatar bullet on the timeline */}
      <span
        className={cn(
          "absolute -left-[27px] top-1 flex size-4 items-center justify-center rounded-full bg-gradient-to-br text-[8px] font-bold text-white ring-2 ring-stone-950",
          grad,
        )}
      >
        {initial}
      </span>

      <div className="rounded-lg border border-white/5 bg-white/[0.02] p-3 transition hover:bg-white/[0.04]">
        <div className="mb-1.5 flex items-center justify-between gap-2">
          <span className="font-mono text-[11px] font-medium text-stone-400 capitalize">
            {agent}
          </span>
          <TypeBadge type={event.type} payload={event.payload} />
        </div>
        <div className="text-sm text-stone-200">
          <TraceBody type={event.type} payload={event.payload} />
        </div>
      </div>
    </li>
  );
}

function TypeBadge({
  type,
  payload,
}: {
  type: string;
  payload: Record<string, unknown>;
}) {
  if (type === "gate_verdict") {
    const verdict = String(payload.verdict ?? "");
    const tone =
      verdict === "advance"
        ? "bg-emerald-500/15 text-emerald-300 ring-emerald-500/30"
        : verdict === "reiterate"
          ? "bg-amber-500/15 text-amber-300 ring-amber-500/30"
          : "bg-rose-500/15 text-rose-300 ring-rose-500/30";
    return (
      <span className={cn("rounded-full px-2 py-0.5 text-[9px] font-semibold uppercase tracking-wider ring-1", tone)}>
        {verdict || "gate"}
      </span>
    );
  }
  if (type === "artifact_update") {
    return (
      <span className="rounded-full bg-sky-500/15 px-2 py-0.5 text-[9px] font-semibold uppercase tracking-wider text-sky-300 ring-1 ring-sky-500/30">
        artifact
      </span>
    );
  }
  return (
    <span className="rounded-full bg-stone-500/15 px-2 py-0.5 text-[9px] font-semibold uppercase tracking-wider text-stone-300 ring-1 ring-stone-500/30">
      message
    </span>
  );
}

function TraceBody({
  type,
  payload,
}: {
  type: string;
  payload: Record<string, unknown>;
}) {
  if (type === "agent_message") {
    const text = typeof payload.text === "string" ? payload.text : "";
    return <p className="leading-relaxed whitespace-pre-wrap text-stone-200">{text}</p>;
  }
  if (type === "artifact_update") {
    const path = typeof payload.path === "string" ? payload.path : "(unknown)";
    return (
      <p className="text-stone-300">
        Wrote artifact{" "}
        <code className="rounded bg-white/[0.06] px-1.5 py-0.5 font-mono text-[11px] text-stone-200">
          {path}
        </code>
      </p>
    );
  }
  if (type === "gate_verdict") {
    const stage = typeof payload.stage === "string" ? payload.stage : "?";
    const attempt = typeof payload.attempt === "number" ? payload.attempt : "?";
    const rationale = typeof payload.rationale === "string" ? payload.rationale : "";
    const gaps = Array.isArray(payload.gaps) ? (payload.gaps as unknown[]) : [];
    return (
      <div className="space-y-1.5">
        <p className="text-xs text-stone-400">
          <span className="font-mono text-stone-300">{stage}</span> · attempt {attempt}
        </p>
        {rationale ? <p className="leading-relaxed text-stone-200">{rationale}</p> : null}
        {gaps.length > 0 ? (
          <ul className="ml-4 list-disc space-y-0.5 text-xs text-stone-400">
            {gaps.map((gap, i) => (
              <li key={i}>{String(gap)}</li>
            ))}
          </ul>
        ) : null}
      </div>
    );
  }
  return null;
}
