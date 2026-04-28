"use client";

/**
 * AgentGraph — SVG + HTML orchestration graph (M7.1 redux).
 *
 * Renders the discovered pipeline (one node per agent + framing /
 * stages / synthesis / audit) with:
 *
 *   - state colors driven by `useAgentStates`
 *   - hover popover showing the latest agent message + artifacts
 *   - iteration badge when reviewer asked for reiterate (attempt > 1)
 *   - animated edges with travelling dots when downstream node is working
 *   - reiterate loop arc when reviewer most recently sent stage back
 *
 * The visualization is purely derived from the SSE event stream — no
 * task-type knowledge required. The hook handles M&A placeholder,
 * pricing/profitability/market_entry stage1..stage5, and any future
 * profile that follows the `stage{N}_{slug}` convention.
 */

import { useMemo, useRef, useState } from "react";
import {
  Check,
  CircleDashed,
  FileText,
  Loader2,
  Search,
  ShieldCheck,
  Shield,
  Sparkles,
  Target,
  X,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import type { RunEvent } from "@/lib/sse";
import { useAgentStates, type AgentNodeData } from "@/lib/useAgentStates";
import { cn } from "@/lib/utils";

interface AgentGraphProps {
  events: RunEvent[];
  className?: string;
}

interface NodeLayout extends AgentNodeData {
  x: number;
  y: number;
}

const NODE_SIZE = 56; // diameter
const ROW_GAP = 36; // vertical reserve for label + state below

// Lane positions (percentages within the SVG viewBox).
const LANE_TOP_Y = 22;
const LANE_MID_Y = 52;
const LANE_BOT_Y = 84;

const SPINE_FRAME_X = 6;
const SPINE_SYNTH_X = 80;
const SPINE_AUDIT_X = 94;
const STAGE_START_X = 20;
const STAGE_END_X = 66;

const KIND_ICON: Record<AgentNodeData["kind"], LucideIcon> = {
  framing: Target,
  stage: Search,
  worker: Search,
  reviewer: ShieldCheck,
  synthesis: Sparkles,
  audit: Shield,
  placeholder: FileText,
};

function stateClasses(state: AgentNodeData["state"]) {
  switch (state) {
    case "working":
      return {
        ring: "ring-sky-400/60",
        bg: "bg-gradient-to-br from-sky-500/30 to-sky-600/10",
        text: "text-sky-200",
        border: "border-sky-400/70",
        glow: "shadow-[0_0_24px_-2px_rgba(56,189,248,0.55)]",
        label: "text-sky-300",
      };
    case "completed":
      return {
        ring: "ring-emerald-500/40",
        bg: "bg-gradient-to-br from-emerald-500/25 to-emerald-700/10",
        text: "text-emerald-200",
        border: "border-emerald-500/50",
        glow: "shadow-[0_0_18px_-4px_rgba(16,185,129,0.45)]",
        label: "text-emerald-300/90",
      };
    case "failed":
      return {
        ring: "ring-rose-500/50",
        bg: "bg-gradient-to-br from-rose-500/25 to-rose-700/10",
        text: "text-rose-200",
        border: "border-rose-500/60",
        glow: "shadow-[0_0_18px_-4px_rgba(244,63,94,0.45)]",
        label: "text-rose-300/90",
      };
    default:
      return {
        ring: "ring-white/5",
        bg: "bg-white/[0.025]",
        text: "text-stone-500",
        border: "border-white/10 border-dashed",
        glow: "",
        label: "text-stone-500",
      };
  }
}

function StateGlyph({
  state,
  kind,
}: {
  state: AgentNodeData["state"];
  kind: AgentNodeData["kind"];
}) {
  if (state === "working") return <Loader2 className="size-5 animate-spin" />;
  if (state === "completed") return <Check className="size-5" strokeWidth={3} />;
  if (state === "failed") return <X className="size-5" strokeWidth={3} />;
  const Icon = KIND_ICON[kind] ?? CircleDashed;
  return <Icon className="size-5" />;
}

function stateLabel(node: AgentNodeData): string {
  if (node.state === "failed") return "failed";
  if (node.state === "completed") return "done";
  if (node.state === "working") return node.reiterating ? "reiterating" : "working";
  return "idle";
}

export function AgentGraph({ events, className }: AgentGraphProps) {
  const { nodes, edges, latestVerdict } = useAgentStates(events);

  // Lay nodes across three horizontal lanes:
  //   top    — framing / synthesis / audit (the spine)
  //   middle — stages 1..N (the iterate loop)
  //   bottom — reviewer (gates each stage)
  const layout = useMemo<NodeLayout[]>(() => {
    if (nodes.length === 0) return [];
    const stages = nodes.filter((n) => n.kind === "stage");
    const stageCount = Math.max(1, stages.length);
    const stageX = (idx: number) => {
      if (stageCount === 1) return (STAGE_START_X + STAGE_END_X) / 2;
      const t = idx / (stageCount - 1);
      return STAGE_START_X + t * (STAGE_END_X - STAGE_START_X);
    };

    return nodes.map((n) => {
      if (n.kind === "framing") return { ...n, x: SPINE_FRAME_X, y: LANE_TOP_Y };
      if (n.kind === "synthesis") return { ...n, x: SPINE_SYNTH_X, y: LANE_TOP_Y };
      if (n.kind === "audit") return { ...n, x: SPINE_AUDIT_X, y: LANE_TOP_Y };
      if (n.kind === "reviewer")
        return { ...n, x: (STAGE_START_X + STAGE_END_X) / 2, y: LANE_BOT_Y };
      if (n.kind === "placeholder") return { ...n, x: 50, y: LANE_MID_Y };
      // Stage
      const idx = stages.findIndex((s) => s.id === n.id);
      return { ...n, x: stageX(Math.max(0, idx)), y: LANE_MID_Y };
    });
  }, [nodes]);

  return (
    <div className={cn("relative h-full w-full", className)}>
      {/* Lane labels (left edge) */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-y-0 left-2 z-0 flex flex-col justify-around text-[9px] font-semibold tracking-wider text-stone-600 uppercase"
      >
        <span>Frame</span>
        <span>Research</span>
        <span>Review</span>
      </div>

      {/* Subtle lane backgrounds */}
      <div aria-hidden className="pointer-events-none absolute inset-0 z-0">
        <div
          className="absolute inset-x-0 rounded-md bg-white/[0.015]"
          style={{ top: `${LANE_MID_Y - 12}%`, height: "24%" }}
        />
      </div>

      {/* Edge layer */}
      <svg
        className="absolute inset-0 z-10 h-full w-full"
        viewBox="0 0 100 100"
        preserveAspectRatio="none"
      >
        <defs>
          <marker
            id="arrow-idle"
            viewBox="0 0 10 10"
            refX="9"
            refY="5"
            markerWidth="4"
            markerHeight="4"
            orient="auto"
          >
            <path d="M 0 0 L 10 5 L 0 10 z" fill="hsl(220 12% 32%)" />
          </marker>
          <marker
            id="arrow-active"
            viewBox="0 0 10 10"
            refX="9"
            refY="5"
            markerWidth="4"
            markerHeight="4"
            orient="auto"
          >
            <path d="M 0 0 L 10 5 L 0 10 z" fill="hsl(200 90% 60%)" />
          </marker>
          <marker
            id="arrow-done"
            viewBox="0 0 10 10"
            refX="9"
            refY="5"
            markerWidth="4"
            markerHeight="4"
            orient="auto"
          >
            <path d="M 0 0 L 10 5 L 0 10 z" fill="hsl(152 55% 50%)" />
          </marker>
          <marker
            id="arrow-loop"
            viewBox="0 0 10 10"
            refX="9"
            refY="5"
            markerWidth="4"
            markerHeight="4"
            orient="auto"
          >
            <path d="M 0 0 L 10 5 L 0 10 z" fill="hsl(35 90% 60%)" />
          </marker>
        </defs>

        {edges.map((edge, i) => {
          const fromNode = layout.find((n) => n.id === edge.from);
          const toNode = layout.find((n) => n.id === edge.to);
          if (!fromNode || !toNode) return null;

          // ── Review band: subtle vertical link from stage down to reviewer ──
          if (edge.kind === "review") {
            const x = fromNode.x;
            const y1 = fromNode.y + 5;
            const y2 = toNode.y - 5;
            // Curved path bowing slightly outward.
            const path = `M ${x} ${y1} L ${x} ${y2}`;
            return (
              <line
                key={`review-${i}`}
                x1={x}
                y1={y1}
                x2={x}
                y2={y2}
                stroke={
                  edge.active
                    ? "hsl(35 90% 60% / 0.7)"
                    : edge.done
                      ? "hsl(152 55% 50% / 0.25)"
                      : "hsl(220 12% 30% / 0.45)"
                }
                strokeWidth="0.18"
                strokeDasharray="0.5 0.6"
                strokeLinecap="round"
                vectorEffect="non-scaling-stroke"
              >
                <title>{path}</title>
              </line>
            );
          }

          // ── Reiterate loop: curved arc above the stage row ──
          if (edge.loop) {
            const x1 = fromNode.x;
            const x2 = toNode.x;
            const midX = (x1 + x2) / 2;
            const arcY = fromNode.y - 12; // arc above the lane
            const path = `M ${x1} ${fromNode.y - 4} Q ${midX} ${arcY} ${x2} ${toNode.y - 4}`;
            return (
              <g key={`loop-${i}`}>
                <path
                  d={path}
                  fill="none"
                  stroke="hsl(35 90% 60%)"
                  strokeWidth="0.4"
                  strokeDasharray="0.9 0.7"
                  markerEnd="url(#arrow-loop)"
                  className="animate-pulse"
                />
              </g>
            );
          }

          // ── Main flow edge ──
          // Inset endpoints so arrows don't dive under node circles.
          const dx = toNode.x - fromNode.x;
          const dy = toNode.y - fromNode.y;
          const len = Math.sqrt(dx * dx + dy * dy) || 1;
          const inset = 3.4;
          const ux = dx / len;
          const uy = dy / len;
          const x1 = fromNode.x + ux * inset;
          const y1 = fromNode.y + uy * inset;
          const x2 = toNode.x - ux * inset;
          const y2 = toNode.y - uy * inset;

          const color = edge.active
            ? "hsl(200 90% 60%)"
            : edge.done
              ? "hsl(152 55% 50%)"
              : "hsl(220 12% 30%)";
          const marker = edge.active
            ? "url(#arrow-active)"
            : edge.done
              ? "url(#arrow-done)"
              : "url(#arrow-idle)";

          // Lane changes (different y) get a smooth curve instead of a straight line.
          const sameLane = Math.abs(dy) < 0.5;
          const path = sameLane
            ? `M ${x1} ${y1} L ${x2} ${y2}`
            : `M ${x1} ${y1} C ${x1 + dx * 0.45} ${y1}, ${x2 - dx * 0.45} ${y2}, ${x2} ${y2}`;

          return (
            <g key={i}>
              <path
                d={path}
                fill="none"
                stroke={color}
                strokeWidth={edge.active ? "0.45" : "0.28"}
                strokeDasharray={edge.active || edge.done ? undefined : "0.9 0.7"}
                strokeLinecap="round"
                markerEnd={marker}
                vectorEffect="non-scaling-stroke"
              />
              {edge.active && (
                <circle r="0.6" fill="hsl(200 90% 75%)">
                  <animateMotion dur="1.6s" repeatCount="indefinite" path={path} />
                </circle>
              )}
            </g>
          );
        })}
      </svg>

      {/* Node layer */}
      <div className="relative z-20 h-full w-full" style={{ paddingBottom: ROW_GAP }}>
        {layout.map((node) => (
          <Node key={node.id} node={node} />
        ))}
      </div>

      {/* Reiterate banner */}
      {latestVerdict?.verdict === "reiterate" && (
        <div className="absolute right-3 top-3 z-30 flex items-center gap-1.5 rounded-full bg-amber-500/15 px-3 py-1 text-[10px] font-medium tracking-wide text-amber-300 ring-1 ring-amber-500/30">
          <span className="size-1.5 animate-pulse rounded-full bg-amber-400" />
          Reviewer requested reiterate · attempt {latestVerdict.attempt}
        </div>
      )}
    </div>
  );
}

function Node({ node }: { node: NodeLayout }) {
  const [open, setOpen] = useState(false);
  const [childrenOpen, setChildrenOpen] = useState(true);
  const ref = useRef<HTMLDivElement>(null);
  const cls = stateClasses(node.state);
  const hasChildren = (node.children?.length ?? 0) > 0;

  return (
    <div
      ref={ref}
      className="absolute"
      data-agent-node={node.id}
      style={{
        left: `${node.x}%`,
        top: `${node.y}%`,
        transform: "translate(-50%, -50%)",
      }}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
    >
      {/* Animated outer ping for working state */}
      {node.state === "working" && (
        <span
          aria-hidden
          className="absolute inset-0 -m-2 animate-ping rounded-full bg-sky-400/20"
          style={{ width: NODE_SIZE + 16, height: NODE_SIZE + 16 }}
        />
      )}

      {/* Main circle */}
      <button
        type="button"
        tabIndex={0}
        className={cn(
          "relative flex items-center justify-center rounded-full border ring-1 transition",
          cls.bg,
          cls.text,
          cls.border,
          cls.ring,
          cls.glow,
        )}
        style={{ width: NODE_SIZE, height: NODE_SIZE }}
        aria-label={`${node.label} — ${stateLabel(node)}`}
      >
        <StateGlyph state={node.state} kind={node.kind} />

        {/* Attempt badge */}
        {node.attempt > 1 && (
          <span
            className="absolute -right-1 -top-1 inline-flex h-4 min-w-[16px] items-center justify-center rounded-full border border-stone-950 bg-amber-400 px-1 text-[9px] font-bold text-stone-950"
            title={`Attempt ${node.attempt}`}
          >
            ×{node.attempt}
          </span>
        )}

        {/* Stage index pill */}
        {node.kind === "stage" && node.stageIndex !== undefined && (
          <span className="absolute -left-1 -top-1 inline-flex size-4 items-center justify-center rounded-full border border-stone-950 bg-stone-900 text-[9px] font-semibold text-stone-300">
            {node.stageIndex}
          </span>
        )}
      </button>

      {hasChildren && (
        <div className="absolute left-1/2 top-full z-20 mt-13 flex min-w-[140px] -translate-x-1/2 flex-col items-center gap-1.5">
          <button
            type="button"
            className="rounded-full border border-white/10 bg-stone-950/85 px-2 py-0.5 text-[9px] font-semibold tracking-wide text-stone-300 transition hover:border-white/20 hover:text-stone-100"
            aria-label={childrenOpen ? `Hide workers for ${node.label}` : `Show workers for ${node.label}`}
            onClick={() => setChildrenOpen((value) => !value)}
          >
            {childrenOpen ? "Hide workers" : "Show workers"}
          </button>

          {childrenOpen && (
            <div className="flex max-w-[180px] flex-wrap items-center justify-center gap-1.5 rounded-2xl border border-white/8 bg-stone-950/80 px-2 py-2 shadow-xl backdrop-blur-sm">
              {node.children!.map((child) => {
                const childCls = stateClasses(child.state);

                return (
                  <div
                    key={child.id}
                    className={cn(
                      "inline-flex items-center gap-1 rounded-full border px-2 py-1 text-[10px] leading-none shadow-sm",
                      childCls.bg,
                      childCls.border,
                      childCls.text,
                    )}
                    title={child.lastMessage ?? child.id}
                  >
                    <span className="truncate font-medium">{child.label}</span>
                    <span className="text-[9px] text-stone-400">{child.eventCount}</span>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Label */}
      <div className="pointer-events-none absolute left-1/2 top-full mt-2 -translate-x-1/2 text-center">
        <div
          className={cn(
            "max-w-[120px] truncate text-xs font-medium",
            node.state === "idle" ? "text-stone-400" : cls.label.replace("/90", ""),
          )}
        >
          {node.label}
        </div>
        <div className="mt-0.5 text-[10px] tracking-wide text-stone-500 capitalize">
          {stateLabel(node)}
        </div>
      </div>

      {/* Hover popover */}
      {open && (node.lastMessage || node.artifacts.length > 0 || node.eventCount > 0) && (
        <div
          role="tooltip"
          className="absolute left-1/2 z-30 mt-3 w-[280px] -translate-x-1/2 rounded-xl border border-white/10 bg-stone-950/95 p-3 text-left text-xs shadow-2xl backdrop-blur-xl"
          style={{ top: NODE_SIZE + 36 }}
        >
          <div className="mb-1.5 flex items-center justify-between gap-2">
            <span className="font-mono text-[10px] tracking-wider text-stone-500 uppercase">
              {node.id}
            </span>
            <span
              className={cn(
                "rounded-full px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wider",
                node.state === "working" && "bg-sky-500/20 text-sky-300",
                node.state === "completed" && "bg-emerald-500/20 text-emerald-300",
                node.state === "failed" && "bg-rose-500/20 text-rose-300",
                node.state === "idle" && "bg-stone-500/20 text-stone-400",
              )}
            >
              {stateLabel(node)}
            </span>
          </div>

          {node.lastMessage && (
            <p className="mb-2 line-clamp-4 leading-relaxed text-stone-200">
              {node.lastMessage}
            </p>
          )}

          {node.artifacts.length > 0 && (
            <div className="mb-2">
              <div className="mb-1 text-[9px] font-semibold tracking-wider text-stone-500 uppercase">
                Artifacts
              </div>
              <ul className="space-y-0.5">
                {node.artifacts.slice(-4).map((p) => (
                  <li
                    key={p}
                    className="truncate font-mono text-[10px] text-stone-300"
                    title={p}
                  >
                    {p}
                  </li>
                ))}
                {node.artifacts.length > 4 && (
                  <li className="text-[10px] text-stone-500">
                    +{node.artifacts.length - 4} more
                  </li>
                )}
              </ul>
            </div>
          )}

          <div className="flex items-center justify-between text-[10px] text-stone-500">
            <span>{node.eventCount} event{node.eventCount === 1 ? "" : "s"}</span>
            {node.attempt > 1 && (
              <span className="text-amber-300">attempt {node.attempt}</span>
            )}
          </div>

          {!node.lastMessage && node.artifacts.length === 0 && node.eventCount === 0 && (
            <p className="text-stone-500">Waiting for activity…</p>
          )}
        </div>
      )}
    </div>
  );
}
