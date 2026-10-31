"use strict";

const tg = window.Telegram.WebApp;
// вне Telegram (dev_link в браузере) нативных попапов нет
const inTelegram = tg.platform !== "unknown";

const view = document.getElementById("view");
const tabs = {
  workouts: document.getElementById("tab-workouts"),
  progress: document.getElementById("tab-progress"),
};
const UNITS = { weight: "kg", reps: "reps", seconds: "sec" };

let listView = null;
let listScroll = 0;
let chart = null;
let selectedExercise = null;

function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  Object.assign(node, props);
  node.append(...children);
  return node;
}

function notify(message) {
  if (inTelegram) tg.showAlert(message);
  else window.alert(message);
}

async function api(method, path, body) {
  const options = { method, headers: { Authorization: `tma ${tg.initData}` } };
  if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  const response = await fetch(path, options);
  if (response.status === 401) {
    notify("Session expired. Reopen the app from /history.");
    throw new Error("unauthorized");
  }
  const data = response.status === 204 ? null : await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = data.error || `Request failed (${response.status})`;
    notify(message);
    throw new Error(message);
  }
  return data;
}

function formatDate(iso) {
  const [y, m, d] = iso.split("-");
  return `${d}-${m}-${y.slice(2)}`;
}

function formatSet(set) {
  const weight = set.weight === null ? "BW" : `${set.weight}kg`;
  if (set.seconds === null) return `${weight} x ${set.reps}`;
  const seconds = String(set.seconds % 60).padStart(2, "0");
  return `${weight} x ${Math.floor(set.seconds / 60)}:${seconds}`;
}

function cssColor(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function setTab(name) {
  for (const [key, button] of Object.entries(tabs)) {
    button.classList.toggle("active", key === name);
  }
}

async function showList(refresh = false) {
  setTab("workouts");
  if (listView && !refresh) {
    view.replaceChildren(listView);
    window.scrollTo(0, listScroll);
    return;
  }

  const list = el("ul");
  const more = el("button", { textContent: "Load more", hidden: true });
  let page = 0;

  async function loadPage() {
    const data = await api("GET", `/api/workouts?page=${page + 1}`);
    page = data.page;
    for (const w of data.items) {
      const title = w.notes ? `${formatDate(w.date)} — ${w.notes}` : formatDate(w.date);
      list.append(el("li", {}, el("button", {
        className: "row",
        textContent: title,
        onclick: () => showWorkout(w.id),
      })));
    }
    more.hidden = page >= data.total_pages;
  }

  more.onclick = loadPage;
  listView = el("div", {}, list, more);
  view.replaceChildren(listView);
  await loadPage();
  if (!list.children.length) {
    listView.replaceChildren(el("p", { className: "hint", textContent: "No workouts yet." }));
  }
}

async function showWorkout(id) {
  if (view.firstChild === listView) listScroll = window.scrollY;
  const w = await api("GET", `/api/workouts/${id}`);
  const actions = el("div", { className: "actions" },
    el("button", { textContent: "← Back", onclick: () => showList() }),
  );
  const content = [actions, el("h2", { textContent: formatDate(w.date) })];
  if (w.notes) content.push(el("p", { className: "hint", textContent: w.notes }));
  for (const ex of w.exercises) {
    content.push(
      el("h3", { textContent: ex.name }),
      el("ol", {}, ...ex.sets.map((s, i) => el("li", { textContent: `${i + 1}. ${formatSet(s)}` }))),
    );
  }
  view.replaceChildren(...content);
  window.scrollTo(0, 0);
  return { workout: w, actions };
}

async function showProgress() {
  setTab("progress");
  const exercises = await api("GET", "/api/exercises");
  if (!exercises.length) {
    view.replaceChildren(el("p", { className: "hint", textContent: "No exercises yet." }));
    return;
  }

  const select = el("select", {},
    ...exercises.map((ex) => el("option", { value: ex.id, textContent: ex.name })),
  );
  if (exercises.some((ex) => String(ex.id) === selectedExercise)) select.value = selectedExercise;
  const canvas = el("canvas");
  select.onchange = () => drawProgress(select.value, canvas);
  view.replaceChildren(select, el("div", { className: "chart" }, canvas));
  await drawProgress(select.value, canvas);
}

async function drawProgress(exerciseId, canvas) {
  selectedExercise = exerciseId;
  const data = await api("GET", `/api/exercises/${exerciseId}/progress`);
  const accent = cssColor("--accent");
  const hint = cssColor("--hint");
  if (chart) chart.destroy();
  chart = new Chart(canvas, {
    type: "line",
    data: {
      labels: data.points.map((p) => formatDate(p.date)),
      datasets: [{
        data: data.points.map((p) => p.value),
        borderColor: accent,
        backgroundColor: accent,
        pointRadius: 3,
      }],
    },
    options: {
      animation: false,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: { label: (ctx) => data.points[ctx.dataIndex].sets.map(formatSet) },
        },
      },
      scales: {
        x: { ticks: { color: hint }, grid: { display: false } },
        y: {
          title: { display: true, text: UNITS[data.metric], color: hint },
          ticks: { color: hint },
          grid: { color: cssColor("--line") },
        },
      },
    },
  });
}

tabs.workouts.onclick = () => showList();
tabs.progress.onclick = () => showProgress();
tg.ready();
tg.expand();
showList();
