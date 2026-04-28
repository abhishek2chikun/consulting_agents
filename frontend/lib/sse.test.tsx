import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useEventStream, type RunEvent } from "@/lib/sse";

function event(overrides: Partial<RunEvent>): RunEvent {
  return {
    id: overrides.id ?? 1,
    run_id: overrides.run_id ?? "run-1",
    ts: overrides.ts ?? "2026-04-29T10:00:00Z",
    agent: overrides.agent ?? null,
    type: overrides.type ?? "agent_message",
    payload: overrides.payload ?? {},
  };
}

class MockEventSource {
  static instances: MockEventSource[] = [];

  readonly url: string;
  readonly listeners = new Map<string, Set<EventListener>>();
  onopen: ((this: EventSource, ev: Event) => unknown) | null = null;
  onmessage: ((this: EventSource, ev: MessageEvent<string>) => unknown) | null = null;
  onerror: ((this: EventSource, ev: Event) => unknown) | null = null;
  closed = false;

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
  }

  addEventListener(type: string, listener: EventListener) {
    const listeners = this.listeners.get(type) ?? new Set<EventListener>();
    listeners.add(listener);
    this.listeners.set(type, listeners);
  }

  close() {
    this.closed = true;
  }

  emitOpen() {
    this.onopen?.call(this as unknown as EventSource, new Event("open"));
  }

  emitError() {
    this.onerror?.call(this as unknown as EventSource, new Event("error"));
  }

  emit(type: string, payload: RunEvent) {
    const message = new MessageEvent<string>(type, {
      data: JSON.stringify(payload),
    });

    this.onmessage?.call(this as unknown as EventSource, message);
    for (const listener of this.listeners.get(type) ?? []) {
      listener.call(this as unknown as EventSource, message);
    }
  }

  static reset() {
    MockEventSource.instances = [];
  }
}

function latestSource(): MockEventSource {
  const source = MockEventSource.instances.at(-1);
  if (source === undefined) {
    throw new Error("expected EventSource to be created");
  }
  return source;
}

describe("useEventStream", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    MockEventSource.reset();
    vi.stubGlobal("EventSource", MockEventSource as unknown as typeof EventSource);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    MockEventSource.reset();
  });

  it("keeps streaming when replayed failure is followed by retry resume history", async () => {
    const { result } = renderHook(() => useEventStream("run-1"));

    const source = latestSource();

    act(() => {
      source.emitOpen();
      source.emit("run_failed", event({ id: 1, type: "run_failed", payload: { reason: "aws error" } }));
      source.emit("run_retry_started", event({ id: 2, type: "run_retry_started", payload: { resume_from: "analysis" } }));
      source.emit("agent_message", event({ id: 3, type: "agent_message", agent: "researcher", payload: { text: "Resumed" } }));
    });

    expect(result.current.events).toHaveLength(3);

    act(() => {
      vi.advanceTimersByTime(500);
    });

    expect(source.closed).toBe(false);
    expect(result.current.status).toBe("open");
    expect(result.current.events.map((evt) => evt.type)).toEqual([
      "run_failed",
      "run_retry_started",
      "agent_message",
    ]);
  });

  it("closes after the latest lifecycle event settles as terminal", async () => {
    const { result } = renderHook(() => useEventStream("run-2"));

    const source = latestSource();

    act(() => {
      source.emitOpen();
      source.emit("run_completed", event({ id: 10, run_id: "run-2", type: "run_completed" }));
    });

    act(() => {
      vi.advanceTimersByTime(499);
    });

    expect(source.closed).toBe(false);

    act(() => {
      vi.advanceTimersByTime(1);
    });

    expect(result.current.status).toBe("closed");
    expect(source.closed).toBe(true);
  });
});
