import type { EventViewModel } from "../types/api";
import { formatDateTime, toRiskClass, truncate } from "../utils/format";

interface AlertsPanelProps {
  alerts: EventViewModel[];
}

export function AlertsPanel({ alerts }: AlertsPanelProps) {
  return (
    <section className="card">
      <h3>Recent Alerts</h3>
      {alerts.length === 0 ? (
        <p className="muted">No events available.</p>
      ) : (
        <div className="alert-list">
          {alerts.slice(0, 8).map((event) => (
            <article key={event.id} className="alert-item">
              <p className="muted">{formatDateTime(event.timestamp)}</p>
              <p className={`badge ${toRiskClass(event.riskLevel)}`}>{event.riskLevel}</p>
              <p>{truncate(event.sceneDescription, 80)}</p>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
