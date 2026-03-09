import type {
  RawEventRecord,
  RawFrameRecord,
  RawHealthResponse,
  RawLatestState,
  RawSessionSummary,
} from "../types/api";

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function fetchJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`);
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return (await response.json()) as T;
}

async function fetchOptional<T>(path: string, fallback: T): Promise<T> {
  try {
    return await fetchJson<T>(path);
  } catch {
    return fallback;
  }
}

export const apiClient = {
  // Source-of-truth backend routes currently implemented in app/api.py
  getHealth: () => fetchJson<RawHealthResponse>("/health"),
  getLatestState: () => fetchJson<RawLatestState>("/latest-state"),
  getEvents: (limit = 100) => fetchJson<RawEventRecord[]>(`/events?limit=${limit}`),
  getEvent: (id: string) => fetchJson<RawEventRecord>(`/events/${id}`),

  // Optional/compatibility routes: may not exist in every backend run.
  getSessions: (limit = 50) => fetchOptional<RawSessionSummary[]>(`/sessions?limit=${limit}`, []),
  getSession: (id: string) => fetchJson<RawSessionSummary>(`/sessions/${id}`),
  getCurrentSessionSummary: () => fetchOptional<RawSessionSummary | null>("/current-session-summary", null),
  getLatestFrame: () => fetchOptional<RawFrameRecord | null>("/latest-frame", null),
  getRecentFrames: (limit = 10) => fetchOptional<RawFrameRecord[]>(`/recent-frames?limit=${limit}`, []),
};
