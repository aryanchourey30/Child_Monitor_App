import { useEffect, useMemo, useState } from "react";
import { apiClient } from "../api/client";
import { toEventViewModel, toSessionSummaryViewModel } from "../api/adapters";
import { ChartsPanel } from "../components/ChartsPanel";
import { EventDetailModal } from "../components/EventDetailModal";
import { EventTable } from "../components/EventTable";
import { FiltersBar } from "../components/FiltersBar";
import type { EventViewModel, RawEventRecord, RawSessionSummary, SessionSummaryViewModel } from "../types/api";
import { formatDateTime, toRiskClass } from "../utils/format";

interface Filters {
  risk: string;
  babyVisible: string;
  activity: string;
  start: string;
  end: string;
}

const defaultFilters: Filters = {
  risk: "",
  babyVisible: "",
  activity: "",
  start: "",
  end: "",
};

function toCsv(events: EventViewModel[]): string {
  const rows = [
    ["timestamp", "event_id", "risk_level", "activity", "scene_description", "recommended_action"],
    ...events.map((event) => [
      event.timestamp,
      event.id,
      event.riskLevel,
      event.babyActivity,
      event.sceneDescription.replace(/\n/g, " "),
      event.recommendedAction.replace(/\n/g, " "),
    ]),
  ];
  return rows.map((row) => row.map((v) => `"${String(v).replace(/"/g, '""')}"`).join(",")).join("\n");
}

export function HistoryPage() {
  const [filters, setFilters] = useState<Filters>(defaultFilters);
  const [selectedEvent, setSelectedEvent] = useState<EventViewModel | null>(null);
  const [rawEvents, setRawEvents] = useState<RawEventRecord[]>([]);
  const [rawSessions, setRawSessions] = useState<RawSessionSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const [events, sessions] = await Promise.all([apiClient.getEvents(200), apiClient.getSessions(50)]);
        setRawEvents(events);
        setRawSessions(sessions);
        setError(null);
      } catch (err) {
        const message = err instanceof Error ? err.message : "Failed to load history";
        setError(message);
      } finally {
        setLoading(false);
      }
    };

    void load();
  }, []);

  const eventVMs = useMemo(() => rawEvents.map(toEventViewModel), [rawEvents]);
  const sessionVMs: SessionSummaryViewModel[] = useMemo(
    () => rawSessions.map(toSessionSummaryViewModel),
    [rawSessions]
  );

  const filteredEvents = useMemo(() => {
    return eventVMs.filter((event) => {
      if (filters.risk && event.riskLevel !== filters.risk) {
        return false;
      }
      if (filters.babyVisible) {
        if (String(event.babyVisible) !== filters.babyVisible) {
          return false;
        }
      }
      if (filters.activity && !event.babyActivity.toLowerCase().includes(filters.activity.toLowerCase())) {
        return false;
      }
      if (filters.start && new Date(event.timestamp) < new Date(filters.start)) {
        return false;
      }
      if (filters.end && new Date(event.timestamp) > new Date(filters.end)) {
        return false;
      }
      return true;
    });
  }, [eventVMs, filters]);

  const exportCsv = () => {
    const blob = new Blob([toCsv(filteredEvents)], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "guardianbaby-events.csv";
    link.click();
    URL.revokeObjectURL(url);
  };

  const exportSessionsJson = () => {
    const blob = new Blob([JSON.stringify(sessionVMs, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "guardianbaby-sessions.json";
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="page-stack">
      <header>
        <h2>History & Analytics</h2>
      </header>

      <FiltersBar value={filters} onChange={setFilters} />

      <section className="actions-row">
        <button type="button" onClick={exportCsv}>Export Events CSV</button>
        <button type="button" onClick={exportSessionsJson}>Export Sessions JSON</button>
      </section>

      {error ? <p className="error">History error: {error}</p> : null}
      {loading ? <p className="muted">Loading events...</p> : <EventTable events={filteredEvents} onView={setSelectedEvent} />}

      <section className="card">
        <h3>Session Summaries</h3>
        {sessionVMs.length === 0 ? (
          <p className="muted">No session summaries available.</p>
        ) : (
          <div className="alert-list">
            {sessionVMs.map((session) => (
              <article className="alert-item" key={session.sessionId}>
                <p><strong>{session.sessionId}</strong></p>
                <p className="muted">
                  {formatDateTime(session.startTime)} {"->"} {formatDateTime(session.endTime)}
                </p>
                <p>Frames: {session.framesProcessed}</p>
                <p>Dominant: {session.dominantState}</p>
                <p>Risk: <span className={`badge ${toRiskClass(session.finalRiskLevel)}`}>{session.finalRiskLevel}</span></p>
              </article>
            ))}
          </div>
        )}
      </section>

      <ChartsPanel events={filteredEvents} />

      <EventDetailModal event={selectedEvent} onClose={() => setSelectedEvent(null)} />
    </div>
  );
}
