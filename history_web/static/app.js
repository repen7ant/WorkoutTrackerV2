"use strict";

const tg = window.Telegram.WebApp;
// вне Telegram (dev_link в браузере) нативных попапов нет
const inTelegram = tg.platform !== "unknown";

const view = document.getElementById("view");
const tabs = {
  workouts: document.getElementById("tab-workouts"),
  progress: document.getElementById("tab-progress"),
};

let listView = null;
let listScroll = 0;
let chart = null;
let selectedExercise = null;
const PERIODS = [["1M", 1], ["3M", 3], ["6M", 6], ["1Y", 12], ["All", null]];
let selectedPeriod = "3M";

function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  Object.assign(node, props);
  node.append(...children);
  return node;
}

function show(...nodes) {
  view.replaceChildren(...nodes);
  view.classList.remove("enter");
  void view.offsetWidth; // перезапуск анимации появления
  view.classList.add("enter");
}

function notify(message) {
  if (inTelegram) tg.showAlert(message);
  else window.alert(message);
}

function confirmAction(message) {
  return new Promise((resolve) => {
    if (inTelegram) tg.showConfirm(message, resolve);
    else resolve(window.confirm(message));
  });
}

async function api(method, path, body) {
  const options = { method, headers: { Authorization: `tma ${tg.initData}` } };
  if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  let response;
  try {
    response = await fetch(path, options);
  } catch (e) {
    notify("No connection. Check the network and try again.");
    throw e;
  }
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

function parseDate(iso) {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d);
}

function formatDate(iso) {
  const [y, m, d] = iso.split("-");
  return `${d}-${m}-${y.slice(2)}`;
}

function formatLongDate(iso) {
  return parseDate(iso).toLocaleDateString("en-GB", {
    weekday: "long", day: "numeric", month: "long", year: "numeric",
  });
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

function workoutRow(w) {
  const date = parseDate(w.date);
  const text = el("span", { className: "row-text" },
    el("span", { textContent: date.toLocaleDateString("en-GB", { weekday: "long" }) }),
  );
  if (w.notes) text.append(el("span", { className: "row-subtitle", textContent: w.notes }));
  return el("button", { className: "row", onclick: () => showWorkout(w.id) },
    el("span", { className: "day", textContent: date.getDate() }),
    text,
    el("span", { className: "chevron", textContent: "›" }),
  );
}

async function showList(refresh = false) {
  setTab("workouts");
  if (listView && !refresh) {
    show(listView);
    window.scrollTo(0, listScroll);
    return;
  }

  const groups = el("div");
  const more = el("button", { className: "more", textContent: "Load more", hidden: true });
  let page = 0;
  let month = null;
  let group = null;

  async function loadPage() {
    // без этого двойное нажатие загрузит одну страницу дважды
    more.disabled = true;
    try {
      const data = await api("GET", `/api/workouts?page=${page + 1}`);
      page = data.page;
      for (const w of data.items) {
        const title = parseDate(w.date).toLocaleDateString("en-GB", { month: "long", year: "numeric" });
        if (title !== month) {
          month = title;
          group = el("ul", { className: "section" });
          groups.append(el("h4", { className: "section-title", textContent: title }), group);
        }
        group.append(el("li", {}, workoutRow(w)));
      }
      more.hidden = page >= data.total_pages;
    } finally {
      more.disabled = false;
    }
  }

  more.onclick = loadPage;
  listView = el("div", {}, groups, more);
  try {
    await loadPage();
  } catch {
    // иначе вкладка останется пустой до перезапуска приложения
    listView = null;
    show(el("div", { className: "empty" },
      el("p", { textContent: "Workouts didn't load." }),
      el("button", { textContent: "Try again", onclick: () => showList(true) }),
    ));
    return;
  }
  if (!groups.children.length) {
    listView.replaceChildren(el("p", {
      className: "empty",
      textContent: "No workouts yet. Log one with /workout in the chat.",
    }));
  }
  show(listView);
}

async function showWorkout(id) {
  if (view.firstChild === listView) listScroll = window.scrollY;
  renderWorkout(await api("GET", `/api/workouts/${id}`));
}

function renderWorkout(w) {
  const head = el("div", { className: "workout-head" },
    el("h2", { textContent: formatLongDate(w.date) }),
  );
  if (w.notes) head.append(el("p", { className: "notes", textContent: w.notes }));
  const exercises = w.exercises.map((ex) => el("section", { className: "section" },
    el("h3", { textContent: ex.name }),
    el("ol", { className: "sets" }, ...ex.sets.map((s, i) => el("li", {},
      el("span", { className: "set-no", textContent: i + 1 }),
      el("span", { textContent: formatSet(s) }),
    ))),
  ));
  show(
    el("div", { className: "actions" },
      el("button", { textContent: "‹ Back", onclick: () => showList() }),
      el("span", { className: "spacer" }),
      el("button", { textContent: "Edit", onclick: () => showEdit(w) }),
      el("button", { className: "destructive", textContent: "Delete", onclick: () => removeWorkout(w.id) }),
    ),
    head,
    ...exercises,
  );
  window.scrollTo(0, 0);
}

async function removeWorkout(id) {
  if (!(await confirmAction("Delete this workout?"))) return;
  await api("DELETE", `/api/workouts/${id}`);
  listView = null;
  showList();
}

function parseWeight(text) {
  const value = text.trim().replace(",", ".");
  if (value === "" || value.toLowerCase() === "bw") return null;
  if (!/^\d+(\.\d+)?$/.test(value)) throw new Error(`Invalid weight: ${text}`);
  return Number(value);
}

function parseAmount(text, unit) {
  const value = text.trim();
  let amount = NaN;
  if (unit === "reps" && /^\d+$/.test(value)) amount = Number(value);
  if (unit === "sec") {
    const time = value.match(/^(\d+):([0-5]\d)$/);
    if (time) amount = Number(time[1]) * 60 + Number(time[2]);
    else if (/^\d+s?$/.test(value)) amount = parseInt(value, 10);
  }
  if (!(amount > 0)) throw new Error(unit === "reps" ? `Invalid reps: ${text}` : `Invalid time: ${text}`);
  return amount;
}

function draftSet(set) {
  const weight = set.weight === null ? "" : String(set.weight);
  if (set.seconds !== null) {
    const seconds = String(set.seconds % 60).padStart(2, "0");
    return { weight, amount: `${Math.floor(set.seconds / 60)}:${seconds}`, unit: "sec" };
  }
  return { weight, amount: String(set.reps), unit: "reps" };
}

function showEdit(workout) {
  // черновик со строками из полей: разбираем только при сохранении
  const draft = {
    date: workout.date,
    notes: workout.notes || "",
    exercises: workout.exercises.map((ex) => ({
      exercise_id: ex.exercise_id,
      name: ex.name,
      sets: ex.sets.map(draftSet),
    })),
  };

  function input(props, onInput) {
    return el("input", { ...props, oninput: (e) => onInput(e.target.value) });
  }

  function setRow(ex, set) {
    const unit = el("select", { onchange: (e) => { set.unit = e.target.value; } },
      el("option", { value: "reps", textContent: "reps" }),
      el("option", { value: "sec", textContent: "sec" }),
    );
    unit.value = set.unit;
    return el("div", { className: "set" },
      input({ value: set.weight, placeholder: "BW", inputMode: "decimal" }, (v) => { set.weight = v; }),
      el("span", { textContent: "x" }),
      input({ value: set.amount, inputMode: set.unit === "reps" ? "numeric" : "text" }, (v) => { set.amount = v; }),
      unit,
      el("button", {
        className: "icon",
        textContent: "✕",
        onclick: () => { ex.sets.splice(ex.sets.indexOf(set), 1); render(); },
      }),
    );
  }

  function move(index, step) {
    const target = index + step;
    if (target < 0 || target >= draft.exercises.length) return;
    const [ex] = draft.exercises.splice(index, 1);
    draft.exercises.splice(target, 0, ex);
    render();
  }

  function exerciseBlock(ex, index) {
    return el("section", { className: "section" },
      el("div", { className: "exercise-head" },
        el("h3", { textContent: ex.name }),
        el("button", { className: "icon", textContent: "↑", onclick: () => move(index, -1) }),
        el("button", { className: "icon", textContent: "↓", onclick: () => move(index, 1) }),
        el("button", {
          className: "icon",
          textContent: "✕",
          onclick: () => { draft.exercises.splice(index, 1); render(); },
        }),
      ),
      ...ex.sets.map((set) => setRow(ex, set)),
      el("button", {
        textContent: "+ Set",
        onclick: () => {
          const last = ex.sets[ex.sets.length - 1];
          ex.sets.push(last ? { ...last } : { weight: "", amount: "", unit: "reps" });
          render();
        },
      }),
    );
  }

  function exerciseSearch() {
    const results = el("ul", { className: "section" });
    let timer = null;
    async function search(query) {
      const found = await api("GET", `/api/catalog?q=${encodeURIComponent(query)}`);
      results.replaceChildren(...found.map((ex) => el("li", {}, el("button", {
        className: "row",
        textContent: ex.name,
        onclick: () => {
          draft.exercises.push({
            exercise_id: ex.id,
            name: ex.name,
            sets: [{ weight: "", amount: "", unit: "reps" }],
          });
          render();
        },
      }))));
    }
    const field = input({ placeholder: "Search exercise" }, (v) => {
      clearTimeout(timer);
      timer = setTimeout(() => search(v.trim()), 300);
    });
    search("");
    return el("section", { className: "section search" }, field, results);
  }

  function buildBody() {
    return {
      date: draft.date,
      notes: draft.notes,
      exercises: draft.exercises.map((ex) => ({
        exercise_id: ex.exercise_id,
        name: ex.name,
        sets: ex.sets.map((set) => {
          const amount = parseAmount(set.amount, set.unit);
          return {
            weight: parseWeight(set.weight),
            reps: set.unit === "reps" ? amount : null,
            seconds: set.unit === "sec" ? amount : null,
          };
        }),
      })),
    };
  }

  async function save() {
    let body;
    try {
      body = buildBody();
    } catch (e) {
      notify(e.message);
      return;
    }
    const saved = await api("PUT", `/api/workouts/${workout.id}`, body);
    listView = null;
    renderWorkout(saved);
  }

  // перерисовка после правки — без анимации, она только при входе в форму
  function render(animate = false) {
    const addExercise = el("div");
    addExercise.append(el("button", {
      textContent: "+ Exercise",
      onclick: () => addExercise.replaceChildren(exerciseSearch()),
    }));
    const nodes = [
      el("div", { className: "actions" },
        el("button", { textContent: "Cancel", onclick: () => renderWorkout(workout) }),
        el("span", { className: "spacer" }),
        el("button", { className: "primary", textContent: "Save", onclick: save }),
      ),
      el("section", { className: "section" },
        el("label", { textContent: "Date" }),
        input({ type: "date", value: draft.date }, (v) => { draft.date = v; }),
        el("label", { textContent: "Notes" }),
        el("textarea", { value: draft.notes, rows: 2, oninput: (e) => { draft.notes = e.target.value; } }),
      ),
      ...draft.exercises.map(exerciseBlock),
      addExercise,
    ];
    if (animate) show(...nodes);
    else view.replaceChildren(...nodes);
  }

  render(true);
  window.scrollTo(0, 0);
}

async function showProgress() {
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

function formatValue(value, metric) {
  if (metric === "weight") return `${value} kg`;
  if (metric === "reps") return `${value} reps`;
  const seconds = String(Math.abs(value) % 60).padStart(2, "0");
  return `${Math.floor(Math.abs(value) / 60)}:${seconds}`;
}

function formatShortDate(iso) {
  return parseDate(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short" });
}

function withAlpha(hex, alpha) {
  const match = /^#([0-9a-f]{6})$/i.exec(hex);
  if (!match) return "transparent";
  const n = parseInt(match[1], 16);
  return `rgba(${n >> 16}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`;
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
  if (chart) chart.destroy();
  chart = null;
  const start = periodStart();
  const points = data.points.filter((p) => start === null || parseDate(p.date) >= start);
  canvas.parentElement.hidden = !points.length;
  if (!points.length) {
    summary.replaceChildren(el("p", { className: "empty", textContent: "No workouts in this period." }));
    return;
  }
  renderSummary(summary, points, data.metric);

  // ось X — настоящее время: перерыв в месяц не должен выглядеть как соседний день
  const from = start === null ? parseDate(points[0].date).getTime() : start.getTime();
  const to = Math.max(Date.now(), parseDate(points[points.length - 1].date).getTime());
  const long = to - from > 180 * 24 * 3600 * 1000;
  const tickFormat = long ? { month: "short", year: "2-digit" } : { day: "numeric", month: "short" };

  const accent = cssColor("--accent");
  const hint = cssColor("--hint");
  const text = cssColor("--text");
  chart = new Chart(canvas, {
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
            callback: (value) => (data.metric === "seconds" ? formatValue(value, "seconds") : value),
          },
        },
      },
    },
  });
}

tabs.workouts.onclick = () => showList();
tabs.progress.onclick = () => showProgress();
tg.ready();
tg.expand();
if (inTelegram && tg.isVersionAtLeast("6.1")) {
  // шапка и фон Telegram того же цвета, что и страница
  tg.setHeaderColor("secondary_bg_color");
  tg.setBackgroundColor("secondary_bg_color");
}
showList();
