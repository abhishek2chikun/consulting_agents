"use client";

import { useMemo } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useEventStream, type RunEvent } from "@/lib/sse";

interface ChatStreamProps {
  runId: string;
  /**
   * Optionally pass externally-managed events (e.g. when the parent
   * page already subscribes to the SSE stream and wants to avoid
   * opening a second connection). When provided, `useEventStream`
   * inside this component is skipped.
   */
  events?: RunEvent[];
  status?: "idle" | "connecting" | "open" | "closed";
}

export function ChatStream({ runId, events: externalEvents, status: externalStatus }: ChatStreamProps) {
  const internal = useEventStream(externalEvents === undefined ? runId : null);
  const events = externalEvents ?? internal.events;
  const status = externalStatus ?? internal.status;

  const statusLabel = useMemo(() => {
    if (status === "open") return "live";
    if (status === "connecting") return "connecting";
    if (status === "closed") return "reconnecting";
    return "idle";
  }, [status]);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span>Run stream</span>
          <span className="text-xs font-mono text-muted-foreground">{statusLabel}</span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {events.length === 0 ? (
          <p className="text-sm text-muted-foreground">Waiting for events…</p>
        ) : null}
        {events.map((evt) => (
          <div key={evt.id} className="rounded-md border p-3">
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span>#{evt.id}</span>
              <span>{evt.type}</span>
            </div>
            <pre className="mt-2 overflow-x-auto text-xs">
              {JSON.stringify(evt.payload, null, 2)}
            </pre>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
