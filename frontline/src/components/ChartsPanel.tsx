import type { EventViewModel } from "../types/api";

interface ChartsPanelProps {
  events: EventViewModel[];
}

function summarize(events: EventViewModel[], key: (e: EventViewModel) => string) {
  const map = new Map<string, number>();
  for (const event of events) {
    const value = key(event) || "unknown";
    map.set(value, (map.get(value) ?? 0) + 1);
  }
  return Array.from(map.entries()).sort((a, b) => b[1] - a[1]);
}

function Bars({ title, data }: { title: string; data: Array<[string, number]> }) {
  const max = Math.max(1, ...data.map((item) => item[1]));
  return (
    <section className="card">
      <h3>{title}</h3>
      {data.length === 0 ? (
        <p className="muted">No data.</p>
      ) : (
        <div className="bars">
          {data.map(([label, count]) => (
            <div key={label} className="bar-row">
              <span>{label}</span>
              <div className="bar-track">
                <div className="bar-fill" style={{ width: `${(count / max) * 100}%` }} />
              </div>
              <strong>{count}</strong>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

export function ChartsPanel({ events }: ChartsPanelProps) {
  const riskDist = summarize(events, (event) => event.riskLevel || "unknown");
  const activityDist = summarize(events, (event) => event.babyActivity || "unknown");

  return (
    <div className="grid-two">
      <Bars title="Risk Distribution" data={riskDist} />
      <Bars title="Activity Distribution" data={activityDist} />
    </div>
  );
}
