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
    expect(parent?.eventCount).toBe(4);
    expect(parent?.lastTs).toBe("2026-04-28T10:00:30Z");
    expect(parent?.state).toBe("working");
    expect(parent?.children).toEqual([
      expect.objectContaining({
        id: "stage1_foundation.market_sizing",
        label: "Market Sizing",
        state: "completed",
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

  it("keeps the parent stage state in sync when worker activity advances to the next stage", () => {
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
        agent: "stage2_analysis",
        type: "agent_message",
        payload: { text: "Stage 2 started" },
      }),
    ];

    const { result } = renderHook(() => useAgentStates(events));

    const stage1 = result.current.nodes.find((node) => node.id === "stage1_foundation");
    const stage2 = result.current.nodes.find((node) => node.id === "stage2_analysis");

    expect(stage1).toBeDefined();
    expect(stage1?.eventCount).toBe(2);
    expect(stage1?.lastTs).toBe("2026-04-28T10:00:10Z");
    expect(stage1?.state).toBe("completed");
    expect(stage1?.children).toEqual([
      expect.objectContaining({
        id: "stage1_foundation.market_sizing",
        state: "completed",
        lastMessage: "Sizing TAM",
      }),
    ]);
    expect(stage2?.state).toBe("working");
    expect(result.current.activeId).toBe("stage2_analysis");
  });
});
