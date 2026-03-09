import { useMemo, useState } from "react";
import { apiClient } from "../api/client";
import {
  buildFrameLiveState,
  buildRealtimeAlert,
  deriveRecentFrames,
  toEventViewModel,
  toSessionSummaryViewModel,
} from "../api/adapters";
import { AlertsPanel } from "../components/AlertsPanel";
import { LatestFramePanel } from "../components/LatestFramePanel";
import { ObservationsPanel } from "../components/ObservationsPanel";
import { RecentFramesStrip } from "../components/RecentFramesStrip";
import { RealtimeAlertBanner } from "../components/RealtimeAlertBanner";
import { SceneSummaryPanel } from "../components/SceneSummaryPanel";
import { SessionSummaryPanel } from "../components/SessionSummaryPanel";
import { StatusCard } from "../components/StatusCard";
import { usePolling } from "../hooks/usePolling";
import type { LatestMonitoringViewModel, RecentFrameViewModel } from "../types/api";
import { formatDateTime, toRiskClass } from "../utils/format";

export function DashboardPage() {
  const [selectedImage, setSelectedImage] = useState<string | null>(null);

  const latestStatePolling = usePolling({ fetcher: apiClient.getLatestState, intervalMs: 3000 });
  const eventsPolling = usePolling({ fetcher: () => apiClient.getEvents(20), intervalMs: 5000 });
  const currentSessionPolling = usePolling({ fetcher: apiClient.getCurrentSessionSummary, intervalMs: 5000 });
  const recentFramesPolling = usePolling({ fetcher: () => apiClient.getRecentFrames(10), intervalMs: 5000 });

  const eventVMs = useMemo(() => (eventsPolling.data ?? []).map(toEventViewModel), [eventsPolling.data]);

  const frameLiveState = useMemo(
    () => buildFrameLiveState(latestStatePolling.data ?? null, eventsPolling.data ?? [], recentFramesPolling.data ?? []),
    [latestStatePolling.data, eventsPolling.data, recentFramesPolling.data]
  );

  const currentSessionSummary = useMemo(
    () => (currentSessionPolling.data ? toSessionSummaryViewModel(currentSessionPolling.data) : null),
    [currentSessionPolling.data]
  );

  const recentFrameVMs: RecentFrameViewModel[] = useMemo(
    () => deriveRecentFrames(recentFramesPolling.data ?? [], latestStatePolling.data ?? null, eventsPolling.data ?? []),
    [recentFramesPolling.data, latestStatePolling.data, eventsPolling.data]
  );

  const alertStateAsLatestMonitoring: LatestMonitoringViewModel = {
    latestFrameUrl: frameLiveState.frameUrl,
    latestFramePath: frameLiveState.framePath,
    latestFrameTimestamp: frameLiveState.timestamp,
    sceneDescription: frameLiveState.sceneDescription,
    babyVisible: frameLiveState.babyVisible,
    babyActivity: frameLiveState.babyActivity,
    riskLevel: frameLiveState.riskLevel,
    riskReason: frameLiveState.riskReason,
    observations: frameLiveState.observations,
    recommendedAction: frameLiveState.recommendedAction,
    lastUpdateTime: frameLiveState.timestamp,
    sessionSummary: null,
  };

  const realtimeAlert = useMemo(
    () => buildRealtimeAlert(alertStateAsLatestMonitoring, eventVMs),
    [alertStateAsLatestMonitoring, eventVMs]
  );

  return (
    <div className="page-stack">
      <header>
        <h2>GuardianBaby</h2>
        <p className="muted">Live Monitoring Dashboard</p>
      </header>

      {latestStatePolling.error ? <p className="error">Latest state error: {latestStatePolling.error}</p> : null}
      <RealtimeAlertBanner alert={realtimeAlert} />

      <div className="grid-two">
        <LatestFramePanel
          imagePath={frameLiveState.frameUrl}
          timestamp={frameLiveState.timestamp}
          selectedImage={selectedImage}
        />
        <div className="card">
          <h3>Recommended Action</h3>
          <p className={`action-text ${toRiskClass(frameLiveState.riskLevel)}`}>{frameLiveState.recommendedAction}</p>
          <p className="muted">Last update: {formatDateTime(frameLiveState.timestamp)}</p>
        </div>
      </div>

      <div className="status-grid">
        <StatusCard title="Baby Visible" value={String(frameLiveState.babyVisible)} />
        <StatusCard title="Current Activity" value={frameLiveState.babyActivity || "Unknown"} />
        <StatusCard title="Risk Level" value={frameLiveState.riskLevel} riskLevel={frameLiveState.riskLevel} />
        <StatusCard title="Last Update Time" value={formatDateTime(frameLiveState.timestamp)} />
      </div>

      <div className="grid-two">
        <SceneSummaryPanel
          sceneDescription={frameLiveState.sceneDescription || "No scene summary available"}
          riskReason={frameLiveState.riskReason || "No risk reason available"}
        />
        <ObservationsPanel observations={frameLiveState.observations} />
      </div>

      <div className="grid-two">
        <AlertsPanel alerts={eventVMs} />
        <SessionSummaryPanel session={currentSessionSummary} />
      </div>

      <RecentFramesStrip frames={recentFrameVMs} onSelect={(path) => setSelectedImage(path)} />

      {latestStatePolling.loading || eventsPolling.loading ? <p className="muted">Refreshing dashboard...</p> : null}
    </div>
  );
}
