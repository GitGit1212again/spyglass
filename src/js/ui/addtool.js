// "Add your own tool" dialog: a website with {query} in its address, or a program on this PC.
import { post } from "../api.js";
import { el } from "../dom.js";

let editing = null;
let onSaved = () => {};

export function wireAddTool(types, saved) {
  onSaved = saved;
  const dlg = document.getElementById("toolDlg");
  const form = document.getElementById("toolForm");
  document.getElementById("typeBoxes").replaceChildren(...types.map(([k, label]) =>
    el("label", {}, el("input", { type: "checkbox", name: "types", value: k }), label)));
  form.addEventListener("change", (e) => {
    if (e.target.name === "kind") showKind(e.target.value);
  });
  form.addEventListener("submit", async (e) => {
    if (e.submitter?.value !== "save") return;
    e.preventDefault();
    const f = new FormData(form);
    const body = {
      id: editing?.id, title: f.get("title"), detail: f.get("detail"), tool: f.get("tool"),
      kind: f.get("kind"), url: f.get("url"), cmd: f.get("cmd"), types: f.getAll("types"),
    };
    try {
      const d = await post("/api/custom", body);
      dlg.close();
      onSaved(d.tools, "Saved.");
    } catch (err) {
      document.getElementById("toolErr").textContent = err.message;
    }
  });
}

function showKind(kind) {
  document.getElementById("urlRow").hidden = kind !== "web";
  document.getElementById("cmdRow").hidden = kind !== "pc";
}

export function openAddTool(tool = null, kindNow = null) {
  editing = tool;
  const form = document.getElementById("toolForm");
  form.reset();
  document.getElementById("toolErr").textContent = "";
  form.querySelector("h2").textContent = tool ? "CHANGE YOUR TOOL" : "ADD YOUR OWN TOOL";
  const kind = tool?.kind || "web";
  form.elements.kind.value = kind;
  showKind(kind);
  if (tool) {
    form.elements.title.value = tool.title;
    form.elements.detail.value = tool.detail || "";
    form.elements.tool.value = tool.tool || "";
    form.elements.url.value = tool.url || "";
    form.elements.cmd.value = (tool.cmd || []).map((a) => (/\s/.test(a) ? `"${a}"` : a)).join(" ");
  }
  const want = tool ? tool.types : kindNow ? [kindNow] : [];
  for (const box of form.querySelectorAll("input[name=types]")) box.checked = want.includes(box.value);

  const old = form.querySelector(".del");
  if (old) old.remove();
  if (tool) {
    form.querySelector(".row").prepend(el("button.ghost.del", {
      type: "button", text: "DELETE", style: "margin-right:auto",
      onclick: async () => {
        const d = await post("/api/custom", { delete: tool.id });
        document.getElementById("toolDlg").close();
        onSaved(d.tools, "Deleted.");
      },
    }));
  }
  document.getElementById("toolDlg").showModal();
}
