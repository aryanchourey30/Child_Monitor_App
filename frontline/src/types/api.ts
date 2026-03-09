export type RiskLevel = "low" | "medium" | "high" | "critical" | "unknown";

// Raw backend contracts
export interface RawHealthResponse {
  status?: string;
  camera_connected?: boolean;
  detector_ready?: boolean;
  notification_ready?: boolean;
  db_writable?: boolean;
  graph_operational?: boolean;
  [key: string]: unknown;
}

export interface RawEventRecord {
  event_id: string;
  timestamp: string;
  event_type: string;
  risk_score: number;
  risk_level: RiskLevel;
  state_label: string;
  explanation: string;
  snapshot_path?: string | null;
  notification_sent?: boolean;
  acknowledged?: boolean;
  caregiver_message?: string | null;
  technical_summary?: string | null;
  llm_used?: boolean;
  llm_fallback_used?: boolean;
  llm_model?: string | null;
  detectors?: Record<string, unknown>;
  frame_id?: string;
  [key: string]: unknown;
}

export interface RawFrameAnalysis {
  frame_path?: string;
  frame_id?: string;
  timestamp?: string;
  scene_description?: string;
  baby_visible?: boolean;
  baby_activity?: string;
  risk_level?: RiskLevel;
  risk_reason?: string;
  observations?: string[] | string;
  recommended_action?: string;
  used_llm?: boolean;
  model?: string | null;
  error?: string | null;
  [key: string]: unknown;
}

export interface RawLatestState {
  frame_result?: RawFrameAnalysis;
  state?: Record<string, unknown>;
  session_summary?: RawSessionSummary;
  live_analysis?: {
    frame_id?: string;
    timestamp?: string;
    baby_visible?: boolean;
    activity?: string;
    risk_level?: RiskLevel;
    scene_summary?: string;
    risk_reason?: string;
    observations?: string[] | string;
    recommended_action?: string;
    used_llm?: boolean;
    model?: string | null;
    error?: string | null;
  };
  [key: string]: unknown;
}

export interface RawFrameRecord {
  frame_id?: string;
  frame_path?: string;
  timestamp?: string;
  thumbnail_path?: string;
  [key: string]: unknown;
}

export interface RawSessionSummary {
  session_id?: string;
  start_time?: string;
  end_time?: string;
  duration_seconds?: number;
  frames_processed?: number;
  subject_detected?: boolean;
  dominant_state?: string;
  final_risk_level?: RiskLevel;
  max_risk_score?: number;
  explanation?: string;
  events?: Array<Record<string, unknown>>;
  snapshot_paths?: string[];
  [key: string]: unknown;
}

// Normalized frontend view models
export interface EventViewModel {
  id: string;
  timestamp: string;
  frameId: string;
  babyVisible: boolean;
  babyActivity: string;
  riskLevel: RiskLevel;
  sceneDescription: string;
  riskReason: string;
  recommendedAction: string;
  observations: string[];
  imageUrl?: string;
  model?: string | null;
  usedLlm: boolean;
  error?: string | null;
  raw: RawEventRecord;
}

export interface SessionSummaryViewModel {
  sessionId: string;
  startTime: string;
  endTime: string;
  framesProcessed: number;
  dominantState: string;
  finalRiskLevel: RiskLevel;
  maxRiskScore: number;
  explanation: string;
}

export interface RecentFrameViewModel {
  frameId: string;
  framePath: string;
  frameUrl?: string;
  timestamp?: string;
}

export interface LatestMonitoringViewModel {
  latestFrameUrl?: string;
  latestFramePath?: string;
  latestFrameTimestamp?: string;
  sceneDescription: string;
  babyVisible: boolean;
  babyActivity: string;
  riskLevel: RiskLevel;
  riskReason: string;
  observations: string[];
  recommendedAction: string;
  lastUpdateTime?: string;
  sessionSummary?: SessionSummaryViewModel | null;
}

export interface RealtimeAlertViewModel {
  shouldAlert: boolean;
  reason: string;
  timestamp?: string;
  riskLevel: RiskLevel;
  activity: string;
  sceneSummary: string;
  recommendedAction: string;
}

export interface FrameLiveState {
  frameId: string;
  timestamp?: string;
  sceneDescription: string;
  babyVisible: boolean;
  babyActivity: string;
  riskLevel: RiskLevel;
  riskReason: string;
  observations: string[];
  recommendedAction: string;
  framePath?: string;
  frameUrl?: string;
}
