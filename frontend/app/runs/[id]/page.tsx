"use client";

import { useMemo, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { toast } from "sonner";

import { ChatStream } from "@/components/ChatStream";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cancelRun, getRun, submitRunAnswers } from "@/lib/api";
import type { RunInfoResponse } from "@/lib/types";

function errorMessage(err: unknown): string {
  if (err instanceof Error) return err.message;
  return String(err);
}

export default function RunPage() {
  const params = useParams<{ id: string }>();
  const runId = params.id;

  const [runInfo, setRunInfo] = useState<RunInfoResponse | null>(null);
  const [answerValue, setAnswerValue] = useState("");
  const [loading, setLoading] = useState(false);

  const refresh = async () => {
    setLoading(true);
    try {
      const next = await getRun(runId);
      setRunInfo(next);
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  const bootstrapped = useRef<boolean | null>(null);
  if (bootstrapped.current == null) {
    bootstrapped.current = true;
    void refresh();
  }

  const artifactSummary = useMemo(() => {
    if (runInfo === null) return "Loading…";
    if (runInfo.artifact_paths.length === 0) return "No artifacts yet";
    return runInfo.artifact_paths.join("\n");
  }, [runInfo]);

  const submitAnswers = async () => {
    if (answerValue.trim().length === 0) {
      toast.error("Enter at least one answer");
      return;
    }
    try {
      await submitRunAnswers(runId, { freeform: answerValue.trim() });
      toast.success("Answers submitted");
      setAnswerValue("");
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
          Minimal run view (M5.7): metadata + SSE event stream.
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
          <CardTitle>Submit answers</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <Label htmlFor="answers">Freeform answer</Label>
          <Input
            id="answers"
            value={answerValue}
            onChange={(e) => setAnswerValue(e.target.value)}
            placeholder="e.g. Focus on enterprise segment in EU"
          />
          <Button onClick={() => void submitAnswers()}>Submit answers</Button>
        </CardContent>
      </Card>

      <ChatStream runId={runId} />
    </main>
  );
}
