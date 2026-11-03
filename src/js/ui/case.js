// Case picker, notes (saved as you type) and the history list.
import { get, post } from "../api.js";
import { el } from "../dom.js";

let current = "General";
let saveTimer = 0;

export function caseName() { return current; }

export function fillCases(cases, selected) {
  current = selected;
  const sel = document.getElementById("caseSel");
  const names = cases.map((c) => c.name);
  if (!names.includes(selected)) names.unshift(selected);
  sel.replaceChildren(...names.map((n) => el("option", { value: n, text: n, selected: n === selected })));
}

const WHEN = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });

export function renderHistory(list, { refill, reveal }) {
  const ol = document.getElementById("history");
  document.getElementById("noHistory").hidden = list.length > 0;
  ol.replaceChildren(...list.map((h) => el("li", {},
    el("div", {},
      el("div.what", { text: h.title }),
      el("div.q", { text: h.query, title: "Look this up again", onclick: () => refill(h) })),
    el("div.when", { text: WHEN.format(new Date(h.time)) }),
    h.file ? el("div.file", { text: "file", title: "Show the saved file", onclick: () => reveal(h.file) }) : "",
  )));
}

export async function loadCase(name, handlers) {
  const d = await get(`/api/case?name=${encodeURIComponent(name)}`);
  current = d.name;
  const notes = document.getElementById("notes");
  notes.value = d.notes;
  document.getElementById("saved").textContent = "";
  renderHistory(d.history, handlers);
  return d;
}

export async function selectCase(name, handlers) {
  await post("/api/case", { name });
  return loadCase(name, handlers);
}

export function wireNotes() {
  const notes = document.getElementById("notes");
  const saved = document.getElementById("saved");
  notes.addEventListener("input", () => {
    saved.textContent = "...";
    clearTimeout(saveTimer);
    const text = notes.value;
    const name = current;
    saveTimer = setTimeout(async () => {
      try {
        await post("/api/notes", { case: name, text });
        saved.textContent = "saved";
      } catch (e) {
        saved.textContent = "NOT SAVED: " + e.message;
      }
    }, 600);
  });
}
