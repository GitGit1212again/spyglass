// Entry point: loads the tool list and the current case, wires the search box, chips and panels.
import { get, post, upload } from "./api.js";
import { detect } from "./detect.js";
import { el, toast } from "./dom.js";
import { startRain } from "./rain.js";
import { renderTools } from "./ui/tools.js";
import { addJob, onJobDone } from "./ui/results.js";
import { caseName, fillCases, loadCase, selectCase, wireNotes } from "./ui/case.js";
import { openAddTool, wireAddTool } from "./ui/addtool.js";
import { LEARN } from "./data/learn.js";

const $ = (id) => document.getElementById(id);
const S = { types: [], tools: [], kind: null, manual: false, file: null, showHidden: false };
const caseHandlers = { refill, reveal };

function reveal(path) {
  post("/api/reveal", { path, case: caseName() });
}

function query() {
  return S.kind === "file" && S.file ? S.file.path : $("q").value.trim();
}

function renderChips() {
  const auto = S.manual ? null : S.kind;
  $("chips").replaceChildren(...S.types.map(([k, label]) => el(`button.chip${S.kind === k ? ".on" : ""}`, {
    role: "radio", "aria-checked": String(S.kind === k),
    onclick: () => {
      if (k === "file" && !S.file) return $("fileInput").click();
      S.kind = S.kind === k && S.manual ? detect($("q").value) : k;
      S.manual = S.kind === k;
      render();
    },
  }, label, auto === k ? el("span.auto", { text: "auto" }) : "")));
}

function render() {
  renderChips();
  renderTools($("sections"), S, { run, fav, hide, edit: (t) => openAddTool(t) });
  const webCount = S.kind ? S.tools.filter((t) => t.kind === "web" && !t.hidden && t.types.includes(S.kind)).length : 0;
  $("bar").hidden = !S.kind || webCount < 2 || S.kind === "file";
  $("barText").textContent = S.kind ? `${webCount} websites fit this` : "";
  $("showHidden").textContent = S.showHidden ? "HIDE HIDDEN TOOLS" : "SHOW HIDDEN TOOLS";
}

async function run(t) {
  const q = query();
  if (!q) return toast("Type something to look up first.", true);
  try {
    const d = await post("/api/run", { tool: t.id, query: q, kind: S.kind, case: caseName() });
    if (d.job) {
      addJob(d.job, { title: t.title, tool: t.tool || "", query: S.kind === "file" ? S.file.name : q }, reveal);
      showTab("results");
    } else {
      toast(`Opened ${t.tool || t.title} in your browser`);
      refreshHistory();
    }
  } catch (e) {
    toast(e.message, true);
  }
}

async function openAll() {
  const q = query();
  const list = S.tools.filter((t) => t.kind === "web" && !t.hidden && t.types.includes(S.kind));
  if (!q || !list.length) return;
  if (list.length > 8 && !confirm(`Open ${list.length} websites at once?`)) return;
  for (const t of list) {
    try { await post("/api/run", { tool: t.id, query: q, kind: S.kind, case: caseName() }); } catch { /* keep going */ }
  }
  toast(`Opened ${list.length} websites`);
  refreshHistory();
}

async function savePrefs() {
  const d = await post("/api/prefs", {
    favorites: S.tools.filter((t) => t.favorite).map((t) => t.id),
    hidden: S.tools.filter((t) => t.hidden).map((t) => t.id),
  });
  S.tools = d.tools;
  render();
}

function fav(t) { t.favorite = !t.favorite; savePrefs(); }
function hide(t) {
  t.hidden = !t.hidden;
  if (t.hidden) toast("Hidden. \"Show hidden tools\" at the bottom brings it back.");
  savePrefs();
}

function refill(h) {
  if (h.kind === "file") {
    const path = h.src || (h.how === "file" ? h.file : null);
    if (!path) return toast("Drop that file in again to use it.", true);
    S.file = { path, name: h.query };
    $("q").value = h.query;
  } else {
    S.file = null;
    $("q").value = h.query;
  }
  S.kind = h.kind || detect(h.query);
  S.manual = true;
  render();
  $("q").focus();
}

async function refreshHistory() {
  try { await loadCase(caseName(), caseHandlers); } catch { /* ignore */ }
}

async function useFile(file) {
  if (!file) return;
  toast(`Adding ${file.name} to the case...`);
  try {
    const d = await upload(file, caseName());
    S.file = { path: d.path, name: d.name };
    $("q").value = d.name;
    S.kind = "file";
    S.manual = true;
    render();
    toast(`${d.name} is in the case's files folder`);
    refreshHistory();
  } catch (e) {
    toast(e.message, true);
  }
}

function showTab(name) {
  for (const b of document.querySelectorAll(".tabs button")) b.classList.toggle("on", b.dataset.tab === name);
  for (const t of document.querySelectorAll(".tab")) t.hidden = t.id !== `tab-${name}`;
}

function wire() {
  $("q").addEventListener("input", () => {
    if (S.file) S.file = null;
    if (S.kind === "file") S.manual = false;
    const guess = detect($("q").value);
    if (!S.manual || !guess) { S.kind = guess; S.manual = false; }
    render();
  });
  $("pick").addEventListener("click", () => $("fileInput").click());
  $("fileInput").addEventListener("change", (e) => { useFile(e.target.files[0]); e.target.value = ""; });
  addEventListener("dragover", (e) => { e.preventDefault(); document.body.classList.add("dragging"); });
  addEventListener("dragleave", (e) => { if (!e.relatedTarget) document.body.classList.remove("dragging"); });
  addEventListener("drop", (e) => {
    e.preventDefault();
    document.body.classList.remove("dragging");
    useFile(e.dataTransfer.files[0]);
  });

  $("openAll").addEventListener("click", openAll);
  $("addTool").addEventListener("click", () => openAddTool(null, S.kind));
  $("showHidden").addEventListener("click", () => { S.showHidden = !S.showHidden; render(); });
  for (const b of document.querySelectorAll(".tabs button")) b.addEventListener("click", () => showTab(b.dataset.tab));

  $("caseSel").addEventListener("change", async (e) => {
    await selectCase(e.target.value, caseHandlers);
    S.file = null;
    toast(`Working on: ${e.target.value}`);
  });
  $("openFolder").addEventListener("click", () => post("/api/reveal", { case: caseName() }));
  $("newCase").addEventListener("click", () => {
    $("caseForm").reset();
    $("caseErr").textContent = "";
    $("caseDlg").showModal();
  });
  $("caseForm").addEventListener("submit", async (e) => {
    if (e.submitter?.value !== "save") return;
    e.preventDefault();
    const name = new FormData($("caseForm")).get("name").trim();
    try {
      await selectCase(name, caseHandlers);
      const st = await get("/api/state");
      fillCases(st.cases, name);
      $("caseDlg").close();
      toast(`Started case: ${name}`);
    } catch (err) {
      $("caseErr").textContent = err.message;
    }
  });
  wireNotes();
  onJobDone(refreshHistory);
  $("learn").replaceChildren(...LEARN.map((l) => el("li", {},
    el("a", { href: l.url, target: "_blank", rel: "noopener noreferrer", text: l.title }),
    el("p", { text: l.detail }))));
}

async function boot() {
  startRain($("rain"));
  wire();
  const st = await get("/api/state");
  S.types = st.types;
  S.tools = st.tools;
  fillCases(st.cases, st.case);
  wireAddTool(st.types, (tools, msg) => { S.tools = tools; render(); toast(msg); });
  await loadCase(st.case, caseHandlers);
  render();
  $("q").focus();
}

boot().catch((e) => toast("Could not start: " + e.message, true));
