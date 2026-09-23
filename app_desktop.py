"""Desktop app entry point: starts the FastAPI server in the background and
opens the interface in its own native window - no browser tab, no terminal
window to babysit. secone_brain.spec packages this into a standalone exe
(see README "Desktop app" section for the one-time PyInstaller build).

Everything else about the app (the server, the database, Calendar/Gmail
config) is unchanged - this file only adds a native window on top of it.
"""

import threading
import time
import urllib.error
import urllib.request

import uvicorn
import webview

from app.main import app

HOST = "127.0.0.1"
PORT = 8756  # an uncommon port, unlikely to collide with anything else


def _run_server() -> None:
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")


def _wait_for_server(url: str, timeout: float = 15.0) -> None:
    """Poll /health instead of a fixed sleep - reliable regardless of how
    long this particular machine takes to get uvicorn listening, and opens
    the window the moment it's actually ready rather than a guessed delay
    too short (a connection-refused flash) or too long (a slow launch)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(url, timeout=0.5)
            return
        except (urllib.error.URLError, ConnectionError, OSError):
            time.sleep(0.15)
    # Falls through anyway rather than hanging indefinitely - the window
    # will just show a connection error the user can reload once the
    # server does come up (e.g. an unusually slow first-run DB migration).


def main() -> None:
    server_thread = threading.Thread(target=_run_server, daemon=True)
    server_thread.start()
    _wait_for_server(f"http://{HOST}:{PORT}/health")

    webview.create_window(
        "Secone Brain",
        f"http://{HOST}:{PORT}/graph",
        width=1280,
        height=860,
        min_size=(800, 600),
    )
    webview.start()
    # webview.start() blocks until the window is closed; the server thread
    # is a daemon, so it's killed automatically when the process exits here.


if __name__ == "__main__":
    main()
