/**
 * Typed REST client for the Consulting Research Agent FastAPI backend.
 *
 * Thin `fetch` wrapper — no third-party HTTP library — with two
 * design decisions worth flagging:
 *
 * 1. **Error model.** Non-2xx responses throw `ApiRequestError`. The
 *    page component catches and toasts `err.message`. We deliberately
 *    surface `detail` from the backend (FastAPI's standard error
 *    envelope) rather than swallow it, so users see actionable
 *    messages like "No API key configured for provider 'anthropic'".
 *
 * 2. **`setModelOverride` contract.** The backend
 *    `PUT /settings/model_overrides` REPLACES the entire overrides
 *    map (not a partial update — see `backend/app/api/settings.py`).
 *    The single-role helper here therefore takes the *current* map as
 *    its 4th argument and merges. The page component owns the
 *    snapshot, so it always has the current map on hand. The raw
 *    `setModelOverrides` is also exported for callers that want to
 *    construct the full map themselves.
 *
 * Base URL: configurable via `NEXT_PUBLIC_API_BASE_URL`. Defaults to
 * `http://localhost:8000` — the convention for `uv run uvicorn` in
 * this repo.
 */

import type {
  ArtifactContentResponse,
  CreateRunResponse,
  DocumentInfo,
  EvidenceListResponse,
  ModelOverridesMap,
  PingResponse,
  ProviderName,
  ProvidersResponse,
  RunInfoResponse,
  SearchHealthResponse,
  SearchProviderName,
  SettingsSnapshot,
  TaskTypeInfo,
} from "./types";

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

/**
 * Error thrown for any non-2xx HTTP response from the backend.
 * `message` carries the parsed `detail` field when present, otherwise
 * a generic `<status> <statusText>` fallback.
 */
export class ApiRequestError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiRequestError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });

  if (!res.ok) {
    let detail: string;
    try {
      const body = (await res.json()) as { detail?: unknown };
      if (typeof body.detail === "string") {
        detail = body.detail;
      } else if (body.detail !== undefined) {
        detail = JSON.stringify(body.detail);
      } else {
        detail = `${res.status} ${res.statusText}`;
      }
    } catch {
      detail = `${res.status} ${res.statusText}`;
    }
    throw new ApiRequestError(res.status, detail);
  }

  // 204 No Content — most PUTs land here.
  if (res.status === 204) {
    return undefined as T;
  }
  return (await res.json()) as T;
}

// ---------------------------------------------------------------------------
// Settings
// ---------------------------------------------------------------------------

export const getProviders = (): Promise<ProvidersResponse> =>
  request<ProvidersResponse>("/settings/providers");

export const getSettings = (): Promise<SettingsSnapshot> =>
  request<SettingsSnapshot>("/settings");

export const setProviderKey = (provider: ProviderName, key: string): Promise<void> =>
  request<void>(`/settings/providers/${provider}`, {
    method: "PUT",
    body: JSON.stringify({ key }),
  });

/**
 * Replace the *entire* model_overrides map. Use `setModelOverride`
 * for single-role updates that preserve sibling roles.
 */
export const setModelOverrides = (overrides: ModelOverridesMap): Promise<void> =>
  request<void>("/settings/model_overrides", {
    method: "PUT",
    body: JSON.stringify({ overrides }),
  });

/**
 * Update one role's override, preserving every other role in
 * `currentOverrides`. The backend PUT replaces the full map, so the
 * caller must pass in the current snapshot's map for safe merge.
 */
export const setModelOverride = (
  role: string,
  provider: string,
  model: string,
  currentOverrides: ModelOverridesMap,
): Promise<void> =>
  setModelOverrides({ ...currentOverrides, [role]: { provider, model } });

export const setSearchProvider = (provider: SearchProviderName): Promise<void> =>
  request<void>("/settings/search_provider", {
    method: "PUT",
    body: JSON.stringify({ provider }),
  });

export const setMaxStageRetries = (value: number): Promise<void> =>
  request<void>("/settings/max_stage_retries", {
    method: "PUT",
    body: JSON.stringify({ value }),
  });

// ---------------------------------------------------------------------------
// Ping (M2.6 smoke endpoint — used by "Test connection" buttons)
// ---------------------------------------------------------------------------

export const pingLLM = (role: string, prompt = "ping"): Promise<PingResponse> =>
  request<PingResponse>("/ping", {
    method: "POST",
    body: JSON.stringify({ prompt, role }),
  });

export const testSearchProvider = (query = "test"): Promise<SearchHealthResponse> =>
  request<SearchHealthResponse>(`/health/search?q=${encodeURIComponent(query)}`);

export const getTasks = (): Promise<TaskTypeInfo[]> => request<TaskTypeInfo[]>("/tasks");

export const uploadDocument = async (file: File): Promise<DocumentInfo> => {
  const form = new FormData();
  form.append("file", file);

  const res = await fetch(`${BASE_URL}/documents`, {
    method: "POST",
    body: form,
  });

  if (!res.ok) {
    let detail: string;
    try {
      const body = (await res.json()) as { detail?: unknown };
      detail =
        typeof body.detail === "string"
          ? body.detail
          : body.detail !== undefined
            ? JSON.stringify(body.detail)
            : `${res.status} ${res.statusText}`;
    } catch {
      detail = `${res.status} ${res.statusText}`;
    }
    throw new ApiRequestError(res.status, detail);
  }

  return (await res.json()) as DocumentInfo;
};

export const deleteDocument = (documentId: string): Promise<void> =>
  request<void>(`/documents/${documentId}`, {
    method: "DELETE",
  });

export const createRun = (body: {
  task_type: string;
  goal: string;
  document_ids: string[];
}): Promise<CreateRunResponse> =>
  request<CreateRunResponse>("/runs", {
    method: "POST",
    body: JSON.stringify(body),
  });

export const getRun = (runId: string): Promise<RunInfoResponse> =>
  request<RunInfoResponse>(`/runs/${runId}`);

export const submitRunAnswers = (
  runId: string,
  answers: Record<string, string>,
): Promise<void> =>
  request<void>(`/runs/${runId}/answers`, {
    method: "POST",
    body: JSON.stringify({ answers }),
  });

export const cancelRun = (runId: string): Promise<void> =>
  request<void>(`/runs/${runId}/cancel`, {
    method: "POST",
  });

export const getRunArtifact = (
  runId: string,
  artifactPath: string,
): Promise<ArtifactContentResponse> =>
  request<ArtifactContentResponse>(
    `/runs/${runId}/artifacts/${artifactPath}`,
  );

export const getRunEvidence = (runId: string): Promise<EvidenceListResponse> =>
  request<EvidenceListResponse>(`/runs/${runId}/evidence`);
