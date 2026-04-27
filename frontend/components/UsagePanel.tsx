"use client";

import { useMemo } from "react";

import type { RunEvent } from "@/lib/sse";

interface UsagePanelProps {
  events: RunEvent[];
}

interface UsageSnapshot {
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  cost_usd: number;
  model_name?: string;
}

function latestUsageSnapshot(events: RunEvent[]): UsageSnapshot | null {
  for (let i = events.length - 1; i >= 0; i -= 1) {
    const ev = events[i];
    if (ev && ev.type === "usage_update") {
      const p = ev.payload as Record<string, unknown>;
      return {
        input_tokens: Number(p.input_tokens ?? 0),
        output_tokens: Number(p.output_tokens ?? 0),
        total_tokens: Number(p.total_tokens ?? 0),
        cost_usd: Number(p.cost_usd ?? 0),
        ...(typeof p.model_name === "string" ? { model_name: p.model_name } : {}),
      };
    }
  }
  return null;
}

export function UsagePanel({ events }: UsagePanelProps) {
  const snapshot = useMemo(() => latestUsageSnapshot(events), [events]);

  return (
    <div className="panel">
      <div className="panel-header">
        <span>Usage</span>
        {snapshot?.model_name && (
          <span className="max-w-[10rem] truncate font-mono text-[10px] tracking-normal text-stone-500 normal-case">
            {snapshot.model_name}
          </span>
        )}
      </div>
      <div className="p-3">
        {snapshot === null ? (
          <p className="text-xs text-stone-500">No usage yet.</p>
        ) : (
          <div className="space-y-3">
            {/* Cost — hero */}
            <div className="rounded-lg border border-white/5 bg-white/[0.02] p-3">
              <div className="text-[10px] font-semibold tracking-wider text-stone-500 uppercase">
                Cost
              </div>
              <div className="mt-1 font-mono text-2xl font-semibold tracking-tight text-white">
                ${snapshot.cost_usd.toFixed(4)}
              </div>
            </div>
            {/* Token grid */}
            <div className="grid grid-cols-3 gap-2">
              <Stat label="Input" value={snapshot.input_tokens} />
              <Stat label="Output" value={snapshot.output_tokens} />
              <Stat label="Total" value={snapshot.total_tokens} accent />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function Stat({
  label,
  value,
  accent,
}: {
  label: string;
  value: number;
  accent?: boolean;
}) {
  return (
    <div className="rounded-lg border border-white/5 bg-white/[0.02] p-2 text-center">
      <div className="text-[9px] font-semibold tracking-wider text-stone-500 uppercase">
        {label}
      </div>
      <div
        className={
          accent
            ? "mt-0.5 font-mono text-sm font-semibold text-sky-300"
            : "mt-0.5 font-mono text-sm font-medium text-stone-200"
        }
      >
        {value.toLocaleString()}
      </div>
    </div>
  );
}
