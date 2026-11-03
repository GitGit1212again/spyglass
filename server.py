"""Spyglass server: serves the workspace page, runs the OSINT tools, keeps case folders.

    Windows:  .venv\\Scripts\\python.exe server.py [--open] [--keep]     http://127.0.0.1:8803
    macOS:    .venv/bin/python server.py [--open] [--keep]              (or run Run-Spyglass.command)

Runs from the app's own .venv so the installed tools (sherlock, maigret, holehe, ...) are
on PATH without touching the main Python. Everything a case collects lives in
<home>/Documents/Spyglass/cases/<case>/ (notes.md, history.jsonl, results/, files/);
set SPYGLASS_DATA to keep it somewhere else.

Safety: tools are started with an argument list (never a shell), so what is typed in the
search box can only ever be one argument. Typed text may not start with "-" so it cannot
be read as a tool option. Requests must come from this server's own page (Host/Origin).
"""
from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import threading
import time
import uuid
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

PORT = 8803
ROOT = os.path.dirname(os.path.abspath(__file__))

if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
try:
    import autoquit  # noqa: E402  (autoquit.py sits next to this file)
except Exception:  # no watchdog: the server then runs until it is stopped by hand
    autoquit = None

from catalog import DEFAULT_FAVORITES, TOOLS, TYPES  # noqa: E402

IS_WIN = os.name == "nt"
IS_MAC = sys.platform == "darwin"
SRC = os.path.join(ROOT, "src")
# The app's private Python lives in .venv (Scripts\python.exe on Windows, bin/python elsewhere).
# Windows keeps python.exe (not pythonw.exe) for the tools so their output can be read.
VENV_BIN = os.path.join(ROOT, ".venv", "Scripts" if IS_WIN else "bin")
VENV_PY = os.path.join(VENV_BIN, "python.exe" if IS_WIN else "python")


def _tool_python() -> str:
    """The Python that runs helpers/*.py: the .venv if it exists, else the one running us."""
    if os.path.isfile(VENV_PY):
        return VENV_PY
    exe = sys.executable
    if IS_WIN and exe.lower().endswith("pythonw.exe"):
        exe = exe[:-len("pythonw.exe")] + "python.exe"
    return exe


PY = _tool_python()
DATA = os.environ.get("SPYGLASS_DATA") or str(Path.home() / "Documents" / "Spyglass")
CASES = os.path.join(DATA, "cases")
SETTINGS = os.path.join(DATA, "settings.json")


def _extra_path() -> list[str]:
    """Folders searched for tools besides PATH (a server started before an install would miss them)."""
    out = [os.path.dirname(PY)]
    if IS_WIN:
        local = os.environ.get("LOCALAPPDATA")
        if local:  # winget puts portable tools (exiftool, amass) here
            out += [os.path.join(local, "Microsoft", "WinGet", "Links"),
                    os.path.join(local, "Programs", "ExifTool")]
    elif IS_MAC:  # Homebrew on Apple Silicon / Intel; a Finder-launched app may not have these on PATH
        out += ["/opt/homebrew/bin", "/opt/homebrew/sbin", "/usr/local/bin"]
    return out


TOOL_PATH = os.pathsep.join(_extra_path() + [os.environ.get("PATH", "")])
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b\][^\x07]*\x07")
# progress bars and console warnings that say nothing about the result
NOISE = re.compile(r"\d+%\|.*\|\s*\d+/\d+|could not be decoded, and were replaced|^\s*\d+/\d+ \[")
CASE_RE = re.compile(r"^[\w .,'()-]{1,60}$")
MAX_LINES = 20000

jobs: dict[str, dict] = {}
jobs_lock = threading.Lock()


# ---------------------------------------------------------------- storage

def load_settings() -> dict:
    try:
        with open(SETTINGS, encoding="utf-8") as f:
            s = json.load(f)
    except (OSError, ValueError):
        s = {}
    s.setdefault("favorites", list(DEFAULT_FAVORITES))
    s.setdefault("hidden", [])
    s.setdefault("custom", [])
    s.setdefault("case", "General")
    return s


def save_settings(s: dict) -> None:
    os.makedirs(DATA, exist_ok=True)
    tmp = SETTINGS + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(s, f, indent=2)
    os.replace(tmp, SETTINGS)


def case_dir(name: str, make: bool = True) -> str:
    if not CASE_RE.match(name or "") or name.strip(" .") != name:
        raise ValueError("Case names can use letters, numbers, spaces and - _ . , ' ( )")
    d = os.path.join(CASES, name)
    if make:
        for sub in ("results", "files"):
            os.makedirs(os.path.join(d, sub), exist_ok=True)
    return d


def list_cases() -> list[dict]:
    os.makedirs(CASES, exist_ok=True)
    out = []
    for n in os.listdir(CASES):
        p = os.path.join(CASES, n)
        if os.path.isdir(p):
            out.append({"name": n, "modified": os.path.getmtime(p)})
    out.sort(key=lambda c: -c["modified"])
    return out


def add_history(case: str, entry: dict) -> None:
    d = case_dir(case)
    entry = {"time": datetime.now().isoformat(timespec="seconds"), **entry}
    with open(os.path.join(d, "history.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    os.utime(d)


def read_case(case: str) -> dict:
    d = case_dir(case)
    notes = ""
    try:
        with open(os.path.join(d, "notes.md"), encoding="utf-8") as f:
            notes = f.read()
    except OSError:
        pass
    hist = []
    try:
        with open(os.path.join(d, "history.jsonl"), encoding="utf-8") as f:
            for line in f:
                try:
                    hist.append(json.loads(line))
                except ValueError:
                    pass
    except OSError:
        pass
    return {"name": case, "folder": d, "notes": notes, "history": hist[::-1][:300]}


# ---------------------------------------------------------------- tools

def all_tools(settings: dict) -> list[dict]:
    out = []
    for t in TOOLS + [dict(c, custom=True) for c in settings["custom"]]:
        t = dict(t)
        if t["kind"] == "pc":
            missing = missing_program(t)
            t["installed"] = missing is None
            if missing:
                t["hint"] = install_hint(missing)
        t["favorite"] = t["id"] in settings["favorites"]
        t["hidden"] = t["id"] in settings["hidden"]
        out.append(t)
    return out


# How to get a program that is not part of the .venv. Keys: sys.platform ("win32", "darwin");
# "pip" tools come with requirements.txt.
INSTALL_HINTS = {
    "exiftool": {"win32": "winget install OliverBetz.ExifTool", "darwin": "brew install exiftool",
                 "other": "Install ExifTool from https://exiftool.org"},
    "amass": {"win32": "winget install OWASP.Amass", "darwin": "brew install amass",
              "other": "Install Amass from https://github.com/owasp-amass/amass"},
    "ffmpeg": {"win32": "winget install Gyan.FFmpeg", "darwin": "brew install ffmpeg",
               "other": "Install ffmpeg from https://ffmpeg.org"},
}
PIP_TOOLS = {"sherlock", "maigret", "holehe", "ignorant", "instaloader", "gallery-dl", "yt-dlp"}


def install_hint(exe: str) -> str | None:
    """One plain sentence on how to install a missing program, or None when unknown."""
    name = os.path.splitext(os.path.basename(exe))[0] if IS_WIN else os.path.basename(exe)
    if name in PIP_TOOLS:
        py = os.path.relpath(PY, ROOT) if PY.startswith(ROOT) else "python"
        return f"In the Spyglass folder run: {py} -m pip install -r requirements.txt"
    h = INSTALL_HINTS.get(name)
    if not h:
        return None
    if sys.platform in h:
        return f"Install it with: {h[sys.platform]}"
    return h["other"]


def missing_program(t: dict) -> str | None:
    """The first program this tool needs that is not available, or None when all are there."""
    exe = t["cmd"][0]
    if exe == "{py}":
        if not os.path.isfile(PY):
            return PY
    elif shutil.which(exe, path=TOOL_PATH) is None:
        return exe
    for need in t.get("needs", []):  # programs a helper script calls (e.g. exiftool)
        if shutil.which(need, path=TOOL_PATH) is None:
            return need
    return None


def installed(t: dict) -> bool:
    return missing_program(t) is None


def find_tool(tid: str) -> dict | None:
    for t in TOOLS + [dict(c, custom=True) for c in load_settings()["custom"]]:
        if t["id"] == tid:
            return t
    return None


def check_query(q: str, kind: str) -> str:
    q = (q or "").strip()
    if not q:
        raise ValueError("Type something to look up first.")
    if len(q) > 500 or "\n" in q or "\r" in q or "\0" in q:
        raise ValueError("That is too long or has line breaks in it.")
    if kind == "file":
        if not os.path.isfile(q):
            raise ValueError("That file is not on this PC any more.")
    elif q.startswith("-"):
        raise ValueError("Lookups cannot start with a dash.")
    return q


def phone_parts(q: str) -> tuple[str, str]:
    try:
        import phonenumbers
        n = phonenumbers.parse(q, "US")
        return str(n.country_code), str(n.national_number)
    except Exception:
        digits = re.sub(r"\D", "", q)
        return ("1", digits[-10:]) if len(digits) >= 10 else ("1", digits)


def build_cmd(t: dict, q: str) -> list[str]:
    cc, national = phone_parts(q) if "{cc}" in "".join(t["cmd"]) else ("", "")
    out = []
    for a in t["cmd"]:
        if a == "{query}":
            out.append(q)  # whole argument, never split
            continue
        arg = (a.replace("{py}", PY).replace("{here}", ROOT)
                .replace("{cc}", cc).replace("{national}", national).replace("{query}", q))
        if "{here}" in a and "{query}" not in a:
            arg = os.path.normpath(arg)  # catalog paths use "/"; make them native
        out.append(arg)
    exe = out[0]
    if exe != PY:
        found = shutil.which(exe, path=TOOL_PATH)
        if not found:
            raise ValueError(missing_message(t, exe))
        out[0] = found
    for need in t.get("needs", []):  # programs a helper script calls
        if shutil.which(need, path=TOOL_PATH) is None:
            raise ValueError(missing_message(t, need))
    return out


def missing_message(t: dict, exe: str) -> str:
    hint = install_hint(exe)
    return f"{t.get('tool') or exe} is not installed on this computer." + (f" {hint}" if hint else "")


def safe_name(s: str) -> str:
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", s).strip(" ._")
    return s[:60] or "result"


def start_job(case: str, t: dict, q: str, kind: str) -> str:
    cmd = build_cmd(t, q)
    d = case_dir(case)
    cwd = os.path.join(d, "files")
    env = dict(os.environ, PATH=TOOL_PATH, PYTHONIOENCODING="utf-8", PYTHONUTF8="1",
               PYTHONUNBUFFERED="1", NO_COLOR="1", TERM="dumb")
    # Windows: no console window. macOS/Linux: own process group, so STOP can end the whole tool.
    flags = {"creationflags": subprocess.CREATE_NO_WINDOW} if IS_WIN else {"start_new_session": True}
    try:
        proc = subprocess.Popen(cmd, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **flags)
    except OSError as e:  # e.g. the program vanished or is not executable
        raise ValueError(f"Could not start {t.get('tool') or t['id']}: {e.strerror or e}") from e
    jid = uuid.uuid4().hex[:10]
    job = {"id": jid, "tool": t["id"], "title": t["title"], "toolname": t.get("tool", ""),
           "query": q if kind != "file" else os.path.basename(q), "src": q, "case": case, "kind": kind,
           "lines": [], "done": False, "code": None, "file": None, "proc": proc,
           "started": time.time()}
    with jobs_lock:
        jobs[jid] = job
    threading.Thread(target=pump, args=(job, cmd), daemon=True).start()
    return jid


def pump(job: dict, cmd: list[str]) -> None:
    proc = job["proc"]
    for raw in iter(proc.stdout.readline, b""):
        line = ANSI.sub("", raw.decode("utf-8", "replace")).rstrip("\r\n")
        line = line.split("\r")[-1]  # progress bars redraw with \r: keep the last frame
        if NOISE.search(line):
            continue
        if len(job["lines"]) < MAX_LINES:
            job["lines"].append(line)
    proc.wait()
    job["code"] = proc.returncode
    stamp = datetime.now().strftime("%Y-%m-%d %H%M%S")
    name = f"{stamp} {safe_name(job['toolname'] or job['tool'])} {safe_name(job['query'])}.txt"
    path = os.path.join(case_dir(job["case"]), "results", name)
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"{job['title']} ({job['toolname']})\nLooked up: {job['query']}\n"
                    f"When: {datetime.now():%Y-%m-%d %H:%M:%S}\n"
                    f"Command: {subprocess.list2cmdline(cmd) if IS_WIN else shlex.join(cmd)}\n"
                    + "-" * 60 + "\n")
            f.write("\n".join(job["lines"]) + "\n")
        job["file"] = path
    except OSError:
        pass
    add_history(job["case"], {"tool": job["tool"], "title": job["title"], "query": job["query"],
                              "kind": job["kind"], "how": "pc", "code": job["code"],
                              "src": job["src"] if job["kind"] == "file" else None,
                              "file": job["file"], "stopped": job.get("stopped", False)})
    job["done"] = True


def stop_job(jid: str) -> None:
    job = jobs.get(jid)
    if job and not job["done"]:
        job["stopped"] = True
        proc = job["proc"]
        if IS_WIN:
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)],
                           capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
            return

        # macOS/Linux: the tool leads its own process group (see start_job): ask nicely, then insist.
        def hit(sig):
            try:
                os.killpg(proc.pid, sig)
            except (ProcessLookupError, PermissionError):
                pass

        hit(signal.SIGTERM)
        threading.Timer(3.0, lambda: proc.poll() is None and hit(signal.SIGKILL)).start()


def inside(path: str, base: str) -> bool:
    """True when path is base or something under it (symlinks resolved, case ignored on Windows)."""
    try:
        p = os.path.normcase(os.path.realpath(path))
        b = os.path.normcase(os.path.realpath(base))
        return os.path.commonpath([p, b]) == b
    except ValueError:  # e.g. different drives
        return False


def reveal(path: str, select: bool) -> None:
    """Show a file or folder in the system file manager (Explorer / Finder / default)."""
    if os.environ.get("SPYGLASS_DRYRUN"):  # tests: don't open windows
        return
    if IS_WIN:
        if select:
            subprocess.Popen(["explorer", "/select,", path])
        else:
            os.startfile(path)
    elif IS_MAC:
        subprocess.Popen(["open", "-R", path] if select else ["open", path])
    else:
        subprocess.Popen(["xdg-open", os.path.dirname(path) if select else path])


def web_url(t: dict, q: str, kind: str) -> str:
    if kind == "file":
        return t.get("upload_url") or t["url"].split("?")[0]
    url = t["url"]
    i = url.find("{query}")
    if i > 0 and url[i - 1] == "/":
        # path position (e.g. web.archive.org/save/{query}): a whole URL goes in as-is
        return url.replace("{query}", quote(q, safe=":/"))
    return url.replace("{query}", quote(q, safe=""))


def clean_custom(c: dict) -> dict:
    title = str(c.get("title", "")).strip()[:80]
    if not title:
        raise ValueError("Give the tool a name.")
    types = [k for k, _ in TYPES if k in (c.get("types") or [])]
    if not types:
        raise ValueError("Tick at least one kind of thing it looks up.")
    out = {"id": str(c.get("id") or "custom-" + uuid.uuid4().hex[:8])[:40], "title": title,
           "detail": str(c.get("detail", "")).strip()[:300], "tool": str(c.get("tool", "")).strip()[:40],
           "types": types, "kind": c.get("kind")}
    if out["kind"] == "web":
        url = str(c.get("url", "")).strip()
        if not re.match(r"^https?://", url):
            raise ValueError("The web address has to start with http:// or https://")
        out["url"] = url
    elif out["kind"] == "pc":
        text = str(c.get("cmd", "")).strip()
        # Windows keeps backslashes in paths (posix=False); macOS/Linux use normal shell-style quoting.
        try:
            parts = [p.strip('"') for p in shlex.split(text, posix=not IS_WIN)] if text else []
        except ValueError:
            raise ValueError("The command has a quote mark that is never closed.") from None
        if not parts:
            raise ValueError("Type the command to run.")
        if "{query}" not in parts:
            parts.append("{query}")
        out["cmd"] = parts
    else:
        raise ValueError("Pick website or program.")
    return out


# ---------------------------------------------------------------- http

class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass

    def _ok_origin(self) -> bool:
        allowed = {f"127.0.0.1:{PORT}", f"localhost:{PORT}"}
        if self.headers.get("Host") not in allowed:
            return False
        origin = self.headers.get("Origin")
        return origin is None or urlparse(origin).netloc in allowed

    def _send(self, status: int, body: bytes, ctype: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, status: int = 200) -> None:
        self._send(status, json.dumps(obj).encode(), "application/json")

    def _body(self) -> bytes:
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n) if n else b""

    def do_GET(self):
        u = urlparse(self.path)
        if autoquit and autoquit.handle(self, u.path):
            return
        if not self._ok_origin():
            return self._send(403, b"forbidden", "text/plain")
        qs = {k: v[0] for k, v in parse_qs(u.query).items()}
        try:
            if u.path == "/api/state":
                s = load_settings()
                case_dir(s["case"])
                return self._json({"types": TYPES, "tools": all_tools(s), "cases": list_cases(),
                                   "case": s["case"], "dataFolder": DATA})
            if u.path == "/api/case":
                return self._json(read_case(qs.get("name", "General")))
            if u.path == "/api/job":
                job = jobs.get(qs.get("id", ""))
                if not job:
                    return self._json({"error": "gone"}, 404)
                start = int(qs.get("from", 0))
                return self._json({"lines": job["lines"][start:], "next": len(job["lines"]),
                                   "done": job["done"], "code": job["code"], "file": job["file"],
                                   "stopped": job.get("stopped", False)})
            if u.path == "/api/jobs":
                return self._json([{k: j[k] for k in ("id", "tool", "title", "query", "done", "code")}
                                   for j in jobs.values() if not j["done"]])
        except ValueError as e:
            return self._json({"error": str(e)}, 400)
        return self._static(u.path)

    def _static(self, path: str):
        rel = "index.html" if path in ("/", "") else path.lstrip("/")
        full = os.path.normpath(os.path.join(SRC, rel))
        if not full.startswith(SRC + os.sep) or not os.path.isfile(full):
            return self._send(404, b"not found", "text/plain")
        types = {".html": "text/html; charset=utf-8", ".css": "text/css", ".js": "text/javascript",
                 ".svg": "image/svg+xml", ".png": "image/png", ".ico": "image/x-icon"}
        ext = os.path.splitext(full)[1].lower()
        with open(full, "rb") as f:
            body = f.read()
        if ext == ".html" and autoquit:
            body = autoquit.inject(body)
        self._send(200, body, types.get(ext, "application/octet-stream"))

    def do_POST(self):
        u = urlparse(self.path)
        if autoquit and autoquit.handle(self, u.path):
            return
        if not self._ok_origin():
            return self._send(403, b"forbidden", "text/plain")
        qs = {k: v[0] for k, v in parse_qs(u.query).items()}
        try:
            if u.path == "/api/upload":
                case = qs.get("case", "General")
                name = safe_name(os.path.basename(qs.get("name", "file")))
                root, ext = os.path.splitext(qs.get("name", ""))
                name = safe_name(root) + re.sub(r"[^\w.]", "", ext)[:10]
                dest = os.path.join(case_dir(case), "files", name)
                n = 1
                while os.path.exists(dest):
                    dest = os.path.join(case_dir(case), "files", f"{safe_name(root)} ({n}){ext}")
                    n += 1
                with open(dest, "wb") as f:
                    f.write(self._body())
                add_history(case, {"tool": "upload", "title": "Added a file", "query": os.path.basename(dest),
                                   "kind": "file", "how": "file", "file": dest})
                return self._json({"path": dest, "name": os.path.basename(dest)})

            d = json.loads(self._body() or b"{}")
            if u.path == "/api/run":
                t = find_tool(d.get("tool", ""))
                if not t:
                    raise ValueError("Unknown tool.")
                kind = d.get("kind", "")
                q = check_query(d.get("query"), kind)
                case = d.get("case", "General")
                if t["kind"] == "web":
                    url = web_url(t, q, kind)
                    if not os.environ.get("SPYGLASS_DRYRUN"):  # tests: log, don't open tabs
                        webbrowser.open(url)
                    add_history(case, {"tool": t["id"], "title": t["title"],
                                       "query": os.path.basename(q) if kind == "file" else q,
                                       "src": q if kind == "file" else None,
                                       "kind": kind, "how": "web", "url": url})
                    return self._json({"opened": url})
                return self._json({"job": start_job(case, t, q, kind)})
            if u.path == "/api/stop":
                stop_job(d.get("id", ""))
                return self._json({"ok": True})
            if u.path == "/api/case":
                name = str(d.get("name", "")).strip()
                case_dir(name)
                s = load_settings()
                s["case"] = name
                save_settings(s)
                return self._json(read_case(name))
            if u.path == "/api/notes":
                p = os.path.join(case_dir(d.get("case", "General")), "notes.md")
                with open(p, "w", encoding="utf-8") as f:
                    f.write(str(d.get("text", "")))
                return self._json({"ok": True})
            if u.path == "/api/prefs":
                s = load_settings()
                ids = {t["id"] for t in TOOLS} | {c["id"] for c in s["custom"]}
                s["favorites"] = [i for i in d.get("favorites", s["favorites"]) if i in ids]
                s["hidden"] = [i for i in d.get("hidden", s["hidden"]) if i in ids]
                save_settings(s)
                return self._json({"tools": all_tools(s)})
            if u.path == "/api/custom":
                s = load_settings()
                if d.get("delete"):
                    s["custom"] = [c for c in s["custom"] if c["id"] != d["delete"]]
                else:
                    c = clean_custom(d)
                    if any(t["id"] == c["id"] for t in TOOLS):
                        raise ValueError("That id belongs to a built-in tool.")
                    s["custom"] = [x for x in s["custom"] if x["id"] != c["id"]] + [c]
                save_settings(s)
                return self._json({"tools": all_tools(s)})
            if u.path == "/api/reveal":
                p = d.get("path")
                if p and os.path.exists(p) and inside(p, DATA):
                    reveal(os.path.normpath(p), select=True)
                else:
                    reveal(case_dir(d.get("case", "General")), select=False)
                return self._json({"ok": True})
        except ValueError as e:
            return self._json({"error": str(e)}, 400)
        self._send(404, b"not found", "text/plain")


class QuietServer(ThreadingHTTPServer):
    """Browsers drop idle connections all the time; that is not worth a traceback in the Terminal."""

    # On Windows SO_REUSEADDR lets a second copy bind the same port, so a double launch would start
    # two servers. Off there; on macOS/Linux it only allows a quick restart and is kept.
    allow_reuse_address = not IS_WIN

    def handle_error(self, request, client_address):
        if isinstance(sys.exc_info()[1], (ConnectionError, TimeoutError)):
            return
        super().handle_error(request, client_address)


def main(argv):
    if "--keep" in argv:
        os.environ["AUTOQUIT"] = "0"
    url = f"http://127.0.0.1:{PORT}/"
    try:
        os.makedirs(CASES, exist_ok=True)
    except OSError as e:  # e.g. macOS has not been allowed to use the Documents folder
        print(f"Spyglass cannot use its case folder {CASES}: {e}\n"
              "Allow access to Documents for this app, or set SPYGLASS_DATA to another folder.", flush=True)
        return 1
    try:
        httpd = QuietServer(("127.0.0.1", PORT), Handler)
    except OSError as e:
        print(f"Spyglass could not start on port {PORT}: {e.strerror or e}. "
              f"It may already be running: {url}", flush=True)
        if "--open" in argv and not os.environ.get("SPYGLASS_DRYRUN"):
            webbrowser.open(url)
        return 1
    httpd.daemon_threads = True
    print(f"Spyglass on {url}", flush=True)
    if "--open" in argv and not os.environ.get("SPYGLASS_DRYRUN"):
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    if autoquit:
        autoquit.Watchdog().start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
