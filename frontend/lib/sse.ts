"use client";

import { useEffect, useRef, useState } from "react";

import { TERMINAL_RUN_EVENT_TYPES } from "@/lib/runEvents";

export interface RunEvent {
  id: number;
  run_id: string;
  ts: string;
  agent: string | null;
  type: string;
  payload: Record<string, unknown>;
}

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

/**
 * Terminal SSE event types — once any of these arrive the run is over
 * and there is no point keeping the EventSource connection alive.
 */
const RUN_EVENT_TYPES = [
  "artifact_update",
  "agent_message",
  "gate_verdict",
  "usage_update",
  "cancel_ack",
  "run_completed",
  "run_failed",
  "system.run_failed",
  "run_cancelled",
] as const;

/** Hard ceiling on buffered events to prevent unbounded memory growth. */
const MAX_EVENTS = 5_000;

/** Maximum reconnect delay (seconds). */
const MAX_BACKOFF_SEC = 30;

/** Give up after this many consecutive reconnect failures. */
const MAX_RETRIES = 10;

export function useEventStream(runId: string | null) {
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [status, setStatus] = useState<"idle" | "connecting" | "open" | "closed">("idle");
  const lastEventIdRef = useRef<number | null>(null);
  const reconnectTimer = useRef<number | null>(null);
  const retriesRef = useRef(0);
  /** Set to true once a terminal event lands — prevents further reconnects. */
  const terminalRef = useRef(false);

  useEffect(() => {
    if (runId === null) {
      return;
    }

    let closed = false;
    let es: EventSource | null = null;

    // Reset per-mount state.
    retriesRef.current = 0;
    terminalRef.current = false;

    const connect = () => {
      if (closed || terminalRef.current) return;

      setStatus("connecting");

      const params = new URLSearchParams();
      if (lastEventIdRef.current !== null) {
        params.set("last_event_id", String(lastEventIdRef.current));
      }
      const query = params.toString();
      const url = `${BASE_URL}/runs/${runId}/stream${query ? `?${query}` : ""}`;
      es = new EventSource(url);

      es.onopen = () => {
        setStatus("open");
        // Reset retry counter on successful connection.
        retriesRef.current = 0;
      };

      const handleEvent = (evt: MessageEvent<string>) => {
        try {
          const parsed = JSON.parse(evt.data) as RunEvent;

          // Deduplication: skip events we've already seen.
          if (
            lastEventIdRef.current !== null &&
            parsed.id <= lastEventIdRef.current
          ) {
            return;
          }

          lastEventIdRef.current = parsed.id;

          setEvents((prev) => {
            const next = [...prev, parsed];
            // Cap the array to prevent unbounded memory growth.
            if (next.length > MAX_EVENTS) {
              return next.slice(next.length - MAX_EVENTS);
            }
            return next;
          });

          // If this is a terminal event, close the connection for good.
          if (TERMINAL_RUN_EVENT_TYPES.has(parsed.type)) {
            terminalRef.current = true;
            es?.close();
            setStatus("closed");
          }
        } catch {
          // ignore malformed message
        }
      };

      es.onmessage = handleEvent;
      for (const type of RUN_EVENT_TYPES) {
        es.addEventListener(type, handleEvent as EventListener);
      }

      es.onerror = () => {
        es?.close();
        setStatus("closed");

        if (closed || terminalRef.current) return;

        retriesRef.current += 1;
        if (retriesRef.current > MAX_RETRIES) {
          // Give up — don't hammer the server (or leak memory) forever.
          return;
        }

        // Exponential backoff: 1s, 2s, 4s, 8s, 16s, capped at MAX_BACKOFF_SEC.
        const delaySec = Math.min(
          2 ** (retriesRef.current - 1),
          MAX_BACKOFF_SEC,
        );
        reconnectTimer.current = window.setTimeout(
          connect,
          delaySec * 1_000,
        );
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
