#!/usr/bin/env python3
"""Look controls for the live DLSS 5 pass.

Writes settings through dlssnr-shmctl. Never stops the helper, never sends
quit or reset, and never touches the game directory.
"""

import os
import subprocess
import tkinter as tk
from tkinter import font as tkfont

SHM = os.environ.get("DLSSNR_SHM") or f"/tmp/dlssnr-{os.getuid()}/shm.bin"
SHMCTL = "dlssnr-shmctl"

STYLES = (("Default", 0), ("Natural", 1), ("Cinematic", 2))

# Create-time keys rebuild the model. The others land on the next frames.
REBUILD = {"style", "intensity", "localtone", "localstructure", "passes"}
# The helper's own ceiling unless the unlock flag is set. Four is inside it.
PASS_MIN = 1
PASS_MAX = 5

SLIDERS = (
    ("intensity", "Intensity", 0.0, 4.0, 0.05),
    ("localtone", "Local tone", 0.0, 4.0, 0.05),
    ("localstructure", "Local structure", 0.0, 4.0, 0.05),
    ("sharpness", "Sharpness", 0.0, 1.0, 0.05),
    ("detail", "Detail", 0.0, 4.0, 0.05),
    ("colour", "Colour", 0.0, 4.0, 0.05),
)

BG = "#171614"
PANEL = "#221f1c"
INK = "#f4efe6"
MUTED = "#a39888"
AMBER = "#c4a574"
AMBER_INK = "#1a140c"
LINE = "#3a342c"
OFF = "#2c2824"


def shm(*args):
    run = subprocess.run(
        [SHMCTL, SHM, *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if run.returncode != 0:
        err = (run.stderr or run.stdout or "shmctl failed").strip()
        raise RuntimeError(err)
    return run.stdout


def parse_pairs(text):
    out = {}
    for line in text.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        out[key] = value.strip()
    return out


def near(a, b):
    try:
        return abs(float(a) - float(b)) < 0.001
    except (TypeError, ValueError):
        return str(a) == str(b)


class Panel:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("DLSS 5")
        self.root.configure(bg=BG)
        self.root.resizable(False, False)
        self.loading = False
        self.dragging = False
        self.pending = {}
        self.after_id = None
        self.values = {}
        self.status_text = {}
        self.scales = {}
        self.value_labels = {}
        self.style_buttons = {}

        family = "Ubuntu" if "Ubuntu" in tkfont.families() else "Sans"
        self.font = tkfont.Font(family=family, size=11)
        self.font_small = tkfont.Font(family=family, size=9)
        self.font_title = tkfont.Font(family=family, size=13, weight="bold")

        outer = tk.Frame(self.root, bg=BG, padx=16, pady=14)
        outer.pack()

        tk.Label(outer, text="DLSS 5", bg=BG, fg=INK, font=self.font_title, anchor="w").pack(
            fill="x"
        )
        self.status = tk.Label(
            outer, text="Reading the pass…", bg=BG, fg=MUTED, font=self.font_small, anchor="w"
        )
        self.status.pack(fill="x", pady=(2, 12))

        tk.Label(outer, text="Style", bg=BG, fg=MUTED, font=self.font_small, anchor="w").pack(
            fill="x"
        )
        row = tk.Frame(outer, bg=BG)
        row.pack(fill="x", pady=(4, 12))
        for name, value in STYLES:
            button = tk.Button(
                row,
                text=name,
                font=self.font,
                relief="flat",
                bd=0,
                padx=12,
                pady=6,
                command=lambda v=value: self.choose_style(v),
            )
            button.pack(side="left", padx=(0, 6))
            self.style_buttons[value] = button

        switches = tk.Frame(outer, bg=PANEL, padx=10, pady=8)
        switches.pack(fill="x", pady=(0, 12))
        self.pass_var = tk.IntVar()
        self.raw_var = tk.IntVar()
        self._check(switches, "Pass on", self.pass_var, self.toggle_pass).pack(anchor="w")
        self._check(switches, "Model picture", self.raw_var, self.toggle_raw).pack(
            anchor="w", pady=(4, 0)
        )
        tk.Label(
            switches,
            text="Model picture is the raw answer. Uncheck it to blend the edit onto the frame.",
            bg=PANEL,
            fg=MUTED,
            font=self.font_small,
            wraplength=300,
            justify="left",
            anchor="w",
        ).pack(fill="x", pady=(6, 0))

        for key, label, lo, hi, step in SLIDERS:
            block = tk.Frame(outer, bg=BG)
            block.pack(fill="x", pady=(0, 2))
            head = tk.Frame(block, bg=BG)
            head.pack(fill="x")
            tk.Label(head, text=label, bg=BG, fg=INK, font=self.font, anchor="w").pack(side="left")
            shown = tk.Label(head, text="", bg=BG, fg=AMBER, font=self.font, anchor="e")
            shown.pack(side="right")
            scale = tk.Scale(
                block,
                from_=lo,
                to=hi,
                resolution=step,
                orient="horizontal",
                showvalue=False,
                bg=BG,
                fg=INK,
                troughcolor=OFF,
                activebackground=AMBER,
                highlightthickness=0,
                bd=0,
                sliderrelief="flat",
                length=320,
                command=lambda v, k=key: self.on_slide(k, v),
            )
            scale.pack(fill="x")
            scale.bind("<ButtonPress-1>", lambda _e: self._set_dragging(True))
            scale.bind("<ButtonRelease-1>", lambda _e: self._set_dragging(False))
            # A new window takes focus. The game's wheel must not move a slider
            # and rebuild the model underneath them.
            for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                scale.bind(seq, lambda _e: "break")
            self.scales[key] = scale
            self.value_labels[key] = shown

        passes = tk.Frame(outer, bg=BG)
        passes.pack(fill="x", pady=(10, 0))
        tk.Label(passes, text="Passes", bg=BG, fg=INK, font=self.font).pack(side="left")
        controls = tk.Frame(passes, bg=BG)
        controls.pack(side="right")
        minus = self._step_button(controls, "−", lambda: self.nudge_passes(-1))
        minus.pack(side="left")
        self.pass_count = tk.Label(
            controls, text="1", bg=BG, fg=AMBER, font=self.font_title, width=2
        )
        self.pass_count.pack(side="left", padx=8)
        plus = self._step_button(controls, "+", lambda: self.nudge_passes(1))
        plus.pack(side="left")
        # Buttons, not a spinbox. A focused spinbox treated the game's wheel
        # as a click and climbed the pass count on its own.
        for widget in (passes, controls, minus, plus, self.pass_count):
            for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                widget.bind(seq, lambda _e: "break")

        tk.Label(
            outer,
            text="Style, intensity, tone, structure, and passes rebuild the model for a moment. Each extra pass runs the model again. The other controls land on the next frames.",
            bg=BG,
            fg=MUTED,
            font=self.font_small,
            wraplength=320,
            justify="left",
        ).pack(fill="x", pady=(10, 0))
        tk.Label(
            outer,
            text="Closing this window leaves the pass running.",
            bg=BG,
            fg=MUTED,
            font=self.font_small,
            anchor="w",
        ).pack(fill="x", pady=(4, 0))

        self.root.update_idletasks()
        placed = os.environ.get("DLSSNR_PANEL_POS", "")
        if placed.startswith("+"):
            self.root.geometry(placed)
        else:
            width = self.root.winfo_width()
            screen = self.root.winfo_screenwidth()
            self.root.geometry(f"+{max(0, screen - width - 28)}+28")
        self.root.attributes("-topmost", True)
        self.refresh()
        self.root.after(1000, self.poll)
        print("panel ready", flush=True)
        self.root.mainloop()

    def _check(self, parent, text, variable, command):
        return tk.Checkbutton(
            parent,
            text=text,
            variable=variable,
            command=command,
            bg=PANEL,
            fg=INK,
            selectcolor=OFF,
            activebackground=PANEL,
            activeforeground=INK,
            font=self.font,
            anchor="w",
            highlightthickness=0,
            bd=0,
        )

    def _step_button(self, parent, text, command):
        return tk.Button(
            parent,
            text=text,
            command=command,
            font=self.font,
            bg=OFF,
            fg=INK,
            activebackground=LINE,
            activeforeground=INK,
            relief="flat",
            bd=0,
            padx=10,
            pady=2,
            highlightthickness=0,
        )

    def nudge_passes(self, delta):
        if self.loading:
            return
        try:
            current = int(float(self.values.get("passes", self.pass_count.cget("text"))))
        except ValueError:
            current = PASS_MIN
        value = max(PASS_MIN, min(PASS_MAX, current + delta))
        self.pass_count.configure(text=str(value))
        self.queue("passes", value)

    def _set_dragging(self, dragging):
        self.dragging = dragging
        if not dragging:
            self.flush()

    def paint_style(self, selected):
        for value, button in self.style_buttons.items():
            if value == selected:
                button.configure(bg=AMBER, fg=AMBER_INK, activebackground=AMBER, activeforeground=AMBER_INK)
            else:
                button.configure(bg=OFF, fg=INK, activebackground=LINE, activeforeground=INK)

    def refresh(self):
        try:
            settings = parse_pairs(shm("settings"))
            status = parse_pairs(shm("status"))
        except (OSError, RuntimeError) as exc:
            self.status.configure(text=str(exc))
            return
        self.loading = True
        try:
            self.values = settings
            style = int(float(settings.get("style", "0")))
            self.paint_style(style)
            self.pass_var.set(1 if near(settings.get("enabled", "0"), 1) else 0)
            raw = near(settings.get("bypass", "0"), 1)
            self.raw_var.set(1 if raw else 0)
            for key, _label, _lo, _hi, _step in SLIDERS:
                value = float(settings.get(key, "0"))
                if not near(self.scales[key].get(), value):
                    self.scales[key].set(value)
                self.value_labels[key].configure(text=f"{value:.2f}")
            self._compose_enabled(raw)
            try:
                count = int(float(settings.get("passes", "1")))
            except ValueError:
                count = PASS_MIN
            self.pass_count.configure(text=str(max(PASS_MIN, min(PASS_MAX, count))))
            self._paint_status(settings, status)
        finally:
            self.loading = False

    def _compose_enabled(self, raw):
        state = "disabled" if raw else "normal"
        color = MUTED if raw else INK
        for key in ("detail", "colour"):
            self.scales[key].configure(state=state, fg=color)
            self.value_labels[key].configure(fg=MUTED if raw else AMBER)

    def _paint_status(self, settings, status):
        names = {0: "Default", 1: "Natural", 2: "Cinematic"}
        style = names.get(int(float(settings.get("style", "0"))), "Style")
        if status.get("model_up") == "1":
            width = status.get("width", "?")
            height = status.get("height", "?")
            ms = status.get("layer_ms", "?")
            text = f"{style} · {width}×{height} · {ms} ms"
        elif status.get("initialised") == "1":
            text = f"{style} · model is down"
        else:
            text = "Helper isn't running"
        self.status.configure(text=text)

    def choose_style(self, value):
        self.paint_style(value)
        self.queue("style", value)

    def toggle_pass(self):
        self.queue("enabled", self.pass_var.get())

    def toggle_raw(self):
        raw = self.raw_var.get() == 1
        self._compose_enabled(raw)
        self.queue("bypass", 1 if raw else 0)

    def on_slide(self, key, value):
        shown = float(value)
        self.value_labels[key].configure(text=f"{shown:.2f}")
        if self.loading:
            return
        self.queue(key, shown)

    def queue(self, key, value):
        if self.loading:
            return
        if near(self.values.get(key), value):
            self.pending.pop(key, None)
            return
        self.pending[key] = value
        if self.dragging:
            return
        if self.after_id is not None:
            self.root.after_cancel(self.after_id)
        self.after_id = self.root.after(180, self.flush)

    def flush(self):
        self.after_id = None
        if not self.pending:
            return
        batch = dict(self.pending)
        self.pending.clear()
        for key, value in batch.items():
            if near(self.values.get(key), value):
                continue
            text = str(int(value)) if key in {"style", "enabled", "bypass", "passes"} else f"{float(value):.2f}"
            try:
                shm("set", key, text)
            except (OSError, RuntimeError) as exc:
                self.status.configure(text=str(exc))
                return
            self.values[key] = text
        # A create-time write settles for about a tenth of a second. Read back
        # after that so the status line shows the picture that is actually up.
        if any(key in REBUILD for key in batch):
            self.root.after(400, self.refresh)
        else:
            self.refresh()

    def poll(self):
        if not self.dragging and not self.pending and self.after_id is None:
            self.refresh()
        self.root.after(1000, self.poll)


if __name__ == "__main__":
    Panel()
