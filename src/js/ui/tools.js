// The tool cards, grouped into "Start here", "Run on this PC" and "Websites".
import { el } from "../dom.js";

function card(t, ready, on) {
  const missing = t.kind === "pc" && !t.installed;
  const label = missing ? "NOT INSTALLED" : t.kind === "pc" ? "RUN" : "OPEN";
  return el(`div.card${missing ? ".missing" : ""}${t.hidden ? ".hidden-tool" : ""}`, {},
    el("div.title", { text: t.title }),
    el("div.detail", { text: missing && t.hint ? `${t.detail || ""} ${t.hint}`.trim() : t.detail || "" }),
    el("div.meta", {},
      el("span.tag", { text: t.kind === "pc" ? "THIS PC" : "WEB", title: t.kind === "pc"
        ? "Runs on this computer; the result is saved in the case" : "Opens the website in your browser" }),
      el("span.tool", { text: t.tool || "" }),
      el(`button.icon${t.favorite ? ".fav" : ""}`, {
        text: t.favorite ? "★" : "☆", title: t.favorite ? "Remove from Start here" : "Add to Start here",
        onclick: () => on.fav(t),
      }),
      t.custom
        ? el("button.icon", { text: "✎", title: "Change this tool", onclick: () => on.edit(t) })
        : el("button.icon", { text: t.hidden ? "↺" : "×", title: t.hidden ? "Show this tool again" : "Hide this tool",
          onclick: () => on.hide(t) }),
      el("button.go", { text: label, disabled: missing || !ready, onclick: () => on.run(t) }),
    ));
}

function section(title, list, ready, on, cls = "") {
  if (!list.length) return null;
  return el(`section.section${cls}`, {},
    el("h3", { text: title }),
    el("div.grid", {}, list.map((t) => card(t, ready, on))));
}

export function renderTools(box, { tools, kind, showHidden }, on) {
  const ready = !!kind;
  const fits = tools.filter((t) => (!kind || t.types.includes(kind)) && (showHidden || !t.hidden));
  const fav = fits.filter((t) => t.favorite);
  const rest = kind ? fits.filter((t) => !t.favorite) : [];
  box.replaceChildren(
    section("START HERE", fav, ready, on, ".start") || "",
    section("RUN ON THIS PC", rest.filter((t) => t.kind === "pc"), ready, on) || "",
    section("WEBSITES", rest.filter((t) => t.kind === "web"), ready, on) || "",
    !kind ? el("div.empty-state", { text: "Type something above to see every tool that fits it." })
      : !fits.length ? el("div.empty-state", { text: "No tools for this kind yet. Add your own below." }) : "",
  );
}
