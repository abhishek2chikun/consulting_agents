"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  Download,
  FileText,
  Loader2,
  RefreshCw,
  RotateCcw,
  XCircle,
} from "lucide-react";
import { toast } from "sonner";

import { AgentGraph } from "@/components/AgentGraph";
import { AgentTrace } from "@/components/AgentTrace";
import { ChatStream } from "@/components/ChatStream";
import { QuestionnaireForm } from "@/components/QuestionnaireForm";
import { ReportView } from "@/components/ReportView";
import { SourcesSidebar } from "@/components/SourcesSidebar";
import { UsagePanel } from "@/components/UsagePanel";
import { Button } from "@/components/ui/button";
import { getRun, getRunArtifact, submitRunAnswers, cancelRun, retryRun } from "@/lib/api";
import { RUN_LIFECYCLE_EVENT_TYPES } from "@/lib/runEvents";
import { useEventStream } from "@/lib/sse";
import type { QuestionnaireSchema, RunInfoResponse } from "@/lib/types";
import { cn } from "@/lib/utils";

const QUESTIONNAIRE_PATH = "framing/questionnaire.json";
const REPORT_PATH = "final_report.md";
const TERMINAL_STATUSES = new Set(["completed", "failed", "cancelled"]);

function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

function statusStyle(status: string | undefined) {
  if (!status) return "bg-stone-500/15 text-stone-400 ring-stone-500/30";
  if (status === "completed") return "bg-emerald-500/15 text-emerald-300 ring-emerald-500/30";
  if (status === "failed") return "bg-rose-500/15 text-rose-300 ring-rose-500/30";
  if (status === "cancelled") return "bg-amber-500/15 text-amber-300 ring-amber-500/30";
  if (status === "running" || status === "in_progress") return "bg-sky-500/15 text-sky-300 ring-sky-500/30";
  if (status === "questioning") return "bg-violet-500/15 text-violet-300 ring-violet-500/30";
  return "bg-stone-500/15 text-stone-300 ring-stone-500/30";
}

function downloadTextFile(filename: string, content: string, type: string) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

function slugForFilename(value: string) {
  return value.replace(/[^a-zA-Z0-9_-]+/g, "-").replace(/^-+|-+$/g, "");
}

function titleCase(s: string) {
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function RunPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const runId = params.id;

  const [runInfo, setRunInfo] = useState<RunInfoResponse | null>(null);
  const [questionnaire, setQuestionnaire] = useState<QuestionnaireSchema | null>(null);
  const [answersSubmitted, setAnswersSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const [streamReconnectKey, setStreamReconnectKey] = useState(0);
  const [highlightedSrcId, setHighlightedSrcId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"report" | "activity">("activity");

  const { events, status: connStatus } = useEventStream(runId, streamReconnectKey);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      setRunInfo(await getRun(runId));
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [runId]);

  const loadQuestionnaire = useCallback(async () => {
    try {
      const artifact = await getRunArtifact(runId, QUESTIONNAIRE_PATH);
      setQuestionnaire(JSON.parse(artifact.content) as QuestionnaireSchema);
    } catch (err) {
      toast.error(`Could not load questionnaire: ${errorMessage(err)}`);
    }
  }, [runId]);

  const bootstrapped = useRef(false);
  useEffect(() => {
    if (bootstrapped.current) return;
    bootstrapped.current = true;
    void refresh();
    void getRunArtifact(runId, QUESTIONNAIRE_PATH)
      .then((a) => setQuestionnaire(JSON.parse(a.content) as QuestionnaireSchema))
      .catch(() => undefined);
  }, [refresh, runId]);

  const latestQuestionnaireEventId = useMemo(() => {
    let latest = 0;
    for (const evt of events) {
      if (
        evt.type === "artifact_update" &&
        (evt.payload as { path?: string }).path === QUESTIONNAIRE_PATH &&
        evt.id > latest
      ) {
        latest = evt.id;
      }
    }
    return latest;
  }, [events]);

  useEffect(() => {
    if (latestQuestionnaireEventId > 0) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      void loadQuestionnaire();
    }
  }, [latestQuestionnaireEventId, loadQuestionnaire]);

  const latestLifecycleEventId = useMemo(() => {
    let latest = 0;
    for (const evt of events) {
        if (RUN_LIFECYCLE_EVENT_TYPES.has(evt.type) && evt.id > latest) latest = evt.id;
    }
    return latest;
  }, [events]);

  useEffect(() => {
    if (latestLifecycleEventId > 0) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      void refresh();
    }
  }, [latestLifecycleEventId, refresh]);

  const hasReportArtifact = useMemo(
    () =>
      events.some(
        (evt) =>
          evt.type === "artifact_update" &&
          (evt.payload as { path?: string }).path === REPORT_PATH,
      ),
    [events],
  );

  useEffect(() => {
    if (hasReportArtifact) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setActiveTab("report");
    }
  }, [hasReportArtifact]);

  const handleSaveReport = async () => {
    try {
      const artifact = await getRunArtifact(runId, REPORT_PATH);
      downloadTextFile(
        `${slugForFilename(runId)}-final-report.md`,
        artifact.content,
        "text/markdown;charset=utf-8",
      );
      toast.success("Report saved");
    } catch (err) {
      toast.error(`Could not save report: ${errorMessage(err)}`);
    }
  };

  const handleSaveLogs = () => {
    const lines = events.map((event) => JSON.stringify(event));
    downloadTextFile(
      `${slugForFilename(runId)}-run-log.jsonl`,
      `${lines.join("\n")}\n`,
      "application/x-ndjson;charset=utf-8",
    );
    toast.success("Run log saved");
  };

  const handleAnswers = async (answers: Record<string, string>) => {
    try {
      await submitRunAnswers(runId, answers);
      toast.success("Answers submitted");
      setAnswersSubmitted(true);
      await refresh();
    } catch (err) {
      toast.error(errorMessage(err));
    }
  };

  const handleCancel = async () => {
    setCancelling(true);
    try {
      await cancelRun(runId);
      toast.success("Run cancelled");
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setCancelling(false);
    }
  };

  const handleRetry = async () => {
    setRetrying(true);
    try {
      await retryRun(runId);
      toast.success("Retry started");
      setStreamReconnectKey((value) => value + 1);
      await refresh();
      setActiveTab("activity");
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setRetrying(false);
    }
  };

  const runStatus = runInfo?.status;
  const isTerminal = runStatus ? TERMINAL_STATUSES.has(runStatus) : false;
  const isLive = connStatus === "open" || connStatus === "connecting";
  const hasReport = runInfo?.artifact_paths.includes(REPORT_PATH) ?? hasReportArtifact;
  const showQuestionnaire =
    questionnaire !== null && !answersSubmitted && runStatus === "questioning";
  const canResume = runStatus === "failed" || runStatus === "cancelled";

  return (
    <div className="dark">
      <main className="run-dark-bg relative min-h-screen text-stone-100">
        {/* ── Top bar ── */}
        <header className="glass-strong sticky top-0 z-30 flex items-center justify-between gap-4 border-b border-white/5 px-4 py-3 sm:px-6">
          <div className="flex min-w-0 items-center gap-3">
            <Button
              variant="ghost"
              size="icon-sm"
              className="text-stone-400 hover:text-white"
              onClick={() => router.push("/")}
            >
              <ArrowLeft className="size-4" />
            </Button>
            <div className="min-w-0">
              <div className="flex items-center gap-2.5">
                <h1 className="truncate text-sm font-semibold tracking-tight text-white">
                  {runInfo?.task_type ? titleCase(runInfo.task_type) : "Run"}
                </h1>
                <span
                  className={cn(
                    "rounded-full px-2 py-0.5 text-[10px] font-semibold tracking-wider uppercase ring-1",
                    statusStyle(runStatus),
                  )}
                >
                  {runStatus ?? (loading ? "loading" : "unknown")}
                </span>
                {isLive && !isTerminal && (
                  <span className="hidden items-center gap-1.5 text-[10px] font-medium text-emerald-400 sm:flex">
                    <span className="relative flex size-1.5">
                      <span className="absolute inline-flex size-full animate-ping rounded-full bg-emerald-400 opacity-75" />
                      <span className="relative inline-flex size-1.5 rounded-full bg-emerald-500" />
                    </span>
                    Live
                  </span>
                )}
              </div>
              <p className="mt-0.5 truncate font-mono text-[10px] text-stone-500">
                {runId}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="sm"
              className="text-stone-400 hover:text-white"
              onClick={() => void handleSaveReport()}
              disabled={!hasReport}
            >
              <Download className="size-3.5" />
              <span className="hidden sm:inline">Report</span>
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="text-stone-400 hover:text-white"
              onClick={handleSaveLogs}
              disabled={events.length === 0}
            >
              <FileText className="size-3.5" />
              <span className="hidden sm:inline">Logs</span>
            </Button>
            <Button
              variant="ghost"
              size="icon-sm"
              className="text-stone-400 hover:text-white"
              onClick={() => void refresh()}
              disabled={loading}
              aria-label="Refresh"
            >
              {loading ? <Loader2 className="size-3.5 animate-spin" /> : <RefreshCw className="size-3.5" />}
            </Button>
            {canResume && (
              <Button
                variant="ghost"
                size="sm"
                className="text-sky-300 hover:bg-sky-500/10 hover:text-sky-200"
                onClick={() => void handleRetry()}
                disabled={retrying}
              >
                {retrying ? <Loader2 className="size-3.5 animate-spin" /> : <RotateCcw className="size-3.5" />}
                <span className="hidden sm:inline">{runStatus === "cancelled" ? "Resume" : "Retry"}</span>
              </Button>
            )}
            {!isTerminal && (
              <Button
                variant="ghost"
                size="sm"
                className="text-rose-400 hover:bg-rose-500/10 hover:text-rose-300"
                onClick={() => void handleCancel()}
                disabled={cancelling}
              >
                {cancelling ? <Loader2 className="size-3.5 animate-spin" /> : <XCircle className="size-3.5" />}
                <span className="hidden sm:inline">Cancel</span>
              </Button>
            )}
          </div>
        </header>

        {/* ── Body ── */}
        <div className="relative z-10 mx-auto w-full max-w-[1600px] px-4 py-5 sm:px-6">
          {/* Goal context strip */}
          {runInfo && (
            <div className="panel mb-5 flex items-start gap-3 px-4 py-3">
              <span className="mt-0.5 shrink-0 text-[10px] font-semibold tracking-wider text-stone-500 uppercase">
                Goal
              </span>
              <p className="text-sm leading-relaxed text-stone-300">{runInfo.goal}</p>
            </div>
          )}

          {/* Pipeline graph */}
          <section className="panel mb-5 overflow-hidden">
            <div className="panel-header">
              <span>Pipeline</span>
              <span className="text-[10px] font-medium tracking-normal text-stone-500 normal-case">
                {events.length} event{events.length === 1 ? "" : "s"}
              </span>
            </div>
            <div className="h-[380px] w-full">
              <AgentGraph events={events} className="h-full w-full" />
            </div>
          </section>

          {/* Questionnaire — full-width when active */}
          {showQuestionnaire && questionnaire && (
            <section className="panel mb-5 p-5">
              <div className="mb-4 flex items-center gap-2">
                <span className="rounded-md bg-violet-500/15 px-2 py-0.5 text-[10px] font-semibold tracking-wider text-violet-300 uppercase ring-1 ring-violet-500/30">
                  Action required
                </span>
                <h2 className="text-base font-semibold text-white">Framing questionnaire</h2>
              </div>
              <p className="mb-4 text-xs text-stone-400">
                Answer these so the agent can scope the engagement precisely.
              </p>
              <QuestionnaireForm schema={questionnaire} onSubmit={handleAnswers} />
            </section>
          )}

          {/* Three-column workspace */}
          <div className="grid gap-5 lg:grid-cols-12">
            {/* Left rail — activity */}
            <aside className="space-y-5 lg:col-span-4 xl:col-span-3">
              <ChatStream events={events} status={connStatus} />
              <UsagePanel events={events} />
            </aside>

            {/* Center — report / activity tabs */}
            <section className="lg:col-span-5 xl:col-span-6">
              <div className="panel flex h-full flex-col">
                <div className="flex items-center gap-1 border-b border-white/5 px-2 py-1.5">
                  <TabButton active={activeTab === "report"} onClick={() => setActiveTab("report")}>
                    Report
                    {hasReport && (
                      <span className="ml-1.5 inline-block size-1.5 rounded-full bg-emerald-400" />
                    )}
                  </TabButton>
                  <TabButton active={activeTab === "activity"} onClick={() => setActiveTab("activity")}>
                    Activity
                  </TabButton>
                </div>
                <div className="scroll-thin max-h-[70vh] min-h-[420px] overflow-y-auto p-4">
                  {activeTab === "report" ? (
                    <ReportView
                      runId={runId}
                      events={events}
                      onCitationClick={(id) => {
                        setHighlightedSrcId(id);
                      }}
                    />
                  ) : (
                    <AgentTrace events={events} />
                  )}
                </div>
              </div>
            </section>

            {/* Right rail — sources */}
            <aside className="lg:col-span-3 xl:col-span-3">
              <SourcesSidebar
                runId={runId}
                events={events}
                highlightedSrcId={highlightedSrcId}
              />
            </aside>
          </div>
        </div>
      </main>
    </div>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "rounded-md px-3 py-1.5 text-xs font-medium transition",
        active
          ? "bg-white/[0.06] text-white"
          : "text-stone-500 hover:bg-white/[0.03] hover:text-stone-300",
      )}
    >
      {children}
    </button>
  );
}
