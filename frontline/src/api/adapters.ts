import { API_BASE_URL } from "./client";
import type {
  EventViewModel,
  FrameLiveState,
  LatestMonitoringViewModel,
  RealtimeAlertViewModel,
  RawEventRecord,
  RawFrameRecord,
  RawLatestState,
  RawSessionSummary,
  RecentFrameViewModel,
  RiskLevel,
  SessionSummaryViewModel,
} from "../types/api";

const isDev = import.meta.env.DEV;
const FALLBACK_SCENE = "A frame was captured, but detailed visual interpretation is unavailable.";
const IMPORTANT_ACTIVITIES = new Set(["near_edge", "restless", "unsafe_exploration", "unsafe exploration"]);

function debug(message: string, payload?: unknown): void {
  if (isDev) {
    console.debug(`[frontline] ${message}`, payload);
  }
}

function warn(message: string, payload?: unknown): void {
  if (isDev) {
    console.warn(`[frontline] ${message}`, payload);
  }
}

function normalizeRisk(level: unknown): RiskLevel {
  const value = String(level ?? "unknown").toLowerCase();
  if (value === "low" || value === "medium" || value === "high" || value === "critical") {
    return value;
  }
  return "unknown";
}

export function toMediaUrl(path?: string | null): string | undefined {
  if (!path) {
    return undefined;
  }
  if (path.startsWith("http://") || path.startsWith("https://")) {
    return path;
  }

  const normalized = path.replace(/\\/g, "/");
  const idx = normalized.indexOf("data/");
  if (idx !== -1) {
    return `${API_BASE_URL}/media/${normalized.slice(idx + "data/".length)}`;
  }
  if (normalized.startsWith("/media/")) {
    return `${API_BASE_URL}${normalized}`;
  }

  warn("Unmappable media path; keeping raw path.", path);
  return undefined;
}

function normalizeObservations(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.map((item) => String(item)).filter(Boolean);
  }
  if (typeof value === "string" && value.trim()) {
    return [value.trim()];
  }
  return [];
}

export function toEventViewModel(event: RawEventRecord): EventViewModel {
  const activity = String(event.state_label ?? "unknown");
  const scene = String(event.explanation ?? "") || "No scene summary available";
  const riskReason = String(event.technical_summary ?? "") || "No risk reason available";
  const recommendedAction = String(event.caregiver_message ?? "") || "No recommendation available";
  const observations = normalizeObservations((event as Record<string, unknown>).observations);

  return {
    id: event.event_id,
    timestamp: event.timestamp,
    frameId: String(event.frame_id ?? event.event_id),
    babyVisible: activity !== "no_baby_visible",
    babyActivity: activity,
    riskLevel: normalizeRisk(event.risk_level),
    sceneDescription: scene,
    riskReason,
    recommendedAction,
    observations,
    imageUrl: toMediaUrl(event.snapshot_path),
    model: event.llm_model,
    usedLlm: Boolean(event.llm_used),
    error: String((event as Record<string, unknown>).error ?? "") || null,
    raw: event,
  };
}

export function toSessionSummaryViewModel(session: RawSessionSummary): SessionSummaryViewModel {
  return {
    sessionId: String(session.session_id ?? "unknown"),
    startTime: String(session.start_time ?? ""),
    endTime: String(session.end_time ?? ""),
    framesProcessed: Number(session.frames_processed ?? 0),
    dominantState: String(session.dominant_state ?? "unknown"),
    finalRiskLevel: normalizeRisk(session.final_risk_level),
    maxRiskScore: Number(session.max_risk_score ?? 0),
    explanation: String(session.explanation ?? "No session summary available"),
  };
}

export function toRecentFrameViewModel(frame: RawFrameRecord): RecentFrameViewModel {
  const framePath = String(frame.frame_path ?? "");
  return {
    frameId: String(frame.frame_id ?? framePath ?? "unknown"),
    framePath,
    frameUrl: toMediaUrl(String(frame.thumbnail_path ?? frame.frame_path ?? "")),
    timestamp: frame.timestamp,
  };
}

export function buildLatestMonitoringViewModel(
  latestState: RawLatestState | null,
  events: RawEventRecord[],
  sessions: RawSessionSummary[],
  recentFrames: RawFrameRecord[]
): LatestMonitoringViewModel {
  debug("latest-state payload", latestState);

  const latestFrame = latestState?.frame_result ?? {};
  const latestStateRecord = (latestState?.state ?? {}) as Record<string, unknown>;
  const liveAnalysis = latestState?.live_analysis ?? {};
  const latestEvent = events[0];

  const frameScene = String(latestFrame.scene_description ?? "");
  const liveScene = String(liveAnalysis.scene_summary ?? "");
  const stateScene = String(latestStateRecord.explanation ?? "");
  const eventScene = String(latestEvent?.explanation ?? "");
  const sceneCandidates = [frameScene, liveScene, stateScene, eventScene].filter(Boolean);
  const nonFallbackScene = sceneCandidates.find((text) => text && text !== FALLBACK_SCENE);
  const sceneDescription = nonFallbackScene || sceneCandidates[0] || "No scene summary available";

  const riskReason =
    String(latestFrame.risk_reason ?? "") ||
    String(liveAnalysis.risk_reason ?? "") ||
    String(latestStateRecord.technical_summary ?? "") ||
    latestEvent?.technical_summary ||
    "No risk reason available";

  const recommendedAction =
    String(latestFrame.recommended_action ?? "") ||
    String(liveAnalysis.recommended_action ?? "") ||
    String(latestStateRecord.caregiver_message ?? "") ||
    latestEvent?.caregiver_message ||
    "No recommendation available";

  const observations = normalizeObservations(latestFrame.observations ?? liveAnalysis.observations);
  if (observations.length === 0) {
    warn("Dashboard latest-state payload missing observations; using empty fallback.", latestState);
  }

  const latestFramePath = String(latestFrame.frame_path ?? "") || recentFrames[0]?.frame_path || "";
  const latestFrameUrl = toMediaUrl(latestFramePath);

  const fallbackActivity = String(
    latestFrame.baby_activity ??
      liveAnalysis.activity ??
      latestStateRecord.state_label ??
      latestEvent?.state_label ??
      "Unknown"
  );
  const risk = normalizeRisk(
    latestFrame.risk_level ?? liveAnalysis.risk_level ?? latestStateRecord.risk_level ?? latestEvent?.risk_level
  );

  const sessionRaw = latestState?.session_summary ?? sessions[0] ?? null;
  const sessionSummary = sessionRaw ? toSessionSummaryViewModel(sessionRaw) : null;

  return {
    latestFrameUrl,
    latestFramePath: latestFramePath || undefined,
    latestFrameTimestamp: String(latestFrame.timestamp ?? latestStateRecord.timestamp ?? latestEvent?.timestamp ?? "") || undefined,
    sceneDescription,
    babyVisible: Boolean(
      latestFrame.baby_visible ?? liveAnalysis.baby_visible ?? latestStateRecord.baby_detected ?? fallbackActivity !== "no_baby_visible"
    ),
    babyActivity: String(fallbackActivity || "Unknown"),
    riskLevel: risk,
    riskReason,
    observations,
    recommendedAction,
    lastUpdateTime: String(latestFrame.timestamp ?? latestStateRecord.timestamp ?? latestEvent?.timestamp ?? "") || undefined,
    sessionSummary,
  };
}

export function buildFrameLiveState(
  latestState: RawLatestState | null,
  events: RawEventRecord[],
  recentFrames: RawFrameRecord[]
): FrameLiveState {
  const latest = buildLatestMonitoringViewModel(latestState, events, [], recentFrames);
  return {
    frameId: String(
      latestState?.frame_result?.frame_id ??
        latestState?.live_analysis?.frame_id ??
        events[0]?.frame_id ??
        "unknown"
    ),
    timestamp: latest.lastUpdateTime,
    sceneDescription: latest.sceneDescription,
    babyVisible: latest.babyVisible,
    babyActivity: latest.babyActivity,
    riskLevel: latest.riskLevel,
    riskReason: latest.riskReason,
    observations: latest.observations,
    recommendedAction: latest.recommendedAction,
    framePath: latest.latestFramePath,
    frameUrl: latest.latestFrameUrl,
  };
}

export function buildRealtimeAlert(
  latest: LatestMonitoringViewModel,
  events: EventViewModel[]
): RealtimeAlertViewModel {
  const highRisk = latest.riskLevel === "high" || latest.riskLevel === "critical";
  const importantActivity = IMPORTANT_ACTIVITIES.has((latest.babyActivity || "").toLowerCase());
  const latestEvent = events[0];
  const eventRisk = latestEvent?.riskLevel === "high" || latestEvent?.riskLevel === "critical";
  const eventActivity = IMPORTANT_ACTIVITIES.has((latestEvent?.babyActivity || "").toLowerCase());
  const shouldAlert = highRisk || importantActivity || eventRisk || eventActivity;

  let reason = "No active alert.";
  if (highRisk || eventRisk) {
    reason = "High risk detected.";
  } else if (importantActivity || eventActivity) {
    reason = "Important activity detected.";
  }

  return {
    shouldAlert,
    reason,
    timestamp: latest.lastUpdateTime ?? latestEvent?.timestamp,
    riskLevel: latest.riskLevel,
    activity: latest.babyActivity,
    sceneSummary: latest.sceneDescription,
    recommendedAction: latest.recommendedAction,
  };
}

export function deriveRecentFrames(
  recentFrames: RawFrameRecord[],
  latestState: RawLatestState | null,
  events: RawEventRecord[]
): RecentFrameViewModel[] {
  if (recentFrames.length > 0) {
    debug("Using /recent-frames payload", recentFrames);
    return recentFrames.map(toRecentFrameViewModel).filter((frame) => Boolean(frame.framePath));
  }

  warn("Recent frames derived from latest-state/events because /recent-frames is empty.");
  const list: RecentFrameViewModel[] = [];
  const fromLatest = latestState?.frame_result?.frame_path;
  if (fromLatest) {
    list.push({
      frameId: String(latestState?.frame_result?.frame_id ?? "latest"),
      framePath: fromLatest,
      frameUrl: toMediaUrl(fromLatest),
      timestamp: latestState?.frame_result?.timestamp,
    });
  }

  for (const event of events) {
    if (!event.snapshot_path) {
      continue;
    }
    list.push({
      frameId: String(event.frame_id ?? event.event_id),
      framePath: event.snapshot_path,
      frameUrl: toMediaUrl(event.snapshot_path),
      timestamp: event.timestamp,
    });
    if (list.length >= 10) {
      break;
    }
  }

  return list;
}
