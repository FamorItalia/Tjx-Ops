export function formatDate(value: string | null | undefined): string {
  if (!value) return "-";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleDateString("it-IT");
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "-";
  const normalized = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$/.test(value) ? `${value}Z` : value;
  const d = new Date(normalized);
  if (Number.isNaN(d.getTime())) return value;
  const date = d.toLocaleDateString("it-IT");
  const time = d.toLocaleTimeString("it-IT", {
    hour12: false,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
  return `${date} ${time}`;
}

export function toNumber(value: string): number | null {
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

export function sum(values: number[]): number {
  return values.reduce((acc, curr) => acc + curr, 0);
}

export function uniq<T>(list: T[]): T[] {
  return Array.from(new Set(list));
}
