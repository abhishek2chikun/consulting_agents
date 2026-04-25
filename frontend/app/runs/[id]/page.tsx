"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { toast } from "sonner";

import { ChatStream } from "@/components/ChatStream";
import { QuestionnaireForm } from "@/components/QuestionnaireForm";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  cancelRun,
  getRun,
  getRunArtifact,
  submitRunAnswers,
} from "@/lib/api";
import { useEventStream } from "@/lib/sse";
import type { QuestionnaireSchema, RunInfoResponse } from "@/lib/types";

const QUESTIONNAIRE_PATH = "framing/questionnaire.json";

function errorMessage(err: unknown): string {
  if (err instanceof Error) return err.message;
  return String(err);
}

export default function RunPage() {
  const params = useParams<{ id: string }>();
  const runId = params.id;

  const [runInfo, setRunInfo] = useState<RunInfoResponse | null>(null);
  const [questionnaire, setQuestionnaire] = useState<QuestionnaireSchema | null>(
    null,
  );
  const [answersSubmitted, setAnswersSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);

  const { events, status } = useEventStream(runId);

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
    // Try loading any pre-existing questionnaire (resume case).
    void getRunArtifact(runId, QUESTIONNAIRE_PATH)
      .then((artifact) => {
        setQuestionnaire(JSON.parse(artifact.content) as QuestionnaireSchema);
      })
      .catch(() => {
        // Not yet produced; SSE will trigger fetch when ready.
      });
  }, [refresh, runId]);

  // Derive the most recent artifact_update event id targeting the
  // questionnaire path. Pure function of `events` — no refs in render.
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
      // Synchronizing to an external system (the questionnaire artifact
      // backed by Postgres + SSE) — fetch is intentional here.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      void loadQuestionnaire();
    }
  }, [latestQuestionnaireEventId, loadQuestionnaire]);

  const artifactSummary = useMemo(() => {
    if (runInfo === null) return "Loading…";
    if (runInfo.artifact_paths.length === 0) return "No artifacts yet";
    return runInfo.artifact_paths.join("\n");
  }, [runInfo]);

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

  const doCancel = async () => {
    try {
      await cancelRun(runId);
      toast.success("Cancellation requested");
      await refresh();
    } catch (err) {
      toast.error(errorMessage(err));
    }
  };

  return (
    <main className="mx-auto max-w-4xl p-8 space-y-6">
      <header>
        <h1 className="text-3xl font-semibold tracking-tight">Run {runId}</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Run view (M6.3): metadata, framing questionnaire, and SSE event stream.
        </p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>Run metadata</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <div>status: {runInfo?.status ?? (loading ? "loading" : "unknown")}</div>
          <div>task: {runInfo?.task_type ?? "-"}</div>
          <div>goal: {runInfo?.goal ?? "-"}</div>
          <pre className="rounded border p-3 text-xs whitespace-pre-wrap">{artifactSummary}</pre>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => void refresh()} disabled={loading}>
              Refresh
            </Button>
            <Button variant="destructive" onClick={() => void doCancel()}>
              Cancel run
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Framing questionnaire</CardTitle>
        </CardHeader>
        <CardContent>
          {questionnaire === null ? (
            <p className="text-sm text-muted-foreground">
              Waiting for the framing agent to produce the questionnaire…
            </p>
          ) : answersSubmitted ? (
            <p className="text-sm text-muted-foreground">
              Answers submitted. The research agents are now working.
            </p>
          ) : (
            <QuestionnaireForm
              schema={questionnaire}
              onSubmit={handleAnswers}
            />
          )}
        </CardContent>
      </Card>

      <ChatStream runId={runId} events={events} status={status} />
    </main>
  );
}
