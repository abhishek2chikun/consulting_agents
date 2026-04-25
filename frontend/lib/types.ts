/**
 * Shared types for the Consulting Research Agent frontend.
 *
 * These mirror the backend Pydantic schemas in
 * `backend/app/schemas/{settings,ping}.py`. The two sides are kept in
 * sync manually for V1 — there is no codegen step. If you change a DTO
 * on the backend, update this file too. The defensive
 * `test_get_providers_never_exposes_raw_key` integration test on the
 * backend is the contract guarantee for `ProviderInfo` (no `key`
 * field — only `has_key`).
 */

/** All providers the backend persists keys for. Mirrors `KNOWN_PROVIDERS`. */
export type ProviderName =
  | "anthropic"
  | "openai"
  | "google"
  | "aws"
  | "ollama"
  | "tavily"
  | "exa"
  | "perplexity";

/** Search providers (closed `Literal` on the backend). */
export type SearchProviderName = "tavily" | "exa" | "perplexity";

/** LLM providers shown in the per-role override picker. */
export const LLM_PROVIDERS: readonly ProviderName[] = [
  "anthropic",
  "openai",
  "google",
  "aws",
  "ollama",
] as const;

/** Search providers shown in the radio group. */
export const SEARCH_PROVIDERS: readonly SearchProviderName[] = [
  "tavily",
  "exa",
  "perplexity",
] as const;

/**
 * V1 agent roles surfaced in the settings UI.
 *
 * The backend `model_overrides` map is open-ended (per the M2.4
 * decision in `backend/app/schemas/settings.py`), but the UI ships a
 * known set so the page can render a fixed grid without first probing
 * the backend for which roles exist.
 */
export const AGENT_ROLES = [
  "framing",
  "research",
  "reviewer",
  "synthesis",
  "audit",
] as const;
export type AgentRole = (typeof AGENT_ROLES)[number];

export interface ProviderInfo {
  provider: ProviderName;
  has_key: boolean;
}

export interface ProvidersResponse {
  providers: ProviderInfo[];
}

export interface ModelOverride {
  provider: string;
  model: string;
}

/** Map keyed by role -> {provider, model}. Backend stores under settings_kv. */
export type ModelOverridesMap = Record<string, ModelOverride>;

export interface SettingsSnapshot {
  providers: ProviderInfo[];
  model_overrides: ModelOverridesMap;
  search_provider: SearchProviderName | null;
  max_stage_retries: number;
}

export interface PingResponse {
  response: string;
  model: string;
  provider: string;
}

export interface SearchHealthResponse {
  titles: string[];
}

export interface CreateRunResponse {
  run_id: string;
}

export interface RunInfoResponse {
  run_id: string;
  task_type: string;
  goal: string;
  status: string;
  artifact_paths: string[];
}

export interface ArtifactContentResponse {
  path: string;
  kind: string;
  content: string;
}

/**
 * Mirrors `app/schemas/runs.py::EvidenceItem` (M7.4).
 * One row of `Run.evidence`, rendered by `<SourcesSidebar>`.
 */
export interface EvidenceItem {
  src_id: string;
  kind: "web" | "doc";
  url: string | null;
  title: string;
  snippet: string;
  provider: string;
}

export interface EvidenceListResponse {
  evidence: EvidenceItem[];
}

/**
 * Mirrors `app/schemas/framing.py::QuestionItem`.
 * Rendered by `<QuestionnaireForm>`.
 */
export interface QuestionnaireItem {
  id: string;
  label: string;
  type: "text" | "select" | "multiselect";
  options?: string[];
  helper?: string | null;
  required: boolean;
}

export interface QuestionnaireSchema {
  items: QuestionnaireItem[];
}
