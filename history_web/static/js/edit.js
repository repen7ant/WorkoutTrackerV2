import { api } from "./api.js";
import { el, show, view } from "./dom.js";
import { resetList } from "./list.js";
import { parseAmount, parseWeight } from "./parse.js";
import { notify } from "./telegram.js";
import { renderWorkout } from "./workout.js";

function draftSet(set) {
  const weight = set.weight === null ? "" : String(set.weight);
  if (set.seconds !== null) {
    const seconds = String(set.seconds % 60).padStart(2, "0");
    return { weight, amount: `${Math.floor(set.seconds / 60)}:${seconds}`, unit: "sec" };
  }
  return { weight, amount: String(set.reps), unit: "reps" };
}

export function showEdit(workout) {
  // черновик со строками из полей: разбираем только при сохранении
  const draft = {
    date: workout.date,
    start_time: workout.start_time || "",
    end_time: workout.end_time || "",
    notes: workout.notes || "",
    exercises: workout.exercises.map((ex) => ({
      exercise_id: ex.exercise_id,
      name: ex.name,
      notes: ex.notes || "",
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
      // textarea, а не input: input вырезает переводы строк из заметки
      el("textarea", {
        value: ex.notes,
        rows: 2,
        maxLength: 200,
        placeholder: "Note",
        oninput: (e) => { ex.notes = e.target.value; },
      }),
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
            notes: "",
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
    if (Boolean(draft.start_time) !== Boolean(draft.end_time)) {
      throw new Error("Enter both start and end or neither.");
    }
    return {
      date: draft.date,
      start_time: draft.start_time || null,
      end_time: draft.end_time || null,
      notes: draft.notes,
      exercises: draft.exercises.map((ex) => ({
        exercise_id: ex.exercise_id,
        name: ex.name,
        notes: ex.notes,
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
    resetList();
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
        el("div", { className: "time-fields" },
          el("div", {},
            el("label", { textContent: "Start" }),
            input({ type: "time", value: draft.start_time }, (v) => { draft.start_time = v; }),
          ),
          el("div", {},
            el("label", { textContent: "End" }),
            input({ type: "time", value: draft.end_time }, (v) => { draft.end_time = v; }),
          ),
        ),
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
