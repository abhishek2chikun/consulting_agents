"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { toast } from "sonner";

import { AgentTrace } from "@/components/AgentTrace";
import { ChatStream } from "@/components/ChatStream";
import { QuestionnaireForm } from "@/components/QuestionnaireForm";
import { ReportView } from "@/components/ReportView";
import { SourcesSidebar } from "@/components/SourcesSidebar";
import { UsagePanel } from "@/components/UsagePanel";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getRun, getRunArtifact, submitRunAnswers } from "@/lib/api";
import { useEventStream } from "@/lib/sse";
import type { QuestionnaireSchema, RunInfoResponse } from "@/lib/types";

const QUESTIONNAIRE_PATH = "framing/questionnaire.json";
const RUN_LIFECYCLE_EVENTS = new Set([
  "run_completed",
  "run_failed",
  "run_cancelled",
  "cancel_ack",
]);

function errorMessage(err: unknown): string {
  if (err instanceof Error) return err.message;
  return String(err);
}

export default function RunPage() {
  const params = useParams<{ id: string }>();
  const runId = params.id;

  const [runInfo, setRunInfo] = useState<RunInfoResponse | null>(null);
  const [questionnaire, setQuestionnaire] =
    useState<QuestionnaireSchema | null>(null);
  const [answersSubmitted, setAnswersSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [highlightedSrcId, setHighlightedSrcId] = useState<string | null>(null);

  const { events, status: connStatus } = useEventStream(runId);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const next = await getRun(runId);
      setRunInfo(next);
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [runId]);

  const loadQuestionnaire = useCallback(async () => {
    try {
      const artifact = await getRunArtifact(runId, QUESTIONNAIRE_PATH);
      const parsed = JSON.parse(artifact.content) as QuestionnaireSchema;
      setQuestionnaire(parsed);
    } catch (err) {
      toast.error(`Could not load questionnaire: ${errorMessage(err)}`);
    }
  }, [runId]);

  // Initial bootstrap on mount.
  const bootstrapped = useRef(false);
  useEffect(() => {
    if (bootstrapped.current) return;
    bootstrapped.current = true;
    void refresh();
    void getRunArtifact(runId, QUESTIONNAIRE_PATH)
      .then((artifact) => {
        setQuestionnaire(JSON.parse(artifact.content) as QuestionnaireSchema);
      })
      .catch(() => {
        // Not yet produced; SSE will trigger fetch when ready.
      });
  }, [refresh, runId]);

  // Latest event id targeting the questionnaire artifact.
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

  // Refresh run metadata whenever a lifecycle event lands so
  // `runInfo.status` stays current (drives Cancel button + status
  // pill). We key off the latest matching event id.
  const latestLifecycleEventId = useMemo(() => {
    let latest = 0;
    for (const evt of events) {
      if (RUN_LIFECYCLE_EVENTS.has(evt.type) && evt.id > latest) {
        latest = evt.id;
      }
    }
    return latest;
  }, [events]);

  useEffect(() => {
    if (latestLifecycleEventId > 0) {
      // Synchronizing run metadata to lifecycle SSE events backed by
      // Postgres — this is the documented external-system sync case.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      void refresh();
    }
  }, [latestLifecycleEventId, refresh]);

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

  const runStatus = runInfo?.status;

  return (
    <main className="mx-auto max-w-[1600px] space-y-4 p-6">
      <header className="flex items-baseline justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Run {runId}</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            task: <span className="font-mono">{runInfo?.task_type ?? "-"}</span>
            {" · "}status:{" "}
            <span className="font-mono">
              {runStatus ?? (loading ? "loading" : "unknown")}
            </span>
          </p>
        </div>
        <Button variant="outline" onClick={() => void refresh()} disabled={loading}>
          Refresh
        </Button>
      </header>

      {runInfo && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Goal</CardTitle>
          </CardHeader>
          <CardContent className="text-sm whitespace-pre-wrap">
            {runInfo.goal}
          </CardContent>
        </Card>
      )}

      {questionnaire !== null && !answersSubmitted && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Framing questionnaire</CardTitle>
          </CardHeader>
          <CardContent>
            <QuestionnaireForm
              schema={questionnaire}
              onSubmit={handleAnswers}
            />
          </CardContent>
        </Card>
      )}

      {/*
       * 4-pane workspace (M7.6):
       *   left   — chat + agent trace
       *   center — final report
       *   right  — sources + usage/cancel
       *
       * Collapses to a single column under `lg`.
       */}
      <section className="grid gap-4 lg:grid-cols-12">
        <div className="space-y-4 lg:col-span-4">
          <div className="h-[28rem]">
            <ChatStream runId={runId} events={events} status={connStatus} />
          </div>
          <AgentTrace events={events} />
        </div>

        <div className="lg:col-span-5">
          <ReportView
            runId={runId}
            events={events}
            onCitationClick={setHighlightedSrcId}
          />
        </div>

        <div className="space-y-4 lg:col-span-3">
          <UsagePanel runId={runId} events={events} status={runStatus} />
          <div className="h-[36rem]">
            <SourcesSidebar
              runId={runId}
              events={events}
              highlightedSrcId={highlightedSrcId}
            />
          </div>
        </div>
      </section>
    </main>
  );
}
