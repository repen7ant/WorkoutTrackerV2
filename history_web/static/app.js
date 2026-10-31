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
  renderWorkout(await api("GET", `/api/workouts/${id}`));
}

function renderWorkout(w) {
  const actions = el("div", { className: "actions" },
    el("button", { textContent: "← Back", onclick: () => showList() }),
    el("button", { textContent: "Edit", onclick: () => showEdit(w) }),
    el("button", { textContent: "Delete", onclick: () => removeWorkout(w.id) }),
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
  if (set.seconds !== null) {
    const seconds = String(set.seconds % 60).padStart(2, "0");
    return {
      weight: set.weight === null ? "" : String(set.weight),
      amount: `${Math.floor(set.seconds / 60)}:${seconds}`,
      unit: "sec",
    };
  }
  return { weight: set.weight === null ? "" : String(set.weight), amount: String(set.reps), unit: "reps" };
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
    return el("div", { className: "exercise" },
      el("div", { className: "exercise-head" },
        el("h3", { textContent: ex.name }),
        el("button", { textContent: "↑", onclick: () => move(index, -1) }),
        el("button", { textContent: "↓", onclick: () => move(index, 1) }),
        el("button", {
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
    const results = el("ul");
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
    return el("div", { className: "search" }, field, results);
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

  function render() {
    const addExercise = el("div");
    addExercise.append(el("button", {
      textContent: "+ Exercise",
      onclick: () => addExercise.replaceChildren(exerciseSearch()),
    }));
    view.replaceChildren(
      el("div", { className: "actions" },
        el("button", { className: "active", textContent: "Save", onclick: save }),
        el("button", { textContent: "Cancel", onclick: () => renderWorkout(workout) }),
      ),
      el("label", { textContent: "Date" }),
      input({ type: "date", value: draft.date }, (v) => { draft.date = v; }),
      el("label", { textContent: "Notes" }),
      el("textarea", { value: draft.notes, rows: 2, oninput: (e) => { draft.notes = e.target.value; } }),
      ...draft.exercises.map(exerciseBlock),
      addExercise,
    );
  }

  render();
  window.scrollTo(0, 0);
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
