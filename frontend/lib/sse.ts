"use client";

import { useEffect, useRef, useState } from "react";

export interface RunEvent {
  id: number;
  run_id: string;
  ts: string;
  agent: string | null;
  type: string;
  payload: Record<string, unknown>;
}

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export function useEventStream(runId: string | null) {
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [status, setStatus] = useState<"idle" | "connecting" | "open" | "closed">("idle");
  const lastEventIdRef = useRef<number | null>(null);
  const reconnectTimer = useRef<number | null>(null);

  useEffect(() => {
    if (runId === null) {
      return;
    }

    let closed = false;
    let es: EventSource | null = null;

    const connect = () => {
      if (closed) return;

      const params = new URLSearchParams();
      if (lastEventIdRef.current !== null) {
        params.set("last_event_id", String(lastEventIdRef.current));
      }
      const query = params.toString();
      const url = `${BASE_URL}/runs/${runId}/stream${query ? `?${query}` : ""}`;
      es = new EventSource(url);

      es.onopen = () => setStatus("open");
      es.onmessage = (evt) => {
        try {
          const parsed = JSON.parse(evt.data) as RunEvent;
          lastEventIdRef.current = parsed.id;
          setEvents((prev) => [...prev, parsed]);
        } catch {
          // ignore malformed message
        }
      };
      es.onerror = () => {
        setStatus("closed");
        es?.close();
        if (!closed) {
          reconnectTimer.current = window.setTimeout(connect, 1000);
        }
      };
    };

    connect();

    return () => {
      closed = true;
      if (reconnectTimer.current !== null) {
        window.clearTimeout(reconnectTimer.current);
      }
      es?.close();
      setStatus("closed");
    };
  }, [runId]);

  if (runId === null) {
    return { events: [], status: "idle" as const };
  }

  return { events, status };
}
