"use client";

import { useMemo, useState } from "react";
import { Loader2 } from "lucide-react";

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
import { cn } from "@/lib/utils";

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
    if (errors[id]) setErrors((prev) => ({ ...prev, [id]: false }));
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const nextErrors: Record<string, boolean> = {};
    for (const item of schema.items) {
      if (!answerValid(item, values[item.id] ?? "")) nextErrors[item.id] = true;
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
      <p className="text-sm text-stone-400">Questionnaire is empty — nothing to answer.</p>
    );
  }

  const required = schema.items.filter((it) => it.required).length;
  const answered = schema.items.filter(
    (it) => it.required && (values[it.id] ?? "").trim().length > 0,
  ).length;
  const progress = required === 0 ? 100 : Math.round((answered / required) * 100);

  return (
    <form className="space-y-5" onSubmit={handleSubmit}>
      {/* Progress bar */}
      <div>
        <div className="mb-1.5 flex items-center justify-between text-[10px] tracking-wider text-stone-500 uppercase">
          <span>Progress</span>
          <span>
            {answered} / {required}
          </span>
        </div>
        <div className="h-1 overflow-hidden rounded-full bg-white/5">
          <div
            className="h-full rounded-full bg-gradient-to-r from-violet-500 to-sky-400 transition-all duration-500"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        {schema.items.map((item) => {
          const value = values[item.id] ?? "";
          const hasError = !!errors[item.id];
          return (
            <div key={item.id} className="space-y-1.5">
              <Label
                htmlFor={`q-${item.id}`}
                className="text-xs font-medium text-stone-300"
              >
                {item.label}
                {item.required ? <span className="ml-1 text-rose-400">*</span> : null}
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
                    className={cn(
                      "border-white/10 bg-white/[0.03] text-stone-100",
                      hasError && "border-rose-500/60",
                    )}
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
                  className={cn(
                    "border-white/10 bg-white/[0.03] text-stone-100 placeholder:text-stone-500",
                    hasError && "border-rose-500/60",
                  )}
                />
              )}
              {item.helper ? (
                <p className="text-[11px] text-stone-500">{item.helper}</p>
              ) : null}
              {hasError ? (
                <p className="text-[11px] text-rose-400">This field is required.</p>
              ) : null}
            </div>
          );
        })}
      </div>

      <div className="flex items-center justify-end pt-2">
        <Button type="submit" disabled={disabled || submitting} className="gap-1.5">
          {submitting && <Loader2 className="size-3.5 animate-spin" />}
          {submitting ? "Submitting…" : "Submit answers"}
        </Button>
      </div>
    </form>
  );
}
