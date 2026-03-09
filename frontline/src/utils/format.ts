export function formatDateTime(value?: string | null): string {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

export function toRiskClass(level?: string): string {
  switch ((level ?? "unknown").toLowerCase()) {
    case "low":
      return "risk-low";
    case "medium":
      return "risk-medium";
    case "high":
      return "risk-high";
    case "critical":
      return "risk-critical";
    default:
      return "risk-unknown";
  }
}

export function truncate(value: string | null | undefined, max = 96): string {
  if (!value) {
    return "-";
  }
  return value.length > max ? `${value.slice(0, max)}...` : value;
}
