"""autoquit: make Spyglass's local web server exit when its page is closed.

Three parts:

  SCRIPT          JavaScript injected into the served HTML. It pings /__ping every
                  4 s while the page is open and beacons /__quit on unload.
  inject(html)    put SCRIPT right after <head> (bytes in, bytes out).
  Watchdog        thread that calls os._exit(0) when:
                    - a page connected and then stopped pinging for IDLE seconds
                    - no page ever connected within STARTUP seconds
                    - (Windows only) the parent process that started the server has died.
  handle(h, path) serve /__ping and /__quit from a BaseHTTPRequestHandler;
                  returns True when it consumed the request.

Usage in a handler's do_GET:
    if autoquit.handle(self, path): return
    ...
    body = autoquit.inject(body)   # for text/html responses
and once, before serve_forever():
    autoquit.Watchdog().start()

Set AUTOQUIT=0 in the environment to disable (for tests or a long session); server.py
does this for you when it is started with --keep.
"""
from __future__ import annotations

import os
import threading
import time

IDLE = 15.0        # seconds without a ping after a page was seen
STARTUP = 90.0     # seconds to wait for the first page
_TICK = 2.0

SCRIPT = (b"<script>(function(){if(window.__autoquit)return;window.__autoquit=1;"
          b"var p=function(){fetch('/__ping',{cache:'no-store',keepalive:true}).catch(function(){})};"
          b"p();setInterval(p,4000);"
          b"var bye=function(){try{navigator.sendBeacon('/__quit')}catch(e){}};"
          b"window.addEventListener('pagehide',bye);window.addEventListener('beforeunload',bye);"
          b"})();</script>")

_client_seen = False
_last_ping = 0.0
_lock = threading.Lock()


def enabled() -> bool:
    return os.environ.get("AUTOQUIT", "1") not in ("0", "false", "no", "off")


def touch() -> None:
    global _client_seen, _last_ping
    with _lock:
        _client_seen = True
        _last_ping = time.time()


def inject(html: bytes) -> bytes:
    if not enabled() or b"__autoquit" in html:
        return html
    low = html.lower()
    i = low.find(b"<head")
    if i >= 0:
        j = low.find(b">", i)
        if j >= 0:
            return html[: j + 1] + SCRIPT + html[j + 1 :]
    return SCRIPT + html


def handle(handler, path: str) -> bool:
    """Answer /__ping and /__quit. Any other path: return False, untouched."""
    if path == "/__ping":
        touch()
        _reply(handler, 204)
        return True
    if path == "/__quit":
        # A tab closed. Do not exit immediately: a reload also fires pagehide.
        # Just stop counting it as alive; the idle timer does the rest.
        global _last_ping
        with _lock:
            _last_ping = min(_last_ping, time.time() - IDLE + 5.0)
        _reply(handler, 204)
        return True
    return False


def _reply(handler, status: int) -> None:
    try:
        handler.send_response(status)
        handler.send_header("Cache-Control", "no-store")
        handler.send_header("Content-Length", "0")
        handler.end_headers()
    except (OSError, ValueError):
        pass


class _Parent:
    """Handle on the parent process (Windows only) so PID reuse cannot fool the check.

    On macOS and Linux this does nothing: closing the Terminal window that started the
    server ends it anyway, and the page-closed timer above still applies.
    """

    def __init__(self):
        self.h = None
        if os.name != "nt":
            return
        import ctypes  # only exists in a usable form on Windows
        SYNCHRONIZE = 0x00100000
        k32 = ctypes.windll.kernel32
        h = k32.OpenProcess(SYNCHRONIZE, False, os.getppid())
        self.h = h or None
        self._wait = k32.WaitForSingleObject

    def dead(self) -> bool:
        if not self.h:
            return False
        return self._wait(self.h, 0) == 0  # WAIT_OBJECT_0: process signalled


class Watchdog(threading.Thread):
    def __init__(self, idle: float = IDLE, startup: float = STARTUP,
                 watch_parent: bool = True, on_exit=None):
        super().__init__(daemon=True, name="autoquit")
        self.idle = idle
        self.startup = startup
        self.parent = _Parent() if watch_parent else None
        self.on_exit = on_exit

    def start(self):
        if enabled():
            super().start()
        return self

    def run(self):
        t0 = time.time()
        while True:
            time.sleep(_TICK)
            now = time.time()
            why = None
            with _lock:
                if _client_seen and now - _last_ping > self.idle:
                    why = "page closed"
                elif not _client_seen and now - t0 > self.startup:
                    why = "no page opened"
            if why is None and self.parent and self.parent.dead():
                why = "parent process exited"
            if why:
                try:
                    if self.on_exit:
                        self.on_exit(why)
                    else:
                        print(f"autoquit: {why}; exiting", flush=True)
                finally:
                    os._exit(0)
