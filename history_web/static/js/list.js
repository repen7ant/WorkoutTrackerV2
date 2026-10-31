import { api } from "./api.js";
import { el, setTab, show } from "./dom.js";
import { parseDate } from "./format.js";
import { showWorkout } from "./workout.js";

let listView = null;
let listScroll = 0;

// после правки или удаления список нужно перечитать
export function resetList() {
  listView = null;
}

function workoutRow(w) {
  const date = parseDate(w.date);
  const text = el("span", { className: "row-text" },
    el("span", { textContent: date.toLocaleDateString("en-GB", { weekday: "long" }) }),
  );
  if (w.notes) text.append(el("span", { className: "row-subtitle", textContent: w.notes }));
  return el("button", {
    className: "row",
    onclick: () => {
      listScroll = window.scrollY;
      showWorkout(w.id);
    },
  },
  el("span", { className: "day", textContent: date.getDate() }),
  text,
  el("span", { className: "chevron", textContent: "›" }),
  );
}

export async function showList(refresh = false) {
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
