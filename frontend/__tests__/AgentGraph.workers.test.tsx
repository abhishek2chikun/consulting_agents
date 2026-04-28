import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { RunEvent } from "@/lib/sse";
import { AgentGraph } from "@/components/AgentGraph";

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

describe("AgentGraph worker children", () => {
  it("renders worker mini-cards beneath the parent stage and supports collapse/expand", () => {
    render(
      <AgentGraph
        events={[
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
            agent: "stage1_foundation.competitive_scan",
            type: "agent_message",
            payload: { text: "Comparing peers" },
          }),
        ]}
      />,
    );

    const stageButton = screen.getByRole("button", { name: /^foundation\s+.+$/i });
    const stageCard = stageButton.closest("[data-agent-node='stage1_foundation']");

    expect(stageCard).not.toBeNull();
    expect(within(stageCard as HTMLElement).getByRole("button", { name: /hide workers/i })).toBeVisible();
    expect(within(stageCard as HTMLElement).getByText("Market Sizing")).toBeVisible();
    expect(within(stageCard as HTMLElement).getByText("Competitive Scan")).toBeVisible();

    fireEvent.click(within(stageCard as HTMLElement).getByRole("button", { name: /hide workers/i }));

    expect(within(stageCard as HTMLElement).queryByText("Market Sizing")).toBeNull();
    expect(within(stageCard as HTMLElement).queryByText("Competitive Scan")).toBeNull();
    expect(within(stageCard as HTMLElement).getByRole("button", { name: /show workers/i })).toBeVisible();

    fireEvent.click(within(stageCard as HTMLElement).getByRole("button", { name: /show workers/i }));

    expect(within(stageCard as HTMLElement).getByText("Market Sizing")).toBeVisible();
    expect(within(stageCard as HTMLElement).getByText("Competitive Scan")).toBeVisible();
  });
});
