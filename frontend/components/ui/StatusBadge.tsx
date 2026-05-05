type StatusTone = "ok" | "warn" | "err";

export function StatusBadge({ label, tone }: { label: string; tone: StatusTone }) {
  return <span className={`badge ${tone}`}>{label}</span>;
}
