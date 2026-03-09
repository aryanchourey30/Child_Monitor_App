interface ObservationsPanelProps {
  observations?: string[];
}

export function ObservationsPanel({ observations }: ObservationsPanelProps) {
  const items = observations?.filter(Boolean) ?? [];

  return (
    <section className="card">
      <h3>Observations</h3>
      {items.length === 0 ? (
        <p className="muted">No observations available.</p>
      ) : (
        <ul>
          {items.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      )}
    </section>
  );
}
