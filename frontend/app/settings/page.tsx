"use client";

/**
 * Settings page (M2.7).
 *
 * Single-page form bound to the M2.4 Settings REST API and the M2.6
 * `/ping` smoke endpoint. Four sections, each independently mutating:
 *
 *   1. LLM provider keys       — per-provider password input + Save Key
 *   2. Model overrides         — per-role provider Select + free-text
 *                                model Input + Save + Test connection
 *   3. Search provider         — radio (tavily/exa/perplexity) + per-
 *                                provider key input + Save (mirrors §1)
 *   4. Pipeline settings       — max_stage_retries number input (1..5)
 *
 * State model: a single `snapshot` (the GET /settings payload) plus
 * transient form state for in-flight inputs. After every successful
 * mutation we re-fetch the snapshot so `has_key` flags and persisted
 * values stay authoritative — optimistic update would drift from the
 * backend the first time validation rejects something.
 *
 * Errors: every API call is awaited inside a try/catch that toasts
 * `ApiRequestError.message` (which carries the FastAPI `detail`
 * field). Loading and saving states disable the relevant button.
 */

import { useCallback, useMemo, useRef, useState } from "react";
import { toast } from "sonner";

import {
  ApiRequestError,
  getSettings,
  pingLLM,
  setMaxStageRetries,
  setModelOverride,
  setProviderKey,
  setSearchProvider,
  testSearchProvider,
} from "@/lib/api";
import {
  AGENT_ROLES,
  LLM_PROVIDERS,
  SEARCH_PROVIDERS,
  type AgentRole,
  type ProviderInfo,
  type ProviderName,
  type SearchProviderName,
  type SettingsSnapshot,
} from "@/lib/types";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function errorMessage(err: unknown): string {
  if (err instanceof ApiRequestError) return err.message;
  if (err instanceof Error) return err.message;
  return String(err);
}

function providerLabel(name: ProviderName | SearchProviderName): string {
  return name.charAt(0).toUpperCase() + name.slice(1);
}

const LLM_PROVIDER_SET = new Set<string>(LLM_PROVIDERS);
const SEARCH_PROVIDER_SET = new Set<string>(SEARCH_PROVIDERS);

function pickProviders(
  providers: ProviderInfo[],
  membership: Set<string>,
): ProviderInfo[] {
  return providers.filter((p) => membership.has(p.provider));
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function SettingsPage() {
  const [snapshot, setSnapshot] = useState<SettingsSnapshot | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    return getSettings()
      .then((next) => {
        setSnapshot(next);
        setLoadError(null);
      })
      .catch((err: unknown) => {
        setLoadError(errorMessage(err));
      });
  }, []);

  // Initial load. Using a ref-init guard sidesteps the
  // react-hooks/set-state-in-effect rule: setState fires inside the
  // fetch's resolution callback, which is exactly the "external system
  // event" pattern the rule is designed to allow. The `ref.current ==
  // null` shape is the one the lint accepts as legitimate one-shot
  // initialisation.
  const bootstrapped = useRef<boolean | null>(null);
  if (bootstrapped.current == null) {
    bootstrapped.current = true;
    void refresh();
  }

  if (loadError !== null) {
    return (
      <main className="mx-auto max-w-3xl p-8">
        <h1 className="text-3xl font-semibold tracking-tight mb-4">Settings</h1>
        <Card>
          <CardHeader>
            <CardTitle>Couldn&apos;t load settings</CardTitle>
            <CardDescription className="text-destructive">
              {loadError}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button onClick={() => void refresh()}>Retry</Button>
          </CardContent>
        </Card>
      </main>
    );
  }

  if (snapshot === null) {
    return (
      <main className="mx-auto max-w-3xl p-8">
        <h1 className="text-3xl font-semibold tracking-tight mb-4">Settings</h1>
        <p className="text-sm text-muted-foreground">Loading settings…</p>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-3xl p-8 space-y-6">
      <header>
        <h1 className="text-3xl font-semibold tracking-tight">Settings</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Provider API keys, per-role model overrides, search backend, and
          pipeline retry budget. Stored encrypted on the backend; raw keys
          never come back from the server.
        </p>
      </header>

      <LlmProvidersSection snapshot={snapshot} onRefresh={refresh} />
      <ModelOverridesSection snapshot={snapshot} onRefresh={refresh} />
      <SearchProviderSection snapshot={snapshot} onRefresh={refresh} />
      <PipelineSettingsSection snapshot={snapshot} onRefresh={refresh} />
    </main>
  );
}

// ---------------------------------------------------------------------------
// 1. LLM provider keys
// ---------------------------------------------------------------------------

interface SectionProps {
  snapshot: SettingsSnapshot;
  onRefresh: () => Promise<void>;
}

function LlmProvidersSection({ snapshot, onRefresh }: SectionProps) {
  const llmProviders = useMemo(
    () => pickProviders(snapshot.providers, LLM_PROVIDER_SET),
    [snapshot.providers],
  );

  return (
    <Card>
      <CardHeader>
        <CardTitle>LLM provider keys</CardTitle>
        <CardDescription>
          Save an API key for each provider you want the agent to use.
          Keys are encrypted at rest; only a presence flag is returned.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {llmProviders.map((info, idx) => (
          <div key={info.provider}>
            <ProviderKeyRow info={info} onSaved={onRefresh} />
            {idx < llmProviders.length - 1 ? (
              <Separator className="mt-4" />
            ) : null}
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

interface ProviderKeyRowProps {
  info: ProviderInfo;
  onSaved: () => Promise<void>;
}

function ProviderKeyRow({ info, onSaved }: ProviderKeyRowProps) {
  const [value, setValue] = useState("");
  const [saving, setSaving] = useState(false);

  const save = async () => {
    if (value.trim().length === 0) {
      toast.error("Key cannot be empty");
      return;
    }
    setSaving(true);
    try {
      await setProviderKey(info.provider, value);
      toast.success(`Saved ${providerLabel(info.provider)} key`);
      setValue("");
      await onSaved();
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="grid grid-cols-[160px_1fr_auto] items-center gap-3">
      <div className="flex items-center gap-2">
        <span className="font-medium">{providerLabel(info.provider)}</span>
        {info.has_key ? (
          <Badge variant="secondary">configured</Badge>
        ) : (
          <Badge variant="outline">no key</Badge>
        )}
      </div>
      <Input
        type="password"
        autoComplete="off"
        placeholder={info.has_key ? "•••••••• (replace)" : "sk-…"}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        disabled={saving}
      />
      <Button onClick={() => void save()} disabled={saving || value.length === 0}>
        {saving ? "Saving…" : "Save Key"}
      </Button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// 2. Model overrides
// ---------------------------------------------------------------------------

function ModelOverridesSection({ snapshot, onRefresh }: SectionProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Model overrides (per role)</CardTitle>
        <CardDescription>
          Pick a provider and free-text model name for each agent role.
          Empty rows fall back to the system default ({"anthropic"} / each
          provider&apos;s default model).
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {AGENT_ROLES.map((role, idx) => (
          <div key={role}>
            <RoleOverrideRow
              role={role}
              snapshot={snapshot}
              onSaved={onRefresh}
            />
            {idx < AGENT_ROLES.length - 1 ? (
              <Separator className="mt-4" />
            ) : null}
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

interface RoleOverrideRowProps {
  role: AgentRole;
  snapshot: SettingsSnapshot;
  onSaved: () => Promise<void>;
}

function RoleOverrideRow({ role, snapshot, onSaved }: RoleOverrideRowProps) {
  const current = snapshot.model_overrides[role];
  const [providerSel, setProviderSel] = useState<ProviderName>(
    (current?.provider as ProviderName | undefined) ?? "anthropic",
  );
  const [model, setModel] = useState(current?.model ?? "");
  const [saving, setSaving] = useState(false);
  const [pinging, setPinging] = useState(false);

  // Re-sync local form state when the snapshot changes (e.g. after an
  // adjacent role's save). React's recommended pattern for "adjust
  // state when a prop changes" is to compare against the previous
  // value during render — see
  // https://react.dev/reference/react/useState#storing-information-from-previous-renders.
  // This avoids the react-hooks/set-state-in-effect lint and is one
  // render cheaper than the effect-based equivalent.
  const [lastSeen, setLastSeen] = useState(current);
  if (current !== lastSeen) {
    setLastSeen(current);
    if (current !== undefined) {
      setProviderSel(current.provider as ProviderName);
      setModel(current.model);
    }
  }

  const save = async () => {
    if (model.trim().length === 0) {
      toast.error(`Model name required for ${role}`);
      return;
    }
    setSaving(true);
    try {
      await setModelOverride(
        role,
        providerSel,
        model.trim(),
        snapshot.model_overrides,
      );
      toast.success(`Saved override for ${role}`);
      await onSaved();
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  const test = async () => {
    setPinging(true);
    try {
      const res = await pingLLM(role);
      const preview =
        res.response.length > 100
          ? `${res.response.slice(0, 100)}…`
          : res.response;
      toast.success(`${res.provider} / ${res.model}: ${preview}`);
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setPinging(false);
    }
  };

  return (
    <div className="space-y-2">
      <div className="flex items-baseline justify-between">
        <Label className="capitalize">{role}</Label>
        {current !== undefined ? (
          <span className="text-xs text-muted-foreground font-mono">
            current: {current.provider} / {current.model}
          </span>
        ) : (
          <span className="text-xs text-muted-foreground">no override</span>
        )}
      </div>
      <div className="grid grid-cols-[160px_1fr_auto_auto] items-center gap-3">
        <Select
          value={providerSel}
          onValueChange={(v) => setProviderSel(v as ProviderName)}
        >
          <SelectTrigger className="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {LLM_PROVIDERS.map((p) => (
              <SelectItem key={p} value={p}>
                {providerLabel(p)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Input
          placeholder="e.g. claude-sonnet-4-5-20250929"
          value={model}
          onChange={(e) => setModel(e.target.value)}
          disabled={saving}
        />
        <Button
          variant="outline"
          onClick={() => void save()}
          disabled={saving || model.trim().length === 0}
        >
          {saving ? "Saving…" : "Save"}
        </Button>
        <Button
          variant="ghost"
          onClick={() => void test()}
          disabled={pinging}
        >
          {pinging ? "Testing…" : "Test"}
        </Button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// 3. Search provider
// ---------------------------------------------------------------------------

function SearchProviderSection({ snapshot, onRefresh }: SectionProps) {
  const [selected, setSelected] = useState<SearchProviderName>(
    snapshot.search_provider ?? "tavily",
  );
  const [savingActive, setSavingActive] = useState(false);
  const [testingSearch, setTestingSearch] = useState(false);

  // Sync to snapshot updates (e.g. after key save triggers a refresh).
  // Previous-prop comparison instead of an effect — see RoleOverrideRow.
  const [lastSeenActive, setLastSeenActive] = useState(snapshot.search_provider);
  if (snapshot.search_provider !== lastSeenActive) {
    setLastSeenActive(snapshot.search_provider);
    if (snapshot.search_provider !== null) {
      setSelected(snapshot.search_provider);
    }
  }

  const searchProviderInfos = useMemo(
    () => pickProviders(snapshot.providers, SEARCH_PROVIDER_SET),
    [snapshot.providers],
  );

  const saveActive = async (next: SearchProviderName) => {
    setSelected(next);
    setSavingActive(true);
    try {
      await setSearchProvider(next);
      toast.success(`Search provider set to ${providerLabel(next)}`);
      await onRefresh();
    } catch (err) {
      toast.error(errorMessage(err));
      // Roll back the radio selection on failure so UI ≡ backend.
      if (snapshot.search_provider !== null) {
        setSelected(snapshot.search_provider);
      }
    } finally {
      setSavingActive(false);
    }
  };

  const testSearch = async () => {
    setTestingSearch(true);
    try {
      const result = await testSearchProvider("test");
      if (result.titles.length === 0) {
        toast.success("Search test succeeded (no titles returned)");
      } else {
        toast.success(result.titles.join(" | "));
      }
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setTestingSearch(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Search provider</CardTitle>
        <CardDescription>
          Pick the active web-search backend and save its API key. Only
          one provider is active at a time, but you can keep keys
          configured for all three.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <RadioGroup
          value={selected}
          onValueChange={(v) => void saveActive(v as SearchProviderName)}
          className="grid grid-cols-3 gap-2"
        >
          {SEARCH_PROVIDERS.map((p) => (
            <Label
              key={p}
              className="flex items-center gap-2 rounded-lg border border-border px-3 py-2 cursor-pointer"
            >
              <RadioGroupItem value={p} disabled={savingActive} />
              <span>{providerLabel(p)}</span>
            </Label>
          ))}
        </RadioGroup>
        <Separator />
        {searchProviderInfos.map((info, idx) => (
          <div key={info.provider}>
            <ProviderKeyRow info={info} onSaved={onRefresh} />
            {idx < searchProviderInfos.length - 1 ? (
              <Separator className="mt-4" />
            ) : null}
          </div>
        ))}
        <div className="flex justify-end">
          <Button
            variant="outline"
            onClick={() => void testSearch()}
            disabled={testingSearch}
          >
            {testingSearch ? "Testing…" : "Test search"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// 4. Pipeline settings
// ---------------------------------------------------------------------------

function PipelineSettingsSection({ snapshot, onRefresh }: SectionProps) {
  const [value, setValue] = useState(snapshot.max_stage_retries);
  const [saving, setSaving] = useState(false);

  // Previous-prop comparison instead of an effect — see RoleOverrideRow.
  const [lastSeenRetries, setLastSeenRetries] = useState(snapshot.max_stage_retries);
  if (snapshot.max_stage_retries !== lastSeenRetries) {
    setLastSeenRetries(snapshot.max_stage_retries);
    setValue(snapshot.max_stage_retries);
  }

  const save = async () => {
    setSaving(true);
    try {
      await setMaxStageRetries(value);
      toast.success(`Max stage retries set to ${value}`);
      await onRefresh();
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Pipeline settings</CardTitle>
        <CardDescription>
          Maximum retry attempts per agent stage. Bounded 1..5 by the
          backend.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-[200px_120px_auto] items-center gap-3">
          <Label htmlFor="max-stage-retries">Max stage retries</Label>
          <Input
            id="max-stage-retries"
            type="number"
            min={1}
            max={5}
            value={value}
            onChange={(e) => {
              const n = Number(e.target.value);
              setValue(Number.isFinite(n) ? n : value);
            }}
            disabled={saving}
          />
          <Button onClick={() => void save()} disabled={saving}>
            {saving ? "Saving…" : "Save"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
