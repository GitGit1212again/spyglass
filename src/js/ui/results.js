// Live output of tools running on this PC. Polls the server while a tool runs.
import { get, post } from "../api.js";
import { el } from "../dom.js";

const URL_RE = /(https?:\/\/[^\s"'<>]+)/g;
let onDone = () => {};

export function onJobDone(fn) { onDone = fn; }

function lineNode(text) {
  const plus = /^\s*\[\+\]|found|^\s*\[\*\] .*: http/i.test(text) && !/not found/i.test(text);
  const minus = /^\s*\[-\]|^\s*\[x\]|not found/i.test(text);
  const span = el(`span${plus ? ".hit" : minus ? ".miss" : ""}`);
  let last = 0;
  for (const m of text.matchAll(URL_RE)) {
    span.append(text.slice(last, m.index),
      el("a", { href: m[1], target: "_blank", rel: "noopener noreferrer", text: m[1] }));
    last = m.index + m[1].length;
  }
  span.append(text.slice(last), "\n");
  return span;
}

export function addJob(id, meta, reveal) {
  document.getElementById("noResults").hidden = true;
  const state = el("span.state", { text: "RUNNING" });
  const pre = el("pre", {}, el("span.run"));
  const stop = el("button.ghost", { text: "STOP", onclick: (e) => { e.stopPropagation(); post("/api/stop", { id }); } });
  const job = el("div.job", {},
    el("div.job-head", { onclick: () => job.classList.toggle("closed") },
      el("div.t", {}, el("b", { text: meta.title }), el("span", { text: `${meta.query}  ·  ${meta.tool}` })),
      state, stop),
    pre);
  document.getElementById("jobs").prepend(job);

  let from = 0;
  const cursor = pre.lastChild;
  const tick = async () => {
    let d;
    try {
      d = await get(`/api/job?id=${id}&from=${from}`);
    } catch {
      state.textContent = "LOST";
      state.className = "state bad";
      return;
    }
    const nearBottom = pre.scrollHeight - pre.scrollTop - pre.clientHeight < 40;
    for (const line of d.lines) pre.insertBefore(lineNode(line), cursor);
    from = d.next;
    if (nearBottom) pre.scrollTop = pre.scrollHeight;
    if (!d.done) return setTimeout(tick, 700);
    cursor.remove();
    stop.remove();
    if (!from) pre.append(el("span.miss", { text: "(the tool printed nothing)\n" }));
    state.textContent = d.stopped ? "STOPPED" : d.code === 0 ? "DONE" : `ENDED (${d.code})`;
    state.className = "state " + (d.code === 0 && !d.stopped ? "ok" : "bad");
    if (d.file) {
      job.querySelector(".job-head").append(el("button.ghost", {
        text: "SAVED", title: "Show the saved result file",
        onclick: (e) => { e.stopPropagation(); reveal(d.file); },
      }));
    }
    onDone();
  };
  tick();
}
