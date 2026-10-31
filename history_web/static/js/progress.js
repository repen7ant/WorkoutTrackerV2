import { api } from "./api.js";
import { clearChart, drawChart } from "./chart.js";
import { el, setTab, show } from "./dom.js";
import { formatShortDate, formatValue, parseDate } from "./format.js";

const PERIODS = [["1M", 1], ["3M", 3], ["6M", 6], ["1Y", 12], ["All", null]];
let selectedPeriod = "3M";
let selectedExercise = null;

export async function showProgress() {
  setTab("progress");
  const exercises = await api("GET", "/api/exercises");
  if (!exercises.length) {
    show(el("p", { className: "empty", textContent: "No exercises yet. Log a workout with /workout in the chat." }));
    return;
  }

  const select = el("select", {},
    ...exercises.map((ex) => el("option", { value: ex.id, textContent: ex.name })),
  );
  if (exercises.some((ex) => String(ex.id) === selectedExercise)) select.value = selectedExercise;
  const summary = el("div", { className: "summary" });
  const canvas = el("canvas");
  let data = null;

  const periods = el("div", { className: "segmented" }, ...PERIODS.map(([name]) => el("button", {
    textContent: name,
    onclick: () => {
      selectedPeriod = name;
      markPeriod();
      if (data) drawProgress(data, summary, canvas);
    },
  })));
  function markPeriod() {
    for (const button of periods.children) {
      button.classList.toggle("active", button.textContent === selectedPeriod);
    }
  }
  markPeriod();

  async function load() {
    selectedExercise = select.value;
    data = await api("GET", `/api/exercises/${select.value}/progress`);
    drawProgress(data, summary, canvas);
  }
  select.onchange = load;
  show(el("section", { className: "section" },
    select, summary, periods, el("div", { className: "chart" }, canvas),
  ));
  await load();
}

function periodStart() {
  const months = new Map(PERIODS).get(selectedPeriod);
  if (months === null) return null;
  const start = new Date();
  start.setHours(0, 0, 0, 0);
  start.setMonth(start.getMonth() - months);
  return start;
}

function renderSummary(summary, points, metric) {
  const first = points[0];
  const last = points[points.length - 1];
  // вычитание float даёт хвосты вроде 0.30000000000000004
  const change = Math.round((last.value - first.value) * 100) / 100;
  let trend = "Only one workout in this period";
  if (points.length > 1) {
    const sign = change > 0 ? "+" : change < 0 ? "−" : "";
    trend = change === 0
      ? `Same as on ${formatShortDate(first.date)}`
      : `${sign}${formatValue(Math.abs(change), metric)} since ${formatShortDate(first.date)}`;
  }
  summary.replaceChildren(
    el("div", { className: "summary-value", textContent: formatValue(last.value, metric) }),
    el("div", { className: "summary-trend", textContent: trend }),
  );
}

function drawProgress(data, summary, canvas) {
  clearChart();
  const start = periodStart();
  const points = data.points.filter((p) => start === null || parseDate(p.date) >= start);
  canvas.parentElement.hidden = !points.length;
  if (!points.length) {
    summary.replaceChildren(el("p", { className: "empty", textContent: "No workouts in this period." }));
    return;
  }
  renderSummary(summary, points, data.metric);

  const from = start === null ? parseDate(points[0].date).getTime() : start.getTime();
  drawChart(canvas, points, data.metric, from);
}
