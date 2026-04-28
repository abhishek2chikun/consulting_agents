"use client";

import { useEffect, useMemo, useRef } from "react";

import { type RunEvent } from "@/lib/sse";
import { cn } from "@/lib/utils";

interface ChatStreamProps {
  events: RunEvent[];
  status: "idle" | "connecting" | "open" | "closed";
}

const TYPE_TONE: Record<string, string> = {
  agent_message: "text-sky-300 bg-sky-500/10 ring-sky-500/20",
  artifact_update: "text-emerald-300 bg-emerald-500/10 ring-emerald-500/20",
  gate_verdict: "text-amber-300 bg-amber-500/10 ring-amber-500/20",
  usage_update: "text-violet-300 bg-violet-500/10 ring-violet-500/20",
  run_completed: "text-emerald-300 bg-emerald-500/10 ring-emerald-500/20",
  run_failed: "text-rose-300 bg-rose-500/10 ring-rose-500/20",
  "system.run_failed": "text-rose-300 bg-rose-500/10 ring-rose-500/20",
  run_cancelled: "text-stone-300 bg-stone-500/10 ring-stone-500/20",
  cancel_ack: "text-stone-300 bg-stone-500/10 ring-stone-500/20",
};

function summarizePayload(type: string, payload: Record<string, unknown>): string {
  if (type === "agent_message" && typeof payload.text === "string") {
    return payload.text;
  }
  if (type === "artifact_update" && typeof payload.path === "string") {
    return payload.path;
  }
  if (type === "gate_verdict") {
    const v = String(payload.verdict ?? "");
    const stage = String(payload.stage ?? "");
    return `${stage} → ${v}`;
  }
  if (type === "usage_update") {
    const t = Number(payload.total_tokens ?? 0);
    const c = Number(payload.cost_usd ?? 0);
    return `${t.toLocaleString()} tok · $${c.toFixed(4)}`;
  }
  // Compact JSON for unknown
  const json = JSON.stringify(payload);
  return json.length > 80 ? json.slice(0, 77) + "…" : json;
}

export function ChatStream({ events, status }: ChatStreamProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const lastIdRef = useRef<number>(0);

  const statusMeta = useMemo(() => {
    if (status === "open")
      return { label: "live", dot: "bg-emerald-400", text: "text-emerald-400" };
    if (status === "connecting")
      return { label: "connecting", dot: "bg-amber-400 animate-pulse", text: "text-amber-400" };
    if (status === "closed")
      return { label: "closed", dot: "bg-stone-500", text: "text-stone-500" };
    return { label: "idle", dot: "bg-stone-500", text: "text-stone-500" };
  }, [status]);

  // Auto-scroll to bottom when new events arrive.
  useEffect(() => {
    const el = scrollRef.current;
    if (!el || events.length === 0) return;
    const newest = events[events.length - 1];
    if (newest && newest.id !== lastIdRef.current) {
      lastIdRef.current = newest.id;
      el.scrollTop = el.scrollHeight;
    }
  }, [events]);

  return (
    <div className="panel flex flex-col">
      <div className="panel-header">
        <span>Run stream</span>
        <span className={cn("flex items-center gap-1.5 text-[10px] font-medium normal-case tracking-normal", statusMeta.text)}>
          <span className={cn("size-1.5 rounded-full", statusMeta.dot)} />
          {statusMeta.label}
        </span>
      </div>
      <div ref={scrollRef} className="scroll-thin max-h-[28rem] flex-1 overflow-y-auto px-3 py-2">
        {events.length === 0 ? (
          <p className="px-1 py-3 text-xs text-stone-500">Waiting for events…</p>
        ) : (
          <ul className="space-y-1">
            {events.map((evt) => (
              <li
                key={evt.id}
                className="group flex items-start gap-2 rounded-md px-1.5 py-1 hover:bg-white/[0.03]"
              >
                <span className="mt-0.5 w-7 shrink-0 text-right font-mono text-[10px] text-stone-600">
                  {evt.id}
                </span>
                <span
                  className={cn(
                    "mt-0.5 shrink-0 rounded px-1.5 py-0.5 text-[9px] font-semibold tracking-wider uppercase ring-1",
                    TYPE_TONE[evt.type] ?? "bg-stone-500/10 text-stone-400 ring-stone-500/20",
                  )}
                >
                  {evt.type.replace(/_/g, " ")}
                </span>
                <p className="min-w-0 flex-1 truncate text-xs text-stone-300" title={summarizePayload(evt.type, evt.payload)}>
                  {summarizePayload(evt.type, evt.payload)}
                </p>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
