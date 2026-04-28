import { describe, expect, it } from "vitest";
import { renderHook } from "@testing-library/react";

import type { RunEvent } from "@/lib/sse";
import { useAgentStates } from "@/lib/useAgentStates";

function event(overrides: Partial<RunEvent>): RunEvent {
  return {
    id: overrides.id ?? 1,
    run_id: overrides.run_id ?? "run-1",
    ts: overrides.ts ?? "2026-04-28T10:00:00Z",
    agent: overrides.agent ?? null,
    type: overrides.type ?? "agent_message",
    payload: overrides.payload ?? {},
  };
}

describe("useAgentStates worker nodes", () => {
  it("attaches dotted stage workers under their parent stage with worker-specific metadata", () => {
    const events: RunEvent[] = [
      event({
        id: 1,
        agent: "stage1_foundation",
        type: "agent_message",
        payload: { text: "Parent stage started" },
      }),
      event({
        id: 2,
        ts: "2026-04-28T10:00:10Z",
        agent: "stage1_foundation.market_sizing",
        type: "agent_message",
        payload: { text: "Sizing TAM" },
      }),
      event({
        id: 3,
        ts: "2026-04-28T10:00:20Z",
        agent: "stage1_foundation.market_sizing",
        type: "artifact_update",
        payload: { path: "artifacts/stage1/market-sizing.md" },
      }),
      event({
        id: 4,
        ts: "2026-04-28T10:00:30Z",
        agent: "stage1_foundation.competitive_scan",
        type: "agent_message",
        payload: { text: "Comparing peers" },
      }),
    ];

    const { result } = renderHook(() => useAgentStates(events));

    const parent = result.current.nodes.find((node) => node.id === "stage1_foundation");

    expect(parent).toBeDefined();
    expect(parent?.lastMessage).toBe("Parent stage started");
    expect(parent?.eventCount).toBe(1);
    expect(parent?.children).toEqual([
      expect.objectContaining({
        id: "stage1_foundation.market_sizing",
        label: "Market Sizing",
        state: "working",
        lastMessage: "Sizing TAM",
        artifacts: ["artifacts/stage1/market-sizing.md"],
        eventCount: 2,
      }),
      expect.objectContaining({
        id: "stage1_foundation.competitive_scan",
        label: "Competitive Scan",
        state: "working",
        lastMessage: "Comparing peers",
        artifacts: [],
        eventCount: 1,
      }),
    ]);
    expect(result.current.nodes.find((node) => node.id === "stage1_foundation.market_sizing")).toBeUndefined();
  });
});
