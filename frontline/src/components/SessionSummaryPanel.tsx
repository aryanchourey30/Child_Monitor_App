import type { SessionSummaryViewModel } from "../types/api";
import { formatDateTime, toRiskClass } from "../utils/format";

interface SessionSummaryPanelProps {
  session?: SessionSummaryViewModel | null;
}

export function SessionSummaryPanel({ session }: SessionSummaryPanelProps) {
  return (
    <section className="card">
      <h3>Session Summary</h3>
      {!session ? (
        <p className="muted">No session summary available.</p>
      ) : (
        <dl className="summary-grid">
          <dt>Session ID</dt>
          <dd>{session.sessionId}</dd>
          <dt>Frames Processed</dt>
          <dd>{session.framesProcessed}</dd>
          <dt>Dominant State</dt>
          <dd>{session.dominantState}</dd>
          <dt>Final Risk</dt>
          <dd><span className={`badge ${toRiskClass(session.finalRiskLevel)}`}>{session.finalRiskLevel}</span></dd>
          <dt>Max Risk Score</dt>
          <dd>{session.maxRiskScore.toFixed(2)}</dd>
          <dt>Start</dt>
          <dd>{formatDateTime(session.startTime)}</dd>
          <dt>End</dt>
          <dd>{formatDateTime(session.endTime)}</dd>
        </dl>
      )}
    </section>
  );
}
