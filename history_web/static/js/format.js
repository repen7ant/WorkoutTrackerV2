export function parseDate(iso) {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d);
}

export function formatLongDate(iso) {
  return parseDate(iso).toLocaleDateString("en-GB", {
    weekday: "long", day: "numeric", month: "long", year: "numeric",
  });
}

export function formatShortDate(iso) {
  return parseDate(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short" });
}

export function formatSet(set) {
  const weight = set.weight === null ? "BW" : `${set.weight}kg`;
  if (set.seconds === null) return `${weight} x ${set.reps}`;
  const seconds = String(set.seconds % 60).padStart(2, "0");
  return `${weight} x ${Math.floor(set.seconds / 60)}:${seconds}`;
}

export function formatValue(value, metric) {
  if (metric === "weight") return `${value} kg`;
  if (metric === "reps") return `${value} reps`;
  const seconds = String(Math.abs(value) % 60).padStart(2, "0");
  return `${Math.floor(Math.abs(value) / 60)}:${seconds}`;
}
