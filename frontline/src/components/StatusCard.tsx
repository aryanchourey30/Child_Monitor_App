import { toRiskClass } from "../utils/format";

interface StatusCardProps {
  title: string;
  value: string;
  riskLevel?: string;
}

export function StatusCard({ title, value, riskLevel }: StatusCardProps) {
  return (
    <section className="card status-card">
      <p className="card-label">{title}</p>
      <p className={`card-value ${riskLevel ? toRiskClass(riskLevel) : ""}`}>{value}</p>
    </section>
  );
}
