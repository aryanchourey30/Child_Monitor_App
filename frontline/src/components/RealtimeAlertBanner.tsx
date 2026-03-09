import type { RealtimeAlertViewModel } from "../types/api";
import { formatDateTime, toRiskClass } from "../utils/format";

interface RealtimeAlertBannerProps {
  alert: RealtimeAlertViewModel;
}

export function RealtimeAlertBanner({ alert }: RealtimeAlertBannerProps) {
  if (!alert.shouldAlert) {
    return null;
  }

  return (
    <section className={`card realtime-alert ${toRiskClass(alert.riskLevel)}`}>
      <h3>Live Alert</h3>
      <p><strong>Reason:</strong> {alert.reason}</p>
      <p><strong>Risk:</strong> {alert.riskLevel}</p>
      <p><strong>Activity:</strong> {alert.activity || "Unknown"}</p>
      <p><strong>Time:</strong> {formatDateTime(alert.timestamp)}</p>
      <p><strong>Summary:</strong> {alert.sceneSummary}</p>
      <p><strong>Action:</strong> {alert.recommendedAction}</p>
    </section>
  );
}
