"use client";

import { useMemo } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useEventStream } from "@/lib/sse";

interface ChatStreamProps {
  runId: string;
}

export function ChatStream({ runId }: ChatStreamProps) {
  const { events, status } = useEventStream(runId);

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
