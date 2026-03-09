import type { EventViewModel } from "../types/api";
import { formatDateTime, toRiskClass, truncate } from "../utils/format";

interface EventTableProps {
  events: EventViewModel[];
  onView: (event: EventViewModel) => void;
}

export function EventTable({ events, onView }: EventTableProps) {
  if (events.length === 0) {
    return <p className="card muted">No events available.</p>;
  }

  return (
    <div className="table-wrap card">
      <table>
        <thead>
          <tr>
            <th>Timestamp</th>
            <th>Frame ID</th>
            <th>Baby Visible</th>
            <th>Activity</th>
            <th>Risk</th>
            <th>Scene</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {events.map((event) => (
            <tr key={event.id}>
              <td>{formatDateTime(event.timestamp)}</td>
              <td>{event.frameId}</td>
              <td>{String(event.babyVisible)}</td>
              <td>{event.babyActivity || "Unknown"}</td>
              <td>
                <span className={`badge ${toRiskClass(event.riskLevel)}`}>{event.riskLevel}</span>
              </td>
              <td>{truncate(event.sceneDescription, 90)}</td>
              <td>
                <button type="button" onClick={() => onView(event)}>
                  View
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
