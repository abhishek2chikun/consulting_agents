"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { createRun } from "@/lib/api";

function errorMessage(err: unknown): string {
  if (err instanceof Error) return err.message;
  return String(err);
}

export default function Home() {
  const router = useRouter();
  const [goal, setGoal] = useState("");
  const [starting, setStarting] = useState(false);

  const start = async () => {
    if (goal.trim().length === 0) {
      toast.error("Goal is required");
      return;
    }
    setStarting(true);
    try {
      const created = await createRun({
        task_type: "market_entry",
        goal: goal.trim(),
        document_ids: [],
      });
      toast.success("Run created");
      router.push(`/runs/${created.run_id}`);
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setStarting(false);
    }
  };

  return (
    <main className="mx-auto max-w-3xl p-8 space-y-6">
      <header>
        <h1 className="text-3xl font-semibold tracking-tight">Consulting Research Agent</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Start a new Market Entry run (M5.7 minimal UI).
        </p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>New run</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="space-y-2">
            <Label htmlFor="goal">Goal</Label>
            <Textarea
              id="goal"
              value={goal}
              onChange={(e) => setGoal(e.target.value)}
              placeholder="e.g. Assess feasibility and GTM strategy for entering Germany B2B payroll market"
              rows={5}
            />
          </div>
          <Button onClick={() => void start()} disabled={starting}>
            {starting ? "Starting…" : "Start"}
          </Button>
        </CardContent>
      </Card>
    </main>
  );
}
