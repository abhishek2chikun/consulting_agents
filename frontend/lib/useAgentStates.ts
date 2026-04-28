"use client";

/**
 * useAgentStates — derives a live agent-graph model from the SSE event stream.
 *
 * Unlike v1 (which hard-coded `framing/research/reviewer/synthesis/audit`),
 * this hook **discovers** stage nodes from the events themselves so it
 * works for every task profile (`market_entry`, `pricing`,
 * `profitability`, `ma`). Nodes are inferred from the `agent` field
 * on each event:
 *
 *   - "framing"            → framing anchor
 *   - "stage{N}_{slug}"    → ordered stage node, label derived from slug
 *   - "reviewer"           → gate-verdict source (decorates edges, no own node)
 *   - "synthesis"          → synthesis anchor
 *   - "audit"              → audit anchor
 *   - "ma.placeholder"     → single placeholder node (M&A V0)
 *
 * Per-node metadata exposed:
 *   - state:       idle | working | completed | failed
 *   - attempt:     latest reiterate/advance attempt number
 *   - lastMessage: most recent `agent_message.text` for hover preview
 *   - artifacts:   distinct artifact paths the stage has written
 *   - lastTs:      ISO timestamp of latest event for this stage
 *   - eventCount:  total events emitted by this stage
 *
 * Reviewer verdicts mutate the *target* stage's state (advance /
 * reiterate) and increment its attempt counter.
 */

import { useMemo } from "react";

import type { RunEvent } from "@/lib/sse";

export type AgentNodeState = "idle" | "working" | "completed" | "failed";

export interface AgentNodeData {
  /** Stable identifier — matches the `agent` field on events. */
  id: string;
  /** Human-readable label. */
  label: string;
  /** Logical kind — drives icon and ordering. */
  kind:
    | "framing"
    | "stage"
    | "worker"
    | "reviewer"
    | "synthesis"
    | "audit"
    | "placeholder";
  /** Visual state. */
  state: AgentNodeState;
  /** 1-based stage index (only set for kind === "stage"). */
  stageIndex?: number;
  /** Latest reviewer attempt number (1 by default). */
  attempt: number;
  /** Whether the reviewer most recently asked for reiteration on this stage. */
  reiterating: boolean;
  /** Latest `agent_message.text` emitted by this stage. */
  lastMessage: string | null;
  /** Distinct artifact paths written by this stage. */
  artifacts: string[];
  /** Latest event timestamp (ISO). */
  lastTs: string | null;
  /** Total number of events for this stage. */
  eventCount: number;
  /** Nested worker nodes for a stage. */
  children?: AgentNodeData[];
}

export interface AgentEdgeData {
  from: string;
  to: string;
  /** True while target node is currently working. */
  active: boolean;
  /** True once target node has completed. */
  done: boolean;
  /** True for the review→prev-stage reiterate loop. */
  loop: boolean;
  /** "flow" = main pipeline, "review" = stage↔reviewer band. */
  kind: "flow" | "review";
}

export interface AgentStatesResult {
  /** Ordered node list ready for rendering. */
  nodes: AgentNodeData[];
  /** Edges between consecutive nodes (plus reiterate loop when active). */
  edges: AgentEdgeData[];
  /** Currently active node id, or null. */
  activeId: string | null;
  /** Latest reviewer verdict, useful for header decorations. */
  latestVerdict: { stage: string; verdict: string; attempt: number } | null;
}

const FALLBACK_NODES: AgentNodeData[] = [
  emptyNode("framing", "Frame", "framing"),
  emptyNode("stage1", "Stage 1", "stage", 1),
  emptyNode("stage2", "Stage 2", "stage", 2),
  emptyNode("stage3", "Stage 3", "stage", 3),
  emptyNode("stage4", "Stage 4", "stage", 4),
  emptyNode("stage5", "Stage 5", "stage", 5),
  emptyNode("synthesis", "Synthesize", "synthesis"),
  emptyNode("audit", "Audit", "audit"),
];

function emptyNode(
  id: string,
  label: string,
  kind: AgentNodeData["kind"],
  stageIndex?: number,
): AgentNodeData {
  const node: AgentNodeData = {
    id,
    label,
    kind,
    state: "idle",
    attempt: 1,
    reiterating: false,
    lastMessage: null,
    artifacts: [],
    lastTs: null,
    eventCount: 0,
  };
  if (stageIndex !== undefined) node.stageIndex = stageIndex;
  return node;
}

function prettyLabel(value: string): string {
  return value
    .split(/[._-]/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

/** Pretty-print a stage slug like `stage4_models` → "Models". */
function prettyStageLabel(slug: string): string {
  const m = slug.match(/^stage\d+_(.+)$/);
  const tail = m ? m[1]! : slug;
  return prettyLabel(tail);
}

function stageIndexFromSlug(slug: string): number | null {
  const m = slug.match(/^stage(\d+)_/);
  return m ? Number(m[1]) : null;
}

function classify(agent: string | null | undefined): {
  kind: AgentNodeData["kind"] | "reviewer" | "other";
  id: string;
  label: string;
  stageIndex?: number;
} {
  if (!agent) return { kind: "other", id: "system", label: "system" };
  const a = agent.toLowerCase().trim();
  if (a === "framing") return { kind: "framing", id: "framing", label: "Frame" };
  if (a === "synthesis" || a === "synthesizer")
    return { kind: "synthesis", id: "synthesis", label: "Synthesize" };
  if (a === "audit" || a === "auditor") return { kind: "audit", id: "audit", label: "Audit" };
  if (a === "reviewer" || a === "review")
    return { kind: "reviewer", id: "reviewer", label: "Review" };
  if (a.startsWith("stage")) {
    const idx = stageIndexFromSlug(a);
    if (idx !== null) {
      return { kind: "stage", id: a, label: prettyStageLabel(a), stageIndex: idx };
    }
  }
  if (a === "ma.placeholder")
    return { kind: "placeholder", id: "ma.placeholder", label: "M&A draft" };
  return { kind: "other", id: a, label: a };
}

function parseWorkerAgent(agent: string | null | undefined): {
  parentId: string;
  workerId: string;
  workerLabel: string;
} | null {
  if (!agent) return null;
  const normalized = agent.toLowerCase().trim();
  const dotIndex = normalized.indexOf(".");
  if (dotIndex <= 0) return null;

  const parentId = normalized.slice(0, dotIndex);
  const workerSlug = normalized.slice(dotIndex + 1);
  if (!workerSlug) return null;

  const parent = classify(parentId);
  if (parent.kind !== "stage") return null;

  return {
    parentId,
    workerId: normalized,
    workerLabel: prettyLabel(workerSlug),
  };
}

export function useAgentStates(events: RunEvent[]): AgentStatesResult {
  return useMemo(() => {
    // Discover nodes by kind, deduplicated by id.
    const discovered = new Map<string, AgentNodeData>();
    const tracked = new Map<string, AgentNodeData>();
    let activeId: string | null = null;
    let runFailed = false;
    let runCompleted = false;
    let latestVerdict: AgentStatesResult["latestVerdict"] = null;
    /** Order in which stage ids were first observed. */
    const stageOrder: string[] = [];

    const ensure = (
      id: string,
      label: string,
      kind: AgentNodeData["kind"],
      stageIndex?: number,
    ) => {
      let node = discovered.get(id);
      if (!node) {
        node = emptyNode(id, label, kind, stageIndex);
        discovered.set(id, node);
        tracked.set(id, node);
        if (kind === "stage" && !stageOrder.includes(id)) stageOrder.push(id);
      }
      return node;
    };

    const ensureChild = (parentId: string, childId: string, label: string) => {
      const parentMeta = classify(parentId);
      const parent = ensure(
        parentMeta.id,
        parentMeta.label,
        parentMeta.kind === "stage" ? "stage" : "stage",
        parentMeta.stageIndex,
      );

      if (!parent.children) parent.children = [];

      let child = tracked.get(childId);
      if (!child) {
        child = emptyNode(childId, label, "worker");
        parent.children.push(child);
        tracked.set(childId, child);
      }

      return child;
    };

    const settleNode = (id: string | null) => {
      if (!id) return;

      const node = tracked.get(id);
      if (node && node.state === "working") {
        node.state = "completed";
      }

      const workerMeta = parseWorkerAgent(id);
      if (!workerMeta) return;

      const parent = discovered.get(workerMeta.parentId);
      if (parent && parent.state === "working") {
        parent.state = "completed";
      }
    };

    for (const evt of events) {
      const workerMeta = parseWorkerAgent(evt.agent);
      const meta = classify(evt.agent);
      // Reviewer events don't get a node — they decorate the target stage.
      if (meta.kind === "reviewer" || meta.kind === "other") {
        if (evt.type === "gate_verdict") {
          const payload = evt.payload as {
            stage?: string;
            verdict?: string;
            attempt?: number;
          };
          if (payload.stage) {
            const sm = classify(payload.stage);
            const kind: AgentNodeData["kind"] =
              sm.kind === "stage" ||
              sm.kind === "framing" ||
              sm.kind === "synthesis" ||
              sm.kind === "audit" ||
              sm.kind === "placeholder"
                ? sm.kind
                : "stage";
            const node = ensure(sm.id, sm.label, kind, sm.stageIndex);
            node.attempt = Math.max(node.attempt, payload.attempt ?? node.attempt);
            node.eventCount += 1;
            node.lastTs = evt.ts;
            const verdict = payload.verdict ?? "";
            if (verdict === "advance") {
              node.state = "completed";
              node.reiterating = false;
              activeId = null;
            } else if (verdict === "reiterate") {
              node.state = "working";
              node.reiterating = true;
              activeId = node.id;
            } else if (verdict === "halt" || verdict === "fail") {
              node.state = "failed";
              node.reiterating = false;
            }
            latestVerdict = {
              stage: payload.stage,
              verdict,
              attempt: payload.attempt ?? node.attempt,
            };
          }
        }
        continue;
      }

      // Lifecycle events with no agent slot fall through to system.
      const node = workerMeta
        ? ensureChild(workerMeta.parentId, workerMeta.workerId, workerMeta.workerLabel)
        : ensure(meta.id, meta.label, meta.kind, meta.stageIndex);
      const parentNode = workerMeta
        ? discovered.get(workerMeta.parentId) ??
          ensure(meta.id.slice(0, meta.id.indexOf(".")), meta.label, "stage")
        : null;
      node.eventCount += 1;
      node.lastTs = evt.ts;
      if (parentNode) {
        parentNode.eventCount += 1;
        parentNode.lastTs = evt.ts;
      }

      if (evt.type === "agent_message") {
        // Mark previous active node as completed if a different node is now talking.
        if (activeId && activeId !== node.id) {
          settleNode(activeId);
        }
        node.state = "working";
        node.reiterating = false;
        if (parentNode) {
          parentNode.state = "working";
          parentNode.reiterating = false;
        }
        const text = (evt.payload as { text?: string }).text;
        if (typeof text === "string" && text.trim().length > 0) {
          node.lastMessage = text;
        }
        activeId = node.id;
      } else if (evt.type === "artifact_update") {
        const path = (evt.payload as { path?: string }).path;
        if (typeof path === "string" && !node.artifacts.includes(path)) {
          node.artifacts.push(path);
        }
        // Don't downgrade an already-completed stage.
        if (node.state === "idle") node.state = "working";
        if (parentNode && parentNode.state === "idle") parentNode.state = "working";
      }
    }

    for (const evt of events) {
      if (evt.type === "run_failed" || evt.type === "system.run_failed") {
        runFailed = true;
      }
      if (evt.type === "run_completed") runCompleted = true;
    }

    if (runFailed && activeId) {
      const node = tracked.get(activeId);
      if (node) node.state = "failed";
      activeId = null;
    }
    if (runCompleted) {
      for (const node of tracked.values()) {
        if (node.state === "working") node.state = "completed";
      }
      activeId = null;
    }

    // Compose final ordered node list.
    // Strategy: build canonical skeleton, then merge discovered nodes.
    let nodes: AgentNodeData[];
    if (discovered.size === 0) {
      // No events yet — show fallback shape so the graph isn't empty.
      nodes = FALLBACK_NODES.map((n) => ({ ...n, artifacts: [...n.artifacts] }));
    } else if (discovered.has("ma.placeholder") && discovered.size === 1) {
      // Special case: M&A placeholder run.
      nodes = [discovered.get("ma.placeholder")!];
    } else {
      const ordered: AgentNodeData[] = [];
      const framing =
        discovered.get("framing") ?? emptyNode("framing", "Frame", "framing");
      ordered.push(framing);

      // Stage nodes — sorted by stageIndex (preferred) else first-observed order.
      const stageNodes = stageOrder
        .map((id) => discovered.get(id)!)
        .filter(Boolean)
        .sort((a, b) => (a.stageIndex ?? 99) - (b.stageIndex ?? 99));

      // Pad to expected 5 stages so the layout stays stable.
      const seenIdx = new Set(stageNodes.map((n) => n.stageIndex));
      for (let i = 1; i <= 5; i++) {
        if (!seenIdx.has(i)) {
          stageNodes.push(emptyNode(`stage${i}`, `Stage ${i}`, "stage", i));
        }
      }
      stageNodes.sort((a, b) => (a.stageIndex ?? 99) - (b.stageIndex ?? 99));
      ordered.push(...stageNodes);

      ordered.push(
        discovered.get("synthesis") ??
          emptyNode("synthesis", "Synthesize", "synthesis"),
      );
      ordered.push(discovered.get("audit") ?? emptyNode("audit", "Audit", "audit"));
      nodes = ordered;
    }

    // Build edges sequentially.
    const edges: AgentEdgeData[] = [];
    for (let i = 0; i < nodes.length - 1; i++) {
      const from = nodes[i]!;
      const to = nodes[i + 1]!;
      edges.push({
        from: from.id,
        to: to.id,
        active: to.state === "working",
        done:
          to.state === "completed" ||
          (from.state === "completed" && to.state !== "idle"),
        loop: false,
        kind: "flow",
      });
    }

    // ── Reviewer as its own node ──
    // Discover by counting gate_verdict events; surface a parallel
    // "Reviewer" node connected by a review-band to each stage so
    // the visual makes the iteration loop explicit.
    const verdictEvents = events.filter(
      (e) => e.type === "gate_verdict" && (e.agent === "reviewer" || e.agent === "review"),
    );
    const stageNodesOnly = nodes.filter((n) => n.kind === "stage");
    if (verdictEvents.length > 0 && stageNodesOnly.length > 0) {
      const reviewerNode: AgentNodeData = emptyNode("reviewer", "Reviewer", "reviewer");
      reviewerNode.eventCount = verdictEvents.length;
      reviewerNode.lastTs = verdictEvents[verdictEvents.length - 1]!.ts;
      // Reviewer state mirrors the latest verdict.
      if (latestVerdict?.verdict === "reiterate") reviewerNode.state = "working";
      else if (latestVerdict?.verdict === "advance") reviewerNode.state = "completed";
      else if (latestVerdict?.verdict === "halt" || latestVerdict?.verdict === "fail")
        reviewerNode.state = "failed";
      else reviewerNode.state = "completed";
      reviewerNode.attempt = latestVerdict?.attempt ?? 1;
      if (latestVerdict)
        reviewerNode.lastMessage = `${latestVerdict.stage} → ${latestVerdict.verdict}`;
      reviewerNode.reiterating = latestVerdict?.verdict === "reiterate";
      nodes.push(reviewerNode);

      // Review-band edges: each stage that produced a verdict ↔ reviewer.
      const stagesWithVerdicts = new Set(verdictEvents.map((e) => (e.payload as { stage?: string }).stage ?? ""));
      for (const stage of stageNodesOnly) {
        if (!stagesWithVerdicts.has(stage.id)) continue;
        edges.push({
          from: stage.id,
          to: "reviewer",
          active: latestVerdict?.stage === stage.id && latestVerdict.verdict === "reiterate",
          done: stage.state === "completed",
          loop: false,
          kind: "review",
        });
      }
    }

    // Reiterate loop: most recent reviewer reiterate goes from this stage
    // back one position.
    if (latestVerdict?.verdict === "reiterate") {
      const idx = nodes.findIndex((n) => n.id === latestVerdict!.stage);
      if (idx > 0) {
        edges.push({
          from: nodes[idx]!.id,
          to: nodes[idx - 1]!.id,
          active: true,
          done: false,
          loop: true,
          kind: "flow",
        });
      }
    }

    return { nodes, edges, activeId, latestVerdict };
  }, [events]);
}
