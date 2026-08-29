#!/usr/bin/env python3
"""
PocketClot — Server-Manager (macOS-GUI).

Doppelklick-Start über `PocketClot Server.command`, oder direkt:
    python3 pocket_claude_manager.py

Was er kann:
- Server starten/stoppen/neustarten (uvicorn als Subprocess)
- Cloudflare-Quick-Tunnel an/aus (temporäre `https://...trycloudflare.com`-URL)
- Bearer-Token aus .env anzeigen, in die Zwischenablage kopieren
- Tunnel-URL kopieren
- Live-Logs in einem Textfeld, mit "Kopieren" und "Leeren"
- Aufräumen beim Fensterschließen (kein Zombie-Server)

Keine externen Python-Dependencies — nur Tkinter aus der Standard-Lib.
"""
from __future__ import annotations

import os
import queue
import re
import signal
import subprocess
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import ttk, scrolledtext, messagebox

# -----------------------------------------------------------------------------
# Konfiguration

ROOT = Path(__file__).resolve().parent
ENV_FILE = ROOT / ".env"
DEFAULT_PORT = 8787
LOG_LINE_CAP = 5000          # so viele Zeilen halten wir maximal im Textfeld
POLL_INTERVAL_MS = 80        # Tkinter-Pollfrequenz für die Log-Queue
SHUTDOWN_GRACE_SEC = 5       # SIGTERM dann SIGKILL nach … Sekunden

CLOUDFLARED_BIN = "cloudflared"  # ggf. `brew install cloudflared`


# -----------------------------------------------------------------------------
# Helpers

def read_server_token() -> str:
    """Liest SERVER_TOKEN aus .env, oder gibt '' zurück."""
    if not ENV_FILE.exists():
        return ""
    try:
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line.startswith("SERVER_TOKEN="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return ""


def venv_python() -> str:
    """Pfad zum venv-Python, falls vorhanden — sonst System-Python."""
    cand = ROOT / ".venv" / "bin" / "python"
    if cand.exists():
        return str(cand)
    return sys.executable


def have_command(name: str) -> bool:
    try:
        subprocess.run(
            ["which", name],
            check=True, capture_output=True, timeout=2,
        )
        return True
    except Exception:
        return False


# -----------------------------------------------------------------------------
# Subprocess-Wrapper mit Live-Log-Pipe

class ManagedProcess:
    """Startet ein Subprocess und pipet stdout+stderr zeilenweise in eine Queue."""

    def __init__(self, label: str, log_queue: "queue.Queue[tuple[str, str]]"):
        self.label = label
        self.log_queue = log_queue
        self.proc: subprocess.Popen | None = None
        self._reader_thread: threading.Thread | None = None

    @property
    def running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def start(self, cmd: list[str], cwd: Path, env: dict | None = None) -> None:
        if self.running:
            return
        self.log_queue.put((self.label, f"$ {' '.join(cmd)}\n"))
        try:
            self.proc = subprocess.Popen(
                cmd,
                cwd=str(cwd),
                env=env or os.environ.copy(),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=1,
                text=True,
                # Eigene Prozess-Gruppe, damit wir die ganze Familie killen können
                start_new_session=True,
            )
        except FileNotFoundError as e:
            self.log_queue.put((self.label, f"FEHLER: {e}\n"))
            self.proc = None
            return
        self._reader_thread = threading.Thread(
            target=self._read_loop, daemon=True,
        )
        self._reader_thread.start()

    def _read_loop(self) -> None:
        assert self.proc and self.proc.stdout
        try:
            for line in self.proc.stdout:
                self.log_queue.put((self.label, line))
        except Exception as e:
            self.log_queue.put((self.label, f"[reader exit: {e}]\n"))
        rc = self.proc.wait() if self.proc else None
        self.log_queue.put((self.label, f"[Prozess beendet, exit={rc}]\n"))

    def stop(self) -> None:
        if not self.running or self.proc is None:
            return
        try:
            os.killpg(os.getpgid(self.proc.pid), signal.SIGTERM)
        except Exception as e:
            self.log_queue.put((self.label, f"SIGTERM fehlgeschlagen: {e}\n"))
        # Warte kurz, dann SIGKILL
        t0 = time.time()
        while self.running and (time.time() - t0) < SHUTDOWN_GRACE_SEC:
            time.sleep(0.1)
        if self.running:
            try:
                os.killpg(os.getpgid(self.proc.pid), signal.SIGKILL)
                self.log_queue.put((self.label, "SIGKILL gesendet.\n"))
            except Exception as e:
                self.log_queue.put((self.label, f"SIGKILL fehlgeschlagen: {e}\n"))


# -----------------------------------------------------------------------------
# GUI

class ManagerWindow:

    TRYCLOUDFLARE_PATTERN = re.compile(r"https://[a-zA-Z0-9\-]+\.trycloudflare\.com")

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("PocketClot Server")
        self.root.geometry("780x640")
        self.root.minsize(680, 520)

        self.log_queue: "queue.Queue[tuple[str, str]]" = queue.Queue()
        self.server_proc = ManagedProcess("server", self.log_queue)
        self.tunnel_proc = ManagedProcess("tunnel", self.log_queue)
        self.tunnel_url: str = ""

        self._build_ui()
        self._refresh_token()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(POLL_INTERVAL_MS, self._poll_logs)
        self.root.after(500, self._tick_status)

    # ----- UI-Aufbau -----

    def _build_ui(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("aqua")  # macOS-nativ falls verfügbar
        except tk.TclError:
            pass
        style.configure("Big.TButton", padding=(14, 10), font=("Helvetica", 13))
        style.configure("Status.TLabel", font=("Helvetica", 13))

        # Top: Server-Block
        top = ttk.Frame(self.root, padding=(16, 14, 16, 8))
        top.pack(fill="x")

        title = ttk.Label(top, text="PocketClot — Server",
                          font=("Helvetica", 18, "bold"))
        title.grid(row=0, column=0, columnspan=4, sticky="w")

        ttk.Label(top, text="Status:").grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.status_var = tk.StringVar(value="⚪ aus")
        ttk.Label(top, textvariable=self.status_var, style="Status.TLabel").grid(
            row=1, column=1, sticky="w", pady=(8, 0),
        )

        self.btn_start = ttk.Button(top, text="Server starten",
                                    style="Big.TButton", command=self.start_server)
        self.btn_stop = ttk.Button(top, text="Stoppen",
                                   style="Big.TButton", command=self.stop_server)
        self.btn_restart = ttk.Button(top, text="Neustart",
                                      style="Big.TButton", command=self.restart_server)
        self.btn_start.grid(row=2, column=0, sticky="ew", pady=(10, 0), padx=(0, 6))
        self.btn_stop.grid(row=2, column=1, sticky="ew", pady=(10, 0), padx=6)
        self.btn_restart.grid(row=2, column=2, sticky="ew", pady=(10, 0), padx=6)
        top.columnconfigure(0, weight=1)
        top.columnconfigure(1, weight=1)
        top.columnconfigure(2, weight=1)
        top.columnconfigure(3, weight=1)

        # URL + Token
        mid = ttk.Frame(self.root, padding=(16, 6, 16, 6))
        mid.pack(fill="x")

        ttk.Label(mid, text="Lokale URL:").grid(row=0, column=0, sticky="w")
        self.url_var = tk.StringVar(value=f"http://localhost:{DEFAULT_PORT}")
        url_entry = ttk.Entry(mid, textvariable=self.url_var, state="readonly", width=44)
        url_entry.grid(row=0, column=1, sticky="ew", padx=(8, 6))
        ttk.Button(mid, text="kopieren",
                   command=lambda: self._copy_to_clipboard(self.url_var.get())
                   ).grid(row=0, column=2)

        ttk.Label(mid, text="Tunnel-URL:").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.tunnel_url_var = tk.StringVar(value="— (Tunnel aus)")
        tunnel_entry = ttk.Entry(mid, textvariable=self.tunnel_url_var,
                                 state="readonly", width=44)
        tunnel_entry.grid(row=1, column=1, sticky="ew", padx=(8, 6), pady=(6, 0))
        ttk.Button(mid, text="kopieren",
                   command=lambda: self._copy_to_clipboard(self.tunnel_url)
                   ).grid(row=1, column=2, pady=(6, 0))

        ttk.Label(mid, text="Bearer-Token:").grid(row=2, column=0, sticky="w", pady=(6, 0))
        self.token_var = tk.StringVar(value="…")
        token_entry = ttk.Entry(mid, textvariable=self.token_var,
                                state="readonly", width=44, show="•")
        token_entry.grid(row=2, column=1, sticky="ew", padx=(8, 6), pady=(6, 0))
        self._token_visible = False
        self.btn_token_toggle = ttk.Button(
            mid, text="zeigen",
            command=lambda: self._toggle_token(token_entry),
        )
        self.btn_token_toggle.grid(row=2, column=2, pady=(6, 0))
        ttk.Button(mid, text="kopieren",
                   command=lambda: self._copy_to_clipboard(self.token_var.get())
                   ).grid(row=2, column=3, pady=(6, 0), padx=(6, 0))

        mid.columnconfigure(1, weight=1)

        # Tunnel-Buttons
        tunnel_row = ttk.Frame(self.root, padding=(16, 10, 16, 6))
        tunnel_row.pack(fill="x")
        ttk.Label(tunnel_row, text="Cloudflare Quick-Tunnel (temporäre öffentliche URL):").pack(anchor="w")
        btn_row = ttk.Frame(tunnel_row)
        btn_row.pack(fill="x", pady=(6, 0))
        self.btn_tunnel_start = ttk.Button(btn_row, text="Tunnel starten",
                                           command=self.start_tunnel)
        self.btn_tunnel_stop = ttk.Button(btn_row, text="Tunnel stoppen",
                                          command=self.stop_tunnel)
        self.btn_tunnel_start.pack(side="left", padx=(0, 6))
        self.btn_tunnel_stop.pack(side="left", padx=6)

        # Logs
        log_frame = ttk.Frame(self.root, padding=(16, 6, 16, 6))
        log_frame.pack(fill="both", expand=True)

        head = ttk.Frame(log_frame)
        head.pack(fill="x")
        ttk.Label(head, text="Logs", font=("Helvetica", 13, "bold")).pack(side="left")
        ttk.Button(head, text="Logs kopieren", command=self.copy_logs).pack(side="right", padx=(6, 0))
        ttk.Button(head, text="Logs leeren", command=self.clear_logs).pack(side="right")

        self.log_text = scrolledtext.ScrolledText(
            log_frame, wrap="word",
            font=("Menlo", 11),
            background="#0F1116", foreground="#E6E8EF",
            insertbackground="#E6E8EF",
            height=18,
        )
        self.log_text.pack(fill="both", expand=True, pady=(6, 0))
        self.log_text.tag_config("server", foreground="#9ECBFF")
        self.log_text.tag_config("tunnel", foreground="#FFD580")
        self.log_text.tag_config("meta", foreground="#A0A0A0")
        self.log_text.configure(state="disabled")

        # Footer
        footer = ttk.Frame(self.root, padding=(16, 0, 16, 12))
        footer.pack(fill="x")
        ttk.Label(footer, text=f"Arbeitsordner: {ROOT}",
                  foreground="#888").pack(anchor="w")

        self._update_button_states()

    # ----- Buttons -----

    def start_server(self) -> None:
        if self.server_proc.running:
            return
        self._append_log("meta", f"\n=== Server-Start: {time.strftime('%H:%M:%S')} ===\n")
        # Lokales Setup wie run-dev.sh es macht: existierendes .venv nutzen, sonst System-Python
        py = venv_python()
        env = os.environ.copy()
        env.setdefault("PYTHONUNBUFFERED", "1")
        self.server_proc.start(
            cmd=[py, "-m", "pocket_claude"],
            cwd=ROOT,
            env=env,
        )
        self._refresh_token()
        self._update_button_states()

    def stop_server(self) -> None:
        if not self.server_proc.running:
            return
        self._append_log("meta", f"\n=== Server-Stop: {time.strftime('%H:%M:%S')} ===\n")
        self.server_proc.stop()
        self._update_button_states()

    def restart_server(self) -> None:
        self.stop_server()
        self.root.after(800, self.start_server)

    def start_tunnel(self) -> None:
        if self.tunnel_proc.running:
            return
        if not have_command(CLOUDFLARED_BIN):
            messagebox.showwarning(
                "cloudflared fehlt",
                "Der `cloudflared`-Befehl ist nicht installiert.\n\n"
                "Im Terminal:\n    brew install cloudflared",
            )
            return
        self._append_log("meta", f"\n=== Tunnel-Start: {time.strftime('%H:%M:%S')} ===\n")
        self.tunnel_url_var.set("… verbinde …")
        self.tunnel_url = ""
        self.tunnel_proc.start(
            cmd=[CLOUDFLARED_BIN, "tunnel", "--no-autoupdate",
                 "--url", f"http://localhost:{DEFAULT_PORT}"],
            cwd=ROOT,
        )
        self._update_button_states()

    def stop_tunnel(self) -> None:
        if not self.tunnel_proc.running:
            return
        self._append_log("meta", f"\n=== Tunnel-Stop: {time.strftime('%H:%M:%S')} ===\n")
        self.tunnel_proc.stop()
        self.tunnel_url = ""
        self.tunnel_url_var.set("— (Tunnel aus)")
        self._update_button_states()

    # ----- Logs -----

    def copy_logs(self) -> None:
        text = self.log_text.get("1.0", "end-1c")
        self._copy_to_clipboard(text)
        messagebox.showinfo("Kopiert", "Die Logs sind jetzt in der Zwischenablage.")

    def clear_logs(self) -> None:
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def _append_log(self, tag: str, line: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", line, tag)
        # Trimm auf LOG_LINE_CAP Zeilen
        cnt = int(self.log_text.index("end-1c").split(".")[0])
        if cnt > LOG_LINE_CAP:
            self.log_text.delete("1.0", f"{cnt - LOG_LINE_CAP}.0")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _poll_logs(self) -> None:
        drained = 0
        try:
            while drained < 200:  # max 200 Zeilen pro Tick — UI bleibt responsiv
                tag, line = self.log_queue.get_nowait()
                self._append_log(tag, line)
                drained += 1
                # Tunnel-URL detektieren
                if tag == "tunnel":
                    m = self.TRYCLOUDFLARE_PATTERN.search(line)
                    if m:
                        self.tunnel_url = m.group(0)
                        self.tunnel_url_var.set(self.tunnel_url)
        except queue.Empty:
            pass
        self.root.after(POLL_INTERVAL_MS, self._poll_logs)

    # ----- Status-Refresh -----

    def _tick_status(self) -> None:
        if self.server_proc.running:
            self.status_var.set("🟢 läuft")
        else:
            self.status_var.set("⚪ aus")
        self._update_button_states()
        self.root.after(500, self._tick_status)

    def _update_button_states(self) -> None:
        running = self.server_proc.running
        self.btn_start.configure(state=("disabled" if running else "normal"))
        self.btn_stop.configure(state=("normal" if running else "disabled"))
        self.btn_restart.configure(state=("normal" if running else "disabled"))

        tr = self.tunnel_proc.running
        self.btn_tunnel_start.configure(state=("disabled" if tr else "normal"))
        self.btn_tunnel_stop.configure(state=("normal" if tr else "disabled"))

    # ----- Token -----

    def _refresh_token(self) -> None:
        tok = read_server_token()
        self.token_var.set(tok or "(nicht gefunden — startet beim ersten Server-Start)")

    def _toggle_token(self, entry: ttk.Entry) -> None:
        self._token_visible = not self._token_visible
        entry.configure(show="" if self._token_visible else "•")
        self.btn_token_toggle.configure(text="verbergen" if self._token_visible else "zeigen")

    # ----- Clipboard -----

    def _copy_to_clipboard(self, value: str) -> None:
        if not value:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(value)
        self.root.update()  # macht den Inhalt zugänglich für andere Apps

    # ----- Schließen -----

    def _on_close(self) -> None:
        if self.server_proc.running or self.tunnel_proc.running:
            if not messagebox.askyesno(
                "Beenden?",
                "Server / Tunnel laufen noch. Beim Schließen werden sie gestoppt.\n\nWirklich beenden?",
            ):
                return
        # Asynchron beenden, damit das Fenster nicht hängt
        threading.Thread(target=self._shutdown_and_quit, daemon=True).start()

    def _shutdown_and_quit(self) -> None:
        self.tunnel_proc.stop()
        self.server_proc.stop()
        # Tkinter aus Main-Thread sauber beenden
        self.root.after(50, self.root.destroy)


def main() -> None:
    root = tk.Tk()
    ManagerWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()
