"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowRight,
  BarChart3,
  CircleDollarSign,
  FileText,
  Landmark,
  Loader2,
  Paperclip,
  Sparkles,
  Target,
  X,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { createRun, deleteDocument, getTasks, uploadDocument } from "@/lib/api";
import type { DocumentInfo, TaskTypeInfo } from "@/lib/types";
import { cn } from "@/lib/utils";

/* ────────────────────────────────────────────────────────────────── */
/* Helpers                                                           */
/* ────────────────────────────────────────────────────────────────── */

function errorMessage(err: unknown): string {
  if (err instanceof Error) return err.message;
  return String(err);
}

const DEFAULT_TASK: TaskTypeInfo = {
  slug: "market_entry",
  name: "Market Entry",
  description: "Assess market attractiveness, competitors, entry motion, and risks.",
  enabled: true,
};

const FALLBACK_TASKS: TaskTypeInfo[] = [
  DEFAULT_TASK,
  {
    slug: "profitability",
    name: "Profitability",
    description: "Diagnose margin pressure across revenue, cost, segment, and levers.",
    enabled: true,
  },
  {
    slug: "pricing",
    name: "Pricing",
    description: "Set or reset price using cost, customer value, competition, and rollout logic.",
    enabled: true,
  },
  {
    slug: "ma",
    name: "M&A",
    description: "Frame a deal screen, diligence themes, synergies, and risk watchouts.",
    enabled: false,
  },
];

const EXAMPLES: Record<string, string> = {
  market_entry:
    "Assess whether a US B2B payroll SaaS company should enter Germany in 2027, including TAM, buyer segments, competitor map, route-to-market, regulatory constraints, and a 90-day validation plan.",
  profitability:
    "Diagnose why a mid-market D2C apparel brand's EBITDA margin fell from 14% to 8% over four quarters, identify the largest drivers, and recommend the first five margin actions.",
  pricing:
    "Recommend a pricing model and launch price for an AI compliance monitoring product sold to enterprise fintech teams, including tiers, packaging, competitor references, and rollout risks.",
  ma: "Evaluate a potential acquisition of a regional managed IT services provider, including strategic fit, diligence priorities, synergy hypotheses, valuation guardrails, and integration risks.",
};

const TASK_META: Record<string, { icon: LucideIcon; color: string }> = {
  market_entry: { icon: Target, color: "hsl(200 85% 55%)" },
  profitability: { icon: BarChart3, color: "hsl(152 65% 48%)" },
  pricing: { icon: CircleDollarSign, color: "hsl(40 90% 55%)" },
  ma: { icon: Landmark, color: "hsl(265 60% 60%)" },
};

function formatBytes(size: number): string {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${Math.round(size / 1024)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

/* ────────────────────────────────────────────────────────────────── */
/* Component                                                         */
/* ────────────────────────────────────────────────────────────────── */

export default function Home() {
  const router = useRouter();
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [goal, setGoal] = useState("");
  const [tasks, setTasks] = useState<TaskTypeInfo[]>(FALLBACK_TASKS);
  const [selectedTask, setSelectedTask] = useState("market_entry");
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [loadingTasks, setLoadingTasks] = useState(true);
  const [uploadingDocuments, setUploadingDocuments] = useState(false);
  const [starting, setStarting] = useState(false);

  // Sync tasks from backend.
  useEffect(() => {
    let active = true;
    getTasks()
      .then((catalog) => {
        if (!active || catalog.length === 0) return;
        setTasks(catalog);
        const firstEnabled = catalog.find((task) => task.enabled);
        if (firstEnabled) setSelectedTask(firstEnabled.slug);
      })
      .catch(() => {
        toast.message("Using local task catalog", {
          description: "Start the backend to load live task availability.",
        });
      })
      .finally(() => {
        if (active) setLoadingTasks(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const selected = useMemo(
    () => tasks.find((task) => task.slug === selectedTask) ?? tasks[0] ?? DEFAULT_TASK,
    [selectedTask, tasks],
  );

  const wordCount = goal.trim().length === 0 ? 0 : goal.trim().split(/\s+/).length;
  const canStart = wordCount >= 3 && selected?.enabled;

  // ── File upload ──
  const uploadFiles = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setUploadingDocuments(true);
    try {
      const uploaded = await Promise.all(Array.from(files).map((file) => uploadDocument(file)));
      setDocuments((current) => [...current, ...uploaded]);
      toast.success(uploaded.length === 1 ? "Document uploaded" : `${uploaded.length} documents uploaded`);
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setUploadingDocuments(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const removeDocument = async (documentId: string) => {
    const doc = documents.find((item) => item.id === documentId);
    setDocuments((current) => current.filter((item) => item.id !== documentId));
    try {
      await deleteDocument(documentId);
    } catch (err) {
      if (doc) setDocuments((current) => [...current, doc]);
      toast.error(errorMessage(err));
    }
  };

  // ── Start run ──
  const start = async () => {
    if (!canStart) return;
    setStarting(true);
    try {
      const created = await createRun({
        task_type: selected.slug,
        goal: goal.trim(),
        document_ids: documents.map((d) => d.id),
      });
      toast.success(`${selected.name} run created`);
      router.push(`/runs/${created.run_id}`);
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setStarting(false);
    }
  };

  // Auto-resize textarea.
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.max(56, Math.min(el.scrollHeight, 240))}px`;
  }, [goal]);

  return (
    <main className="landing-gradient relative flex min-h-screen flex-col items-center justify-center overflow-hidden px-4 py-12">
      {/* Subtle grid backdrop */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-[0.04]"
        style={{
          backgroundImage:
            "linear-gradient(to right, currentColor 1px, transparent 1px), linear-gradient(to bottom, currentColor 1px, transparent 1px)",
          backgroundSize: "40px 40px",
          color: "hsl(220 10% 30%)",
          maskImage: "radial-gradient(ellipse at center, black 30%, transparent 75%)",
        }}
      />

      {/* ── Settings link (top-right corner) ── */}
      <div className="fixed top-5 right-6 z-20">
        <Button
          variant="ghost"
          size="sm"
          className="text-stone-500 hover:text-stone-800"
          onClick={() => router.push("/settings")}
        >
          Settings
        </Button>
      </div>

      {/* ── Hero block ── */}
      <div className="animate-fade-in-up relative z-10 w-full max-w-2xl space-y-8">
        {/* Brand mark */}
        <div className="flex flex-col items-center gap-3">
          <div className="flex size-12 items-center justify-center rounded-xl bg-stone-950 text-white shadow-lg">
            <Sparkles className="size-5" />
          </div>
          <div className="text-center">
            <h1 className="text-3xl font-semibold tracking-tight text-stone-950 sm:text-4xl">
              Consulting Research Agent
            </h1>
            <p className="mt-2 text-sm text-stone-500">
              Describe your research goal. The agent handles the rest.
            </p>
          </div>
        </div>

        {/* ── Intent input area ── */}
        <div className="group relative">
          {/* Main input card */}
          <div className="overflow-hidden rounded-2xl border border-stone-200/80 bg-white shadow-lg shadow-stone-200/40 transition-shadow focus-within:shadow-xl focus-within:shadow-stone-300/30">
            <textarea
              ref={textareaRef}
              id="goal-input"
              value={goal}
              onChange={(e) => setGoal(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey && canStart) {
                  e.preventDefault();
                  void start();
                }
              }}
              placeholder="Example: Assess feasibility of entering Germany's B2B payroll market…"
              rows={1}
              className="w-full resize-none border-0 bg-transparent px-5 pt-5 pb-3 text-[15px] leading-relaxed text-stone-900 placeholder:text-stone-400 focus:ring-0 focus:outline-none"
            />

            {/* Bottom toolbar */}
            <div className="flex items-center justify-between border-t border-stone-100 px-4 py-2.5">
              <div className="flex items-center gap-2">
                {/* Attach button */}
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={uploadingDocuments}
                  className="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs text-stone-500 transition hover:bg-stone-100 hover:text-stone-700 disabled:opacity-50"
                >
                  {uploadingDocuments ? (
                    <Loader2 className="size-3.5 animate-spin" />
                  ) : (
                    <Paperclip className="size-3.5" />
                  )}
                  Attach
                </button>

                {/* Use example */}
                <button
                  type="button"
                  onClick={() => setGoal(EXAMPLES[selected.slug] ?? EXAMPLES.market_entry ?? "")}
                  className="rounded-lg px-2.5 py-1.5 text-xs text-stone-500 transition hover:bg-stone-100 hover:text-stone-700"
                >
                  Use example
                </button>

                {/* Word count */}
                <span className="text-xs tabular-nums text-stone-400">
                  {wordCount} word{wordCount !== 1 ? "s" : ""}
                </span>
              </div>

              {/* Start button */}
              <Button
                size="sm"
                onClick={() => void start()}
                disabled={!canStart || starting}
                className="h-8 gap-1.5 rounded-lg px-4 text-xs"
              >
                {starting ? (
                  <Loader2 className="size-3.5 animate-spin" />
                ) : (
                  <ArrowRight className="size-3.5" />
                )}
                {starting ? "Starting…" : "Start run"}
              </Button>
            </div>
          </div>

          {/* Hidden file input */}
          <input
            ref={fileInputRef}
            type="file"
            multiple
            className="hidden"
            accept=".pdf,.txt,.md,.doc,.docx,.ppt,.pptx,.xls,.xlsx,.csv,text/*,application/pdf"
            onChange={(event) => void uploadFiles(event.target.files)}
          />
        </div>

        {/* ── Uploaded documents (chips) ── */}
        {documents.length > 0 && (
          <div className="animate-fade-in-up flex flex-wrap gap-2">
            {documents.map((doc) => (
              <div
                key={doc.id}
                className="flex items-center gap-2 rounded-lg border border-stone-200 bg-white px-3 py-1.5 text-xs shadow-sm"
              >
                <FileText className="size-3.5 text-stone-400" />
                <span className="max-w-[120px] truncate font-medium text-stone-700">
                  {doc.filename}
                </span>
                <span className="text-stone-400">{formatBytes(doc.size)}</span>
                <button
                  type="button"
                  onClick={() => void removeDocument(doc.id)}
                  className="rounded-full p-0.5 text-stone-400 transition hover:bg-stone-100 hover:text-stone-600"
                >
                  <X className="size-3" />
                </button>
              </div>
            ))}
          </div>
        )}

        {/* ── Task type selector (chip row) ── */}
        <div className="space-y-3">
          <p className="text-center text-xs font-medium tracking-wide text-stone-400 uppercase">
            Consulting type
          </p>
          <div className="flex flex-wrap items-center justify-center gap-2">
            {tasks.map((task) => {
              const meta = TASK_META[task.slug];
              const Icon = meta?.icon ?? Target;
              const color = meta?.color ?? "hsl(200 80% 55%)";
              const active = selectedTask === task.slug;
              return (
                <button
                  key={task.slug}
                  type="button"
                  disabled={!task.enabled}
                  onClick={() => setSelectedTask(task.slug)}
                  className={cn(
                    "flex items-center gap-2 rounded-full border px-4 py-2 text-sm transition",
                    "focus-visible:ring-2 focus-visible:ring-stone-400 focus-visible:outline-none",
                    "disabled:cursor-not-allowed disabled:opacity-40",
                    active
                      ? "border-stone-900 bg-stone-950 text-white shadow-md"
                      : "border-stone-200 bg-white text-stone-600 hover:border-stone-300 hover:bg-stone-50 shadow-sm",
                  )}
                >
                  <Icon
                    className="size-4"
                    style={{ color: active ? "white" : color }}
                  />
                  <span className="font-medium">{task.name}</span>
                  {!task.enabled && (
                    <Badge variant="secondary" className="ml-1 rounded-full px-1.5 py-0 text-[10px]">
                      Soon
                    </Badge>
                  )}
                </button>
              );
            })}
            {loadingTasks && <Loader2 className="size-4 animate-spin text-stone-400" />}
          </div>
        </div>

        {/* ── Pipeline preview ── */}
        <div className="flex items-center justify-center gap-1.5 text-[11px] font-medium text-stone-400">
          {["Frame", "Research", "Review", "Synthesize", "Audit"].map((step, i) => (
            <span key={step} className="flex items-center gap-1.5">
              {i > 0 && <span className="text-stone-300">→</span>}
              <span className="rounded-md border border-stone-200/70 bg-white/60 px-2 py-1 shadow-sm">
                {step}
              </span>
            </span>
          ))}
        </div>
      </div>
    </main>
  );
}
