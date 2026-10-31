export const view = document.getElementById("view");
export const tabs = {
  workouts: document.getElementById("tab-workouts"),
  progress: document.getElementById("tab-progress"),
};

export function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  Object.assign(node, props);
  node.append(...children);
  return node;
}

export function show(...nodes) {
  view.replaceChildren(...nodes);
  view.classList.remove("enter");
  void view.offsetWidth; // перезапуск анимации появления
  view.classList.add("enter");
}

export function setTab(name) {
  for (const [key, button] of Object.entries(tabs)) {
    button.classList.toggle("active", key === name);
  }
}

export function cssColor(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}
