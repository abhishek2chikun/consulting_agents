"use client";

/**
 * QuestionnaireForm — renders the framing-stage questionnaire produced
 * by `nodes/framing.py` and persisted as
 * `framing/questionnaire.json` artifact (M6.2).
 *
 * Lifecycle:
 *  1. Parent listens to SSE; on `artifact_update` whose `path ===
 *     "framing/questionnaire.json"` it fetches the artifact via
 *     `getRunArtifact` and passes the parsed schema in.
 *  2. User fills out the form; on submit we POST `/runs/{id}/answers`
 *     with `{ [item.id]: value }` (multiselect collapsed to comma list
 *     for V1's `Record<string, string>` API contract).
 *
 * V1 keeps validation light: required fields are checked client-side
 * and an `onSubmit` callback returns a Promise so the parent can show
 * loading state and toast errors.
 */

import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { QuestionnaireItem, QuestionnaireSchema } from "@/lib/types";

interface QuestionnaireFormProps {
  schema: QuestionnaireSchema;
  onSubmit: (answers: Record<string, string>) => Promise<void> | void;
  disabled?: boolean;
}

function answerValid(item: QuestionnaireItem, value: string): boolean {
  if (!item.required) return true;
  return value.trim().length > 0;
}

export function QuestionnaireForm({
  schema,
  onSubmit,
  disabled,
}: QuestionnaireFormProps) {
  const initial = useMemo(
    () => Object.fromEntries(schema.items.map((it) => [it.id, ""])),
    [schema],
  );
  const [values, setValues] = useState<Record<string, string>>(initial);
  const [submitting, setSubmitting] = useState(false);
  const [errors, setErrors] = useState<Record<string, boolean>>({});

  const handleChange = (id: string, next: string) => {
    setValues((prev) => ({ ...prev, [id]: next }));
    if (errors[id]) {
      setErrors((prev) => ({ ...prev, [id]: false }));
    }
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const nextErrors: Record<string, boolean> = {};
    for (const item of schema.items) {
      if (!answerValid(item, values[item.id] ?? "")) {
        nextErrors[item.id] = true;
      }
    }
    if (Object.keys(nextErrors).length > 0) {
      setErrors(nextErrors);
      return;
    }
    setSubmitting(true);
    try {
      await onSubmit(values);
    } finally {
      setSubmitting(false);
    }
  };

  if (schema.items.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        Questionnaire is empty — nothing to answer.
      </p>
    );
  }

  return (
    <form className="space-y-4" onSubmit={handleSubmit}>
      {schema.items.map((item) => {
        const value = values[item.id] ?? "";
        const hasError = !!errors[item.id];
        return (
          <div key={item.id} className="space-y-1.5">
            <Label htmlFor={`q-${item.id}`}>
              {item.label}
              {item.required ? <span className="text-destructive ml-1">*</span> : null}
            </Label>
            {item.type === "select" || item.type === "multiselect" ? (
              <Select
                value={value || undefined}
                onValueChange={(v) => handleChange(item.id, v ?? "")}
                disabled={disabled || submitting}
              >
                <SelectTrigger
                  id={`q-${item.id}`}
                  aria-invalid={hasError}
                  className={hasError ? "border-destructive" : undefined}
                >
                  <SelectValue placeholder="Select…" />
                </SelectTrigger>
                <SelectContent>
                  {(item.options ?? []).map((opt) => (
                    <SelectItem key={opt} value={opt}>
                      {opt}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            ) : (
              <Input
                id={`q-${item.id}`}
                value={value}
                onChange={(e) => handleChange(item.id, e.target.value)}
                disabled={disabled || submitting}
                aria-invalid={hasError}
                className={hasError ? "border-destructive" : undefined}
              />
            )}
            {item.helper ? (
              <p className="text-xs text-muted-foreground">{item.helper}</p>
            ) : null}
            {hasError ? (
              <p className="text-xs text-destructive">This field is required.</p>
            ) : null}
          </div>
        );
      })}

      <Button type="submit" disabled={disabled || submitting}>
        {submitting ? "Submitting…" : "Submit answers"}
      </Button>
    </form>
  );
}
