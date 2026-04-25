"use client";

/**
 * AgentTrace — chronological timeline of agent activity (M7.2).
 *
 * Filters the raw run-event stream to the subset that represents
 * "what an agent did" — `agent_message`, `gate_verdict`, and
 * `artifact_update`. Other event types (`heartbeat`, `usage_update`,
 * `cancel_ack`, `run_completed`, …) are intentionally hidden so the
 * timeline reads as a narrative.
 *
 * The component is purely presentational: events are passed in by the
 * parent page, which already maintains the SSE connection. We never
 * open our own EventSource here.
 */

import { useMemo } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { RunEvent } from "@/lib/sse";

const TRACE_TYPES = new Set(["agent_message", "gate_verdict", "artifact_update"]);

interface AgentTraceProps {
  events: RunEvent[];
}

export function AgentTrace({ events }: AgentTraceProps) {
  const traceEvents = useMemo(
    () => events.filter((e) => TRACE_TYPES.has(e.type)),
    [events],
  );

  return (
    <Card>
      <CardHeader>
        <CardTitle>Agent activity</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {traceEvents.length === 0 ? (
          <p className="text-sm text-muted-foreground">No agent activity yet.</p>
        ) : null}
        {traceEvents.map((evt) => (
          <TraceEntry key={evt.id} event={evt} />
        ))}
      </CardContent>
    </Card>
  );
}

function TraceEntry({ event }: { event: RunEvent }) {
  const agent = event.agent ?? "system";
  return (
    <div className="rounded-md border p-3">
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span className="font-mono">{agent}</span>
        <TypeBadge type={event.type} payload={event.payload} />
      </div>
      <div className="mt-2 text-sm">
        <TraceBody type={event.type} payload={event.payload} />
      </div>
    </div>
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
        ? "bg-emerald-100 text-emerald-900"
        : verdict === "reiterate"
          ? "bg-amber-100 text-amber-900"
          : "bg-rose-100 text-rose-900";
    return (
      <span className={`rounded px-2 py-0.5 text-[10px] uppercase ${tone}`}>
        {verdict || "gate"}
      </span>
    );
  }
  if (type === "artifact_update") {
    return (
      <span className="rounded bg-sky-100 px-2 py-0.5 text-[10px] uppercase text-sky-900">
        artifact
      </span>
    );
  }
  return (
    <span className="rounded bg-slate-100 px-2 py-0.5 text-[10px] uppercase text-slate-900">
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
    return <p className="whitespace-pre-wrap">{text}</p>;
  }
  if (type === "artifact_update") {
    const path = typeof payload.path === "string" ? payload.path : "(unknown)";
    return (
      <p>
        Wrote artifact <code className="font-mono text-xs">{path}</code>
      </p>
    );
  }
  if (type === "gate_verdict") {
    const stage = typeof payload.stage === "string" ? payload.stage : "?";
    const attempt =
      typeof payload.attempt === "number" ? payload.attempt : "?";
    const rationale =
      typeof payload.rationale === "string" ? payload.rationale : "";
    const gaps = Array.isArray(payload.gaps) ? (payload.gaps as unknown[]) : [];
    return (
      <div className="space-y-1">
        <p>
          <span className="font-mono text-xs">{stage}</span> · attempt {attempt}
        </p>
        {rationale ? <p className="text-muted-foreground">{rationale}</p> : null}
        {gaps.length > 0 ? (
          <ul className="list-disc pl-5 text-xs text-muted-foreground">
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
