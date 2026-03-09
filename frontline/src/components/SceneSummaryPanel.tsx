interface SceneSummaryPanelProps {
  sceneDescription?: string;
  riskReason?: string;
}

export function SceneSummaryPanel({ sceneDescription, riskReason }: SceneSummaryPanelProps) {
  return (
    <section className="card">
      <h3>Scene Summary</h3>
      <p>{sceneDescription || "No scene summary yet."}</p>
      <p className="muted"><strong>Risk reason:</strong> {riskReason || "-"}</p>
    </section>
  );
}
