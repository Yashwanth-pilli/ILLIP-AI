"""ILLIP desktop cat — a tiny always-on-top cat that lives on your screen.

Click the cat  -> starts the ILLIP server (if not running) and opens the app.
Drag the cat   -> move it anywhere; position is remembered.
Right-click    -> menu (Open ILLIP / Quit).

No dependencies beyond the Python standard library (tkinter).
Launched by the "ILLIP Cat" desktop shortcut that setup.ps1 creates.
"""
import json
import socket
import subprocess
import sys
import webbrowser
import tkinter as tk
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POS_FILE = ROOT / "data" / "cat_pos.json"
PORT = 8000
URL = f"http://localhost:{PORT}"
TRANSPARENT = "#010203"  # unlikely-to-appear color used as the transparency key


def server_up() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", PORT), timeout=1):
            return True
    except OSError:
        return False


def start_server() -> None:
    python = ROOT / ".venv" / "Scripts" / "pythonw.exe"
    subprocess.Popen(
        [str(python), "-m", "uvicorn", "app.main:app", "--port", str(PORT)],
        cwd=str(ROOT),
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


class Cat:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.overrideredirect(True)          # no title bar
        self.root.attributes("-topmost", True)    # always on top
        self.root.configure(bg=TRANSPARENT)
        self.root.attributes("-transparentcolor", TRANSPARENT)

        self.label = tk.Label(
            self.root, text="🐱", font=("Segoe UI Emoji", 30),
            bg=TRANSPARENT, cursor="hand2",
        )
        self.label.pack()

        x, y = self._load_pos()
        self.root.geometry(f"+{x}+{y}")

        self._drag_start = None
        self._moved = False
        self.label.bind("<ButtonPress-1>", self._press)
        self.label.bind("<B1-Motion>", self._drag)
        self.label.bind("<ButtonRelease-1>", self._release)
        self.label.bind("<Button-3>", self._menu)

        self._busy = False

    def _load_pos(self):
        try:
            p = json.loads(POS_FILE.read_text())
            return int(p["x"]), int(p["y"])
        except Exception:
            # bottom-right corner by default
            self.root.update_idletasks()
            return self.root.winfo_screenwidth() - 120, self.root.winfo_screenheight() - 160

    def _save_pos(self):
        try:
            POS_FILE.parent.mkdir(parents=True, exist_ok=True)
            POS_FILE.write_text(json.dumps({"x": self.root.winfo_x(), "y": self.root.winfo_y()}))
        except Exception:
            pass

    def _press(self, e):
        self._drag_start = (e.x_root, e.y_root, self.root.winfo_x(), self.root.winfo_y())
        self._moved = False

    def _drag(self, e):
        sx, sy, wx, wy = self._drag_start
        dx, dy = e.x_root - sx, e.y_root - sy
        if abs(dx) > 5 or abs(dy) > 5:
            self._moved = True
        self.root.geometry(f"+{wx + dx}+{wy + dy}")

    def _release(self, _e):
        if self._moved:
            self._save_pos()
        else:
            self.launch()

    def _menu(self, e):
        m = tk.Menu(self.root, tearoff=0)
        m.add_command(label="Open ILLIP", command=self.launch)
        m.add_separator()
        m.add_command(label="Quit cat", command=self.root.destroy)
        m.tk_popup(e.x_root, e.y_root)

    def launch(self):
        if self._busy:
            return
        if server_up():
            webbrowser.open(URL)
            return
        self._busy = True
        self.label.config(text="⏳")
        start_server()
        self._wait_for_server(tries=40)  # up to ~60 s for a cold start

    def _wait_for_server(self, tries):
        if server_up():
            self.label.config(text="🐱")
            self._busy = False
            webbrowser.open(URL)
        elif tries <= 0:
            self.label.config(text="😿")
            self._busy = False
            self.root.after(4000, lambda: self.label.config(text="🐱"))
        else:
            self.root.after(1500, lambda: self._wait_for_server(tries - 1))

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    if "--check" in sys.argv:  # ponytail: smallest self-check — logic paths import & resolve
        assert callable(server_up) and ROOT.name
        print("ok")
        sys.exit(0)
    Cat().run()
