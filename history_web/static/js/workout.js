import { api } from "./api.js";
import { el, show } from "./dom.js";
import { showEdit } from "./edit.js";
import { formatLongDate, formatSet } from "./format.js";
import { resetList, showList } from "./list.js";
import { confirmAction } from "./telegram.js";

export async function showWorkout(id) {
  renderWorkout(await api("GET", `/api/workouts/${id}`));
}

export function renderWorkout(w) {
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
  resetList();
  showList();
}
