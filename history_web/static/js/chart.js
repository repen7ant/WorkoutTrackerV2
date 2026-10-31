import { cssColor } from "./dom.js";
import { formatLongDate, formatSet, formatValue, parseDate } from "./format.js";

let chart = null;

function withAlpha(hex, alpha) {
  const match = /^#([0-9a-f]{6})$/i.exec(hex);
  if (!match) return "transparent";
  const n = parseInt(match[1], 16);
  return `rgba(${n >> 16}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`;
}

export function clearChart() {
  if (chart) chart.destroy();
  chart = null;
}

// from — начало оси X: начало выбранного периода или первая тренировка
export function drawChart(canvas, points, metric, from) {
  clearChart();
  // ось X — настоящее время: перерыв в месяц не должен выглядеть как соседний день
  const to = Math.max(Date.now(), parseDate(points[points.length - 1].date).getTime());
  const long = to - from > 180 * 24 * 3600 * 1000;
  const tickFormat = long ? { month: "short", year: "2-digit" } : { day: "numeric", month: "short" };

  const accent = cssColor("--accent");
  const hint = cssColor("--hint");
  const text = cssColor("--text");
  chart = new window.Chart(canvas, {
    type: "line",
    data: {
      datasets: [{
        data: points.map((p) => ({ x: parseDate(p.date).getTime(), y: p.value })),
        borderColor: accent,
        borderWidth: 2.5,
        cubicInterpolationMode: "monotone",
        fill: "start",
        backgroundColor: ({ chart: c }) => {
          if (!c.chartArea) return "transparent";
          const gradient = c.ctx.createLinearGradient(0, c.chartArea.top, 0, c.chartArea.bottom);
          gradient.addColorStop(0, withAlpha(accent, 0.25));
          gradient.addColorStop(1, withAlpha(accent, 0));
          return gradient;
        },
        pointRadius: points.length === 1 ? 4 : 0,
        pointBackgroundColor: accent,
        pointHoverRadius: 5,
        pointHoverBackgroundColor: accent,
        pointHoverBorderColor: cssColor("--section"),
        pointHoverBorderWidth: 2,
      }],
    },
    options: {
      animation: false,
      maintainAspectRatio: false,
      // касание в любом месте показывает ближайшую тренировку
      interaction: { mode: "nearest", axis: "x", intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: cssColor("--section"),
          titleColor: text,
          bodyColor: text,
          borderColor: cssColor("--separator"),
          borderWidth: 1,
          cornerRadius: 8,
          padding: 10,
          displayColors: false,
          callbacks: {
            title: (items) => formatLongDate(points[items[0].dataIndex].date),
            label: (ctx) => points[ctx.dataIndex].sets.map(formatSet),
          },
        },
      },
      scales: {
        x: {
          type: "linear",
          min: from,
          max: to,
          border: { display: false },
          grid: { display: false },
          ticks: {
            color: hint,
            maxRotation: 0,
            autoSkipPadding: 16,
            maxTicksLimit: 5,
            callback: (value) => new Date(value).toLocaleDateString("en-GB", tickFormat),
          },
        },
        y: {
          border: { display: false },
          grid: { color: cssColor("--separator") },
          ticks: {
            color: hint,
            maxTicksLimit: 5,
            callback: (value) => (metric === "seconds" ? formatValue(value, "seconds") : value),
          },
        },
      },
    },
  });
}
