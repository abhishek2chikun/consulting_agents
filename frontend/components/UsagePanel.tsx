"use client";

/**
 * UsagePanel — running token + USD cost totals for a run (M7.5).
 *
 * Reads from the SSE event stream rather than polling: the backend
 * `BudgetTracker` (see `app/agents/budget.py`) emits a
 * `usage_update` event after every LLM call, with absolute totals
 * for the run alongside the per-call delta. We render the latest
 * snapshot.
 *
 * Includes a Cancel button that POSTs to `/runs/{id}/cancel`. The
 * button is disabled when the run is already in a terminal state or
 * the cancel request is in flight; the actual run-status transition
 * is observed via the `run_status` event the parent page already
 * receives.
 */

import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cancelRun } from "@/lib/api";
import type { RunEvent } from "@/lib/sse";

interface UsagePanelProps {
  runId: string;
  events: RunEvent[];
  /** Latest known run status (drives Cancel button enablement). */
  status?: string | undefined;
}

interface UsageSnapshot {
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  cost_usd: number;
  model_name?: string;
}

const TERMINAL_STATUSES = new Set(["completed", "failed", "cancelled"]);

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

export function UsagePanel({ runId, events, status }: UsagePanelProps) {
  const [cancelling, setCancelling] = useState(false);
  const [cancelError, setCancelError] = useState<string | null>(null);

  const snapshot = useMemo(() => latestUsageSnapshot(events), [events]);
  const terminal = status ? TERMINAL_STATUSES.has(status) : false;

  const handleCancel = async () => {
    setCancelling(true);
    setCancelError(null);
    try {
      await cancelRun(runId);
    } catch (err) {
      setCancelError(err instanceof Error ? err.message : "Cancel failed");
    } finally {
      setCancelling(false);
    }
  };

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle className="text-base">Usage</CardTitle>
        <Button
          variant="outline"
          size="sm"
          onClick={handleCancel}
          disabled={terminal || cancelling || status === "cancelling"}
        >
          {cancelling ? "Cancelling…" : "Cancel run"}
        </Button>
      </CardHeader>
      <CardContent>
        {snapshot === null ? (
          <p className="text-sm text-muted-foreground">No usage yet.</p>
        ) : (
          <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
            <dt className="text-muted-foreground">Input tokens</dt>
            <dd className="text-right font-mono">
              {snapshot.input_tokens.toLocaleString()}
            </dd>
            <dt className="text-muted-foreground">Output tokens</dt>
            <dd className="text-right font-mono">
              {snapshot.output_tokens.toLocaleString()}
            </dd>
            <dt className="text-muted-foreground">Total tokens</dt>
            <dd className="text-right font-mono">
              {snapshot.total_tokens.toLocaleString()}
            </dd>
            <dt className="text-muted-foreground">Cost (USD)</dt>
            <dd className="text-right font-mono">
              ${snapshot.cost_usd.toFixed(4)}
            </dd>
            {snapshot.model_name && (
              <>
                <dt className="text-muted-foreground">Last model</dt>
                <dd className="truncate text-right font-mono text-xs">
                  {snapshot.model_name}
                </dd>
              </>
            )}
          </dl>
        )}
        {cancelError && (
          <p className="mt-2 text-sm text-rose-600 dark:text-rose-400">
            {cancelError}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
