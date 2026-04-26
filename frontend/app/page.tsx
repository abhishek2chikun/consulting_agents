"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowRight,
  BarChart3,
  BriefcaseBusiness,
  Check,
  CircleDollarSign,
  FileText,
  Landmark,
  Loader2,
  Settings,
  Sparkles,
  Target,
  Upload,
  X,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { createRun, deleteDocument, getTasks, uploadDocument } from "@/lib/api";
import type { DocumentInfo, TaskTypeInfo } from "@/lib/types";
import { cn } from "@/lib/utils";

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

const TASK_ACCENTS: Record<
  string,
  {
    icon: LucideIcon;
    tint: string;
    signal: string;
  }
> = {
  market_entry: {
    icon: Target,
    tint: "border-sky-200 bg-sky-50/70 text-sky-950",
    signal: "Market map",
  },
  profitability: {
    icon: BarChart3,
    tint: "border-emerald-200 bg-emerald-50/70 text-emerald-950",
    signal: "Margin tree",
  },
  pricing: {
    icon: CircleDollarSign,
    tint: "border-amber-200 bg-amber-50/70 text-amber-950",
    signal: "Price curve",
  },
  ma: {
    icon: Landmark,
    tint: "border-violet-200 bg-violet-50/70 text-violet-950",
    signal: "Deal screen",
  },
};

const DEFAULT_ACCENT = {
  icon: Target,
  tint: "border-sky-200 bg-sky-50/70 text-sky-950",
  signal: "Market map",
} satisfies {
  icon: LucideIcon;
  tint: string;
  signal: string;
};

function taskAccent(slug: string | undefined) {
  if (!slug) return DEFAULT_ACCENT;
  return TASK_ACCENTS[slug] ?? DEFAULT_ACCENT;
}

const WORKFLOW_STEPS = ["Frame", "Research", "Review", "Synthesize", "Audit"];

function formatBytes(size: number): string {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${Math.round(size / 1024)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

export default function Home() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [goal, setGoal] = useState("");
  const [tasks, setTasks] = useState<TaskTypeInfo[]>(FALLBACK_TASKS);
  const [selectedTask, setSelectedTask] = useState("market_entry");
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [loadingTasks, setLoadingTasks] = useState(true);
  const [uploadingDocuments, setUploadingDocuments] = useState(false);
  const [starting, setStarting] = useState(false);

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

  const selectedAccent = taskAccent(selected.slug);
  const SelectedIcon = selectedAccent.icon;
  const wordCount = goal.trim().length === 0 ? 0 : goal.trim().split(/\s+/).length;

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
      toast.success("Document removed");
    } catch (err) {
      if (doc) setDocuments((current) => [...current, doc]);
      toast.error(errorMessage(err));
    }
  };

  const start = async () => {
    if (goal.trim().length === 0) {
      toast.error("Brief is required");
      return;
    }
    if (!selected?.enabled) {
      toast.error("Selected consulting type is not enabled");
      return;
    }
    setStarting(true);
    try {
      const created = await createRun({
        task_type: selected.slug,
        goal: goal.trim(),
        document_ids: documents.map((document) => document.id),
      });
      toast.success(`${selected.name} run created`);
      router.push(`/runs/${created.run_id}`);
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setStarting(false);
    }
  };

  return (
    <main className="min-h-screen px-4 py-5 text-stone-950 sm:px-6 lg:px-8">
      <div className="mx-auto grid min-h-[calc(100vh-2.5rem)] max-w-7xl grid-cols-1 gap-5 lg:grid-cols-[17rem_minmax(0,1fr)]">
        <aside className="flex flex-col justify-between rounded-lg border border-black/10 bg-white/70 p-4 shadow-sm backdrop-blur">
          <div className="space-y-7">
            <div className="flex items-center gap-3">
              <div className="flex size-9 items-center justify-center rounded-md bg-stone-950 text-white">
                <BriefcaseBusiness className="size-4" />
              </div>
              <div>
                <p className="text-sm font-semibold tracking-tight">Consulting Agent</p>
                <p className="text-xs text-stone-500">Research workspace</p>
              </div>
            </div>

            <nav className="space-y-1 text-sm">
              {["New run", "Runs", "Evidence", "Settings"].map((item, index) => (
                <div
                  key={item}
                  className={cn(
                    "flex h-9 items-center gap-2 rounded-md px-2 text-stone-600",
                    index === 0 && "bg-stone-950 text-white shadow-sm",
                  )}
                >
                  {index === 3 ? <Settings className="size-4" /> : <Sparkles className="size-4" />}
                  <span>{item}</span>
                </div>
              ))}
            </nav>
          </div>

          <div className="rounded-md border border-stone-200 bg-white p-3">
            <p className="text-xs font-medium text-stone-500">Pipeline</p>
            <div className="mt-3 space-y-2">
              {WORKFLOW_STEPS.map((step, index) => (
                <div key={step} className="flex items-center gap-2 text-xs text-stone-600">
                  <span className="flex size-5 items-center justify-center rounded-full border border-stone-200 bg-stone-50 text-[10px] font-semibold">
                    {index + 1}
                  </span>
                  {step}
                </div>
              ))}
            </div>
          </div>
        </aside>

        <section className="rounded-lg border border-black/10 bg-white/78 shadow-sm backdrop-blur">
          <div className="border-b border-stone-200 px-5 py-4 sm:px-7">
            <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
              <div>
                <Badge variant="outline" className="mb-3 rounded-md border-stone-300 bg-white/60">
                  {loadingTasks ? "Syncing catalog" : "Ready"}
                </Badge>
                <h1 className="max-w-3xl text-3xl font-semibold tracking-tight sm:text-4xl">
                  Build the consulting brief, then let the agent do the legwork.
                </h1>
              </div>
              <Button
                onClick={() => void start()}
                disabled={starting || !selected?.enabled}
                className="h-10 px-4"
              >
                {starting ? <Loader2 className="size-4 animate-spin" /> : <ArrowRight className="size-4" />}
                {starting ? "Starting" : "Start run"}
              </Button>
            </div>
          </div>

          <div className="grid gap-0 lg:grid-cols-[minmax(0,1fr)_21rem]">
            <div className="space-y-7 p-5 sm:p-7">
              <div className="space-y-3">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold">Consulting type</p>
                    <p className="text-xs text-stone-500">Select the working model for this run.</p>
                  </div>
                  {loadingTasks && <Loader2 className="size-4 animate-spin text-stone-400" />}
                </div>

                <div className="grid gap-3 md:grid-cols-2">
                  {tasks.map((task) => {
                    const accent = taskAccent(task.slug);
                    const Icon = accent.icon;
                    const active = selectedTask === task.slug;

                    return (
                      <button
                        key={task.slug}
                        type="button"
                        disabled={!task.enabled}
                        onClick={() => setSelectedTask(task.slug)}
                        className={cn(
                          "group min-h-36 rounded-lg border bg-white p-4 text-left shadow-sm transition hover:-translate-y-0.5 hover:shadow-md focus-visible:ring-3 focus-visible:ring-stone-300 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-45",
                          active ? "border-stone-950 ring-2 ring-stone-950/8" : "border-stone-200",
                        )}
                      >
                        <div className="flex items-start justify-between gap-3">
                          <span
                            className={cn(
                              "flex size-9 items-center justify-center rounded-md border",
                              accent.tint,
                            )}
                          >
                            <Icon className="size-4" />
                          </span>
                          <span
                            className={cn(
                              "flex size-5 items-center justify-center rounded-full border text-white",
                              active ? "border-stone-950 bg-stone-950" : "border-stone-200 bg-white",
                            )}
                          >
                            {active && <Check className="size-3" />}
                          </span>
                        </div>
                        <div className="mt-4">
                          <div className="flex items-center gap-2">
                            <h2 className="text-base font-semibold tracking-tight">{task.name}</h2>
                            {!task.enabled && (
                              <Badge variant="secondary" className="rounded-md">
                                Soon
                              </Badge>
                            )}
                          </div>
                          <p className="mt-2 text-sm leading-5 text-stone-600">{task.description}</p>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>

              <div className="space-y-3">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
                  <div>
                    <p className="text-sm font-semibold">Brief</p>
                    <p className="text-xs text-stone-500">
                      Add scope, geography, company context, constraints, and the decision to support.
                    </p>
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => setGoal(EXAMPLES[selected.slug] ?? EXAMPLES.market_entry ?? "")}
                  >
                    Use example
                  </Button>
                </div>
                <Textarea
                  id="goal"
                  value={goal}
                  onChange={(event) => setGoal(event.target.value)}
                  placeholder="Example: Assess feasibility and GTM strategy for entering Germany's B2B payroll market, with a recommendation for whether to enter, where to play, and how to win."
                  rows={9}
                  className="min-h-56 resize-none rounded-lg border-stone-300 bg-white/80 p-4 text-[15px] leading-6 shadow-inner"
                />
              </div>

              <div className="space-y-3">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
                  <div>
                    <p className="text-sm font-semibold">Context documents</p>
                    <p className="text-xs text-stone-500">
                      Attach PDFs, notes, spreadsheets, or source material for this run.
                    </p>
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={uploadingDocuments}
                  >
                    {uploadingDocuments ? (
                      <Loader2 className="size-4 animate-spin" />
                    ) : (
                      <Upload className="size-4" />
                    )}
                    Upload
                  </Button>
                </div>

                <input
                  ref={fileInputRef}
                  type="file"
                  multiple
                  className="hidden"
                  accept=".pdf,.txt,.md,.doc,.docx,.ppt,.pptx,.xls,.xlsx,.csv,text/*,application/pdf"
                  onChange={(event) => void uploadFiles(event.target.files)}
                />

                <div
                  className={cn(
                    "rounded-lg border border-dashed border-stone-300 bg-white/70 p-4",
                    documents.length > 0 && "border-solid",
                  )}
                >
                  {documents.length === 0 ? (
                    <button
                      type="button"
                      onClick={() => fileInputRef.current?.click()}
                      className="flex min-h-24 w-full flex-col items-center justify-center gap-2 rounded-md text-center text-sm text-stone-500 transition hover:bg-stone-50 focus-visible:ring-3 focus-visible:ring-stone-300 focus-visible:outline-none"
                    >
                      {uploadingDocuments ? (
                        <Loader2 className="size-5 animate-spin" />
                      ) : (
                        <FileText className="size-5" />
                      )}
                      <span>{uploadingDocuments ? "Uploading" : "Drop in deal context"}</span>
                    </button>
                  ) : (
                    <div className="space-y-2">
                      {documents.map((document) => (
                        <div
                          key={document.id}
                          className="flex items-center justify-between gap-3 rounded-md border border-stone-200 bg-white px-3 py-2"
                        >
                          <div className="flex min-w-0 items-center gap-3">
                            <span className="flex size-8 shrink-0 items-center justify-center rounded-md bg-stone-100 text-stone-600">
                              <FileText className="size-4" />
                            </span>
                            <div className="min-w-0">
                              <p className="truncate text-sm font-medium">{document.filename}</p>
                              <p className="text-xs text-stone-500">
                                {formatBytes(document.size)} · {document.status}
                              </p>
                            </div>
                          </div>
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon-sm"
                            onClick={() => void removeDocument(document.id)}
                            aria-label={`Remove ${document.filename}`}
                          >
                            <X className="size-4" />
                          </Button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>

            <aside className="border-t border-stone-200 bg-stone-50/70 p-5 sm:p-7 lg:border-t-0 lg:border-l">
              <div className="sticky top-5 space-y-5">
                <div className="rounded-lg border border-stone-200 bg-white p-4 shadow-sm">
                  <div className="flex items-center gap-3">
                    <span
                      className={cn(
                        "flex size-10 items-center justify-center rounded-md border",
                        selectedAccent.tint,
                      )}
                    >
                      <SelectedIcon className="size-4" />
                    </span>
                    <div>
                      <p className="text-sm font-semibold">{selected?.name ?? "Consulting"}</p>
                      <p className="text-xs text-stone-500">{selectedAccent.signal}</p>
                    </div>
                  </div>

                  <dl className="mt-5 grid grid-cols-2 gap-3 text-sm">
                    <div className="rounded-md border border-stone-200 bg-stone-50 p-3">
                      <dt className="text-xs text-stone-500">Input</dt>
                      <dd className="mt-1 font-semibold">{wordCount} words</dd>
                    </div>
                    <div className="rounded-md border border-stone-200 bg-stone-50 p-3">
                      <dt className="text-xs text-stone-500">Sources</dt>
                      <dd className="mt-1 font-semibold">
                        Web + {documents.length} doc{documents.length === 1 ? "" : "s"}
                      </dd>
                    </div>
                  </dl>
                </div>

                <div className="rounded-lg border border-stone-200 bg-white p-4 shadow-sm">
                  <p className="text-sm font-semibold">Output package</p>
                  <div className="mt-4 space-y-3">
                    {["Framing questions", "Stage evidence", "Final report", "Audit notes"].map((item) => (
                      <div key={item} className="flex items-center gap-2 text-sm text-stone-700">
                        <span className="flex size-5 items-center justify-center rounded-full bg-emerald-50 text-emerald-700">
                          <Check className="size-3" />
                        </span>
                        {item}
                      </div>
                    ))}
                  </div>
                </div>

                <Button
                  onClick={() => void start()}
                  disabled={starting || !selected?.enabled}
                  className="h-11 w-full"
                >
                  {starting ? <Loader2 className="size-4 animate-spin" /> : <ArrowRight className="size-4" />}
                  {starting ? "Creating run" : "Start consulting run"}
                </Button>
              </div>
            </aside>
          </div>
        </section>
      </div>
    </main>
  );
}
