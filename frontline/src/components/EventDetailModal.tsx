import type { EventViewModel } from "../types/api";
import { formatDateTime, toRiskClass } from "../utils/format";

interface EventDetailModalProps {
  event: EventViewModel | null;
  onClose: () => void;
}

export function EventDetailModal({ event, onClose }: EventDetailModalProps) {
  if (!event) {
    return null;
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>Event Detail</h3>
          <button type="button" onClick={onClose}>Close</button>
        </div>
        <p><strong>Timestamp:</strong> {formatDateTime(event.timestamp)}</p>
        <p><strong>Event ID:</strong> {event.id}</p>
        <p><strong>Risk:</strong> <span className={`badge ${toRiskClass(event.riskLevel)}`}>{event.riskLevel}</span></p>
        <p><strong>Scene:</strong> {event.sceneDescription}</p>
        <p><strong>Observations:</strong> {event.observations.length > 0 ? event.observations.join(", ") : "No observations available"}</p>
        <p><strong>Risk Reason:</strong> {event.riskReason}</p>
        <p><strong>Recommended Action:</strong> {event.recommendedAction}</p>
        <p><strong>Model:</strong> {event.model ?? "-"}</p>
        <p><strong>Used LLM:</strong> {String(event.usedLlm)}</p>
        <p><strong>Error:</strong> {event.error ?? "-"}</p>
        {event.imageUrl ? <img src={event.imageUrl} className="frame-image" alt="snapshot" /> : null}
      </div>
    </div>
  );
}
