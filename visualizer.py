"""
Keystroke Visualizer — desktop app with Magic Keyboard–style overlay.
Control window for light/dark theme; keys appear at bottom center over any app.
Visible overlay only; does not log or save keystrokes.
"""

from __future__ import annotations

import ctypes
import json
import sys
import threading
import tkinter as tk
from collections import deque
from pathlib import Path
from typing import Deque, Optional

from pynput import keyboard

# Win32
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
HWND_TOPMOST = -1
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040

user32 = ctypes.windll.user32


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


CONFIG_PATH = app_dir() / "settings.json"

# Timing
IDLE_HIDE_MS = 1200
FADE_STEPS = 14
FADE_INTERVAL_MS = 35

TRANSPARENT = "#010101"

THEMES = {
    "light": {
        "chassis": "#c9c9c9",
        "chassis_edge": "#b8b8b8",
        "key_face": "#ececec",
        "key_side": "#d5d5d5",
        "key_edge": "#d8d8d8",
        "label": "#4a4a4a",
        "shadow": "#b0b0b0",
    },
    "dark": {
        "chassis": "#2c2c2e",
        "chassis_edge": "#1c1c1e",
        "key_face": "#3a3a3c",
        "key_side": "#1f1f21",
        "key_edge": "#48484a",
        "label": "#f2f2f7",
        "shadow": "#0a0a0a",
    },
}

# App chrome (control window)
UI = {
    "light": {
        "bg": "#f5f5f7",
        "card": "#ffffff",
        "text": "#1d1d1f",
        "muted": "#6e6e73",
        "accent": "#0071e3",
        "accent_text": "#ffffff",
        "border": "#d2d2d7",
        "toggle_off": "#d2d2d7",
    },
    "dark": {
        "bg": "#1c1c1e",
        "card": "#2c2c2e",
        "text": "#f5f5f7",
        "muted": "#98989d",
        "accent": "#0a84ff",
        "accent_text": "#ffffff",
        "border": "#3a3a3c",
        "toggle_off": "#3a3a3c",
    },
}

KEY_SIZE = 78
RADIUS = 16
GAP = 8
CHASSIS_PAD_X = 6
CHASSIS_PAD_Y = 6
SHADOW_EXTRA = 5
CHASSIS_RADIUS = 18
BOTTOM_MARGIN = 80
FONT = ("Segoe UI", 26)
FONT_ICON = ("Segoe UI Symbol", 28)
FONT_SMALL = ("Segoe UI", 13)

# Compact legends: icons where clear, short text otherwise (always fits)
SPECIAL_NAMES = {
    keyboard.Key.space: "␣",
    keyboard.Key.enter: "⏎",
    keyboard.Key.tab: "⇥",
    keyboard.Key.backspace: "⌫",
    keyboard.Key.delete: "⌦",
    keyboard.Key.esc: "esc",
    keyboard.Key.up: "↑",
    keyboard.Key.down: "↓",
    keyboard.Key.left: "←",
    keyboard.Key.right: "→",
    keyboard.Key.home: "home",
    keyboard.Key.end: "end",
    keyboard.Key.page_up: "pgup",
    keyboard.Key.page_down: "pgdn",
    keyboard.Key.insert: "ins",
    keyboard.Key.caps_lock: "⇪",
    keyboard.Key.print_screen: "prt",
    keyboard.Key.scroll_lock: "scr",
    keyboard.Key.pause: "pause",
    keyboard.Key.menu: "☰",
    keyboard.Key.cmd: "⊞",
    keyboard.Key.cmd_l: "⊞",
    keyboard.Key.cmd_r: "⊞",
}

MODIFIER_KEYS = {
    keyboard.Key.ctrl,
    keyboard.Key.ctrl_l,
    keyboard.Key.ctrl_r,
    keyboard.Key.alt,
    keyboard.Key.alt_l,
    keyboard.Key.alt_r,
    keyboard.Key.alt_gr,
    keyboard.Key.shift,
    keyboard.Key.shift_l,
    keyboard.Key.shift_r,
    keyboard.Key.cmd,
    keyboard.Key.cmd_l,
    keyboard.Key.cmd_r,
}

MODIFIER_LABEL = {
    keyboard.Key.ctrl: "ctrl",
    keyboard.Key.ctrl_l: "ctrl",
    keyboard.Key.ctrl_r: "ctrl",
    keyboard.Key.alt: "alt",
    keyboard.Key.alt_l: "alt",
    keyboard.Key.alt_r: "alt",
    keyboard.Key.alt_gr: "alt",
    keyboard.Key.shift: "⇧",
    keyboard.Key.shift_l: "⇧",
    keyboard.Key.shift_r: "⇧",
    keyboard.Key.cmd: "⊞",
    keyboard.Key.cmd_l: "⊞",
    keyboard.Key.cmd_r: "⊞",
}

# Icons / short glyphs — drawn larger and centered
ICON_LABELS = {
    "␣", "⏎", "⇥", "⌫", "⌦", "⇪", "⇧", "↑", "↓", "←", "→", "☰", "⊞",
}


def load_settings() -> dict:
    defaults = {"theme": "light", "enabled": True}
    try:
        if CONFIG_PATH.exists():
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if data.get("theme") in THEMES:
                defaults["theme"] = data["theme"]
            if isinstance(data.get("enabled"), bool):
                defaults["enabled"] = data["enabled"]
    except Exception:
        pass
    return defaults


def save_settings(settings: dict) -> None:
    try:
        CONFIG_PATH.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    except Exception:
        pass


def key_label(key: keyboard.Key | keyboard.KeyCode) -> Optional[str]:
    if isinstance(key, keyboard.Key):
        if key in SPECIAL_NAMES:
            return SPECIAL_NAMES[key]
        if key in MODIFIER_LABEL:
            return MODIFIER_LABEL[key]
        name = getattr(key, "name", None)
        if name:
            if name.startswith("f") and name[1:].isdigit():
                return name.lower()
            return name.replace("_", " ").lower()
        return None

    if key.char is not None:
        ch = key.char
        if ord(ch) < 32:
            return chr(ord(ch) + 64)
        return ch.upper() if ch.isalpha() else ch

    vk = getattr(key, "vk", None)
    if vk is not None and 0x30 <= vk <= 0x39:
        return chr(vk)
    if vk is not None and 0x41 <= vk <= 0x5A:
        return chr(vk)
    return None


def is_modifier(key: keyboard.Key | keyboard.KeyCode) -> bool:
    return isinstance(key, keyboard.Key) and key in MODIFIER_KEYS


def _round_rect(
    canvas: tk.Canvas, x1: float, y1: float, x2: float, y2: float, r: float, **kwargs
) -> int:
    r = min(r, (x2 - x1) / 2, (y2 - y1) / 2)
    points = [
        x1 + r, y1,
        x2 - r, y1,
        x2, y1,
        x2, y1 + r,
        x2, y2 - r,
        x2, y2,
        x2 - r, y2,
        x1 + r, y2,
        x1, y2,
        x1, y2 - r,
        x1, y1 + r,
        x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, splinesteps=36, **kwargs)


def key_width_for(label: str, size: int = KEY_SIZE) -> int:
    if label == "␣":
        return int(size * 2.4)
    if label in ICON_LABELS:
        return size
    # Text labels: pad enough so nothing clips
    char_w = max(9, int(size * 0.14))
    return max(size, int(size * 0.45) + len(label) * char_w)


def draw_keycap(
    canvas: tk.Canvas,
    x: int,
    y: int,
    w: int,
    h: int,
    text: str,
    theme: dict,
    font=FONT,
    font_icon=FONT_ICON,
    font_small=FONT_SMALL,
) -> None:
    radius = max(10, int(h * 0.2))
    face_h = h - 2
    _round_rect(
        canvas, x + 1, y + 3, x + w + 1, y + h + 3, radius, fill=theme["shadow"], outline=""
    )
    _round_rect(
        canvas, x, y + 2, x + w, y + h, radius, fill=theme["key_side"], outline=""
    )
    _round_rect(
        canvas,
        x,
        y,
        x + w,
        y + face_h,
        radius,
        fill=theme["key_face"],
        outline=theme["key_edge"],
        width=1,
    )

    cx = x + w / 2
    cy = y + face_h / 2
    if text in ICON_LABELS or len(text) == 1:
        canvas.create_text(
            cx, cy, text=text, fill=theme["label"], font=font_icon if text in ICON_LABELS else font
        )
    else:
        # Short words (ctrl, alt, esc, f1…) — always centered
        canvas.create_text(
            cx, cy, text=text, fill=theme["label"], font=font_small
        )


def draw_keys_group(
    canvas: tk.Canvas,
    labels: list[str],
    theme: dict,
    key_size: int = KEY_SIZE,
    pad_x: int = CHASSIS_PAD_X,
    pad_y: int = CHASSIS_PAD_Y,
) -> tuple[int, int]:
    widths = [key_width_for(t, key_size) for t in labels]
    gap = max(6, key_size // 10)
    inner_w = sum(widths) + gap * max(0, len(labels) - 1)
    total_w = inner_w + pad_x * 2
    total_h = key_size + pad_y * 2 + SHADOW_EXTRA
    chassis_r = max(12, int(key_size * 0.23))

    canvas.delete("all")
    canvas.config(width=total_w, height=total_h)
    _round_rect(
        canvas,
        1,
        1,
        total_w - 1,
        total_h - 1,
        chassis_r,
        fill=theme["chassis"],
        outline=theme["chassis_edge"],
        width=1,
    )

    x = pad_x
    y = pad_y
    font = ("Segoe UI", max(16, int(key_size * 0.34)))
    font_icon = ("Segoe UI Symbol", max(18, int(key_size * 0.36)))
    font_small = ("Segoe UI Semibold", max(11, int(key_size * 0.22)))
    for i, text in enumerate(labels):
        draw_keycap(
            canvas, x, y, widths[i], key_size, text, theme, font, font_icon, font_small
        )
        x += widths[i] + gap
    return total_w, total_h


class Overlay:
    """Always-on-top click-through key display."""

    def __init__(self, master: tk.Tk, theme_name: str) -> None:
        self.master = master
        self.theme_name = theme_name
        self.enabled = True

        self.win = tk.Toplevel(master)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.configure(bg=TRANSPARENT)
        self.win.attributes("-transparentcolor", TRANSPARENT)
        self.win.attributes("-alpha", 0.98)
        self.win.withdraw()

        self.canvas = tk.Canvas(
            self.win,
            bg=TRANSPARENT,
            highlightthickness=0,
            bd=0,
            width=200,
            height=KEY_SIZE + CHASSIS_PAD_Y * 2 + 16,
        )
        self.canvas.pack()

        self.pressed_mods: set[str] = set()
        self.hide_after_id: Optional[str] = None
        self.fade_after_id: Optional[str] = None
        self.visible = False
        self._lock = threading.Lock()
        self._pending: Deque[list[str]] = deque()

        self._listener: Optional[keyboard.Listener] = None
        self._hotkey: Optional[keyboard.GlobalHotKeys] = None

        self.win.after(50, self._make_clickthrough)
        self.win.after(16, self._drain_pending)

    @property
    def theme(self) -> dict:
        return THEMES[self.theme_name]

    def set_theme(self, name: str) -> None:
        if name in THEMES:
            self.theme_name = name

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        if not enabled:
            self._hide_instant()

    def start(self) -> None:
        if self._listener is None:
            self._listener = keyboard.Listener(
                on_press=self._on_press,
                on_release=self._on_release,
            )
            self._listener.daemon = True
            self._listener.start()
        if self._hotkey is None:
            self._hotkey = keyboard.GlobalHotKeys({"<ctrl>+<alt>+q": self._request_quit})
            self._hotkey.daemon = True
            self._hotkey.start()

    def stop(self) -> None:
        for listener in (self._listener, self._hotkey):
            if listener is None:
                continue
            try:
                listener.stop()
            except Exception:
                pass
        self._listener = None
        self._hotkey = None
        self._hide_instant()

    def _request_quit(self) -> None:
        self.master.after(0, self.master.destroy)

    def _hwnd(self) -> int:
        self.win.update_idletasks()
        hwnd = self.win.winfo_id()
        parent = user32.GetParent(hwnd)
        while parent:
            hwnd = parent
            parent = user32.GetParent(hwnd)
        return int(hwnd)

    def _make_clickthrough(self) -> None:
        try:
            hwnd = self._hwnd()
            style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            style |= WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
            user32.SetWindowPos(
                hwnd,
                HWND_TOPMOST,
                0,
                0,
                0,
                0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW,
            )
        except Exception:
            pass

    def _position(self) -> None:
        self.win.update_idletasks()
        sw = self.win.winfo_screenwidth()
        sh = self.win.winfo_screenheight()
        w = max(self.win.winfo_reqwidth(), 80)
        h = max(self.win.winfo_reqheight(), 40)
        x = (sw - w) // 2
        y = sh - h - BOTTOM_MARGIN
        self.win.geometry(f"{w}x{h}+{x}+{y}")
        self._make_clickthrough()

    def _mod_order(self) -> list[str]:
        order = ["ctrl", "⇧", "alt", "⊞"]
        return [m for m in order if m in self.pressed_mods]

    def _on_press(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        if not self.enabled:
            return
        label = key_label(key)
        if not label:
            return
        with self._lock:
            if is_modifier(key):
                self.pressed_mods.add(label)
                self._pending.append(self._mod_order())
                return
            self._pending.append(self._mod_order() + [label])

    def _on_release(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        if not is_modifier(key):
            return
        label = key_label(key)
        if not label:
            return
        with self._lock:
            self.pressed_mods.discard(label)

    def _drain_pending(self) -> None:
        keys: Optional[list[str]] = None
        with self._lock:
            while self._pending:
                keys = self._pending.popleft()
        if keys is not None and self.enabled:
            self._show(keys)
        try:
            self.win.after(16, self._drain_pending)
        except tk.TclError:
            pass

    def _show(self, labels: list[str]) -> None:
        if not labels:
            return
        if self.hide_after_id:
            self.win.after_cancel(self.hide_after_id)
            self.hide_after_id = None
        if self.fade_after_id:
            self.win.after_cancel(self.fade_after_id)
            self.fade_after_id = None

        draw_keys_group(self.canvas, labels, self.theme)
        self.win.attributes("-alpha", 0.98)
        if not self.visible:
            self.win.deiconify()
            self.visible = True
        self._position()
        self.hide_after_id = self.win.after(IDLE_HIDE_MS, self._start_fade)

    def _start_fade(self) -> None:
        self._fade_step(FADE_STEPS)

    def _fade_step(self, remaining: int) -> None:
        if remaining <= 0:
            self._hide_instant()
            return
        try:
            self.win.attributes("-alpha", 0.98 * (remaining / FADE_STEPS))
            self.fade_after_id = self.win.after(
                FADE_INTERVAL_MS, lambda: self._fade_step(remaining - 1)
            )
        except tk.TclError:
            pass

    def _hide_instant(self) -> None:
        try:
            self.win.attributes("-alpha", 0.0)
            self.win.withdraw()
            self.canvas.delete("all")
        except tk.TclError:
            pass
        self.visible = False


class App:
    def __init__(self) -> None:
        self.settings = load_settings()
        self.root = tk.Tk()
        self.root.title("Keystroke Visualizer")
        self.root.minsize(360, 520)
        self.root.resizable(False, False)

        self.theme_var = tk.StringVar(value=self.settings["theme"])
        self.enabled_var = tk.BooleanVar(value=self.settings["enabled"])

        self.overlay = Overlay(self.root, self.settings["theme"])
        self.overlay.set_enabled(self.settings["enabled"])
        self.overlay.start()

        self._build_ui()
        self._apply_ui_theme()
        self.root.update_idletasks()
        req_w = max(380, self.root.winfo_reqwidth())
        req_h = max(540, self.root.winfo_reqheight() + 24)
        self.root.geometry(f"{req_w}x{req_h}")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self) -> None:
        self.frame = tk.Frame(self.root, padx=28, pady=20)
        self.frame.pack(fill="both", expand=True)

        self.title = tk.Label(
            self.frame,
            text="Keystroke Visualizer",
            font=("Segoe UI Semibold", 20),
            anchor="w",
        )
        self.title.pack(fill="x")

        self.subtitle = tk.Label(
            self.frame,
            text="Keys appear at the bottom center over any app.",
            font=("Segoe UI", 11),
            anchor="w",
            justify="left",
            wraplength=320,
        )
        self.subtitle.pack(fill="x", pady=(4, 16))

        # Preview card
        self.preview_card = tk.Frame(self.frame, padx=16, pady=14)
        self.preview_card.pack(fill="x", pady=(0, 16))

        self.preview_label = tk.Label(
            self.preview_card,
            text="Preview",
            font=("Segoe UI", 10),
            anchor="w",
        )
        self.preview_label.pack(fill="x", pady=(0, 10))

        self.preview_canvas = tk.Canvas(
            self.preview_card, highlightthickness=0, bd=0, height=90
        )
        self.preview_canvas.pack()
        self._refresh_preview()

        # Theme section
        self.theme_header = tk.Label(
            self.frame, text="Key style", font=("Segoe UI Semibold", 12), anchor="w"
        )
        self.theme_header.pack(fill="x", pady=(0, 10))

        self.theme_row = tk.Frame(self.frame)
        self.theme_row.pack(fill="x", pady=(0, 16))

        self.light_btn = tk.Button(
            self.theme_row,
            text="Light",
            font=("Segoe UI Semibold", 11),
            relief="flat",
            bd=0,
            padx=18,
            pady=10,
            cursor="hand2",
            command=lambda: self._set_theme("light"),
        )
        self.light_btn.pack(side="left", expand=True, fill="x", padx=(0, 6))

        self.dark_btn = tk.Button(
            self.theme_row,
            text="Dark",
            font=("Segoe UI Semibold", 11),
            relief="flat",
            bd=0,
            padx=18,
            pady=10,
            cursor="hand2",
            command=lambda: self._set_theme("dark"),
        )
        self.dark_btn.pack(side="left", expand=True, fill="x", padx=(6, 0))

        # Enable toggle
        self.toggle_row = tk.Frame(self.frame)
        self.toggle_row.pack(fill="x", pady=(4, 12))

        self.toggle_text = tk.Label(
            self.toggle_row,
            text="Show keystrokes",
            font=("Segoe UI Semibold", 12),
            anchor="w",
        )
        self.toggle_text.pack(side="left")

        self.toggle_btn = tk.Canvas(
            self.toggle_row, width=52, height=30, highlightthickness=0, cursor="hand2"
        )
        self.toggle_btn.pack(side="right")
        self.toggle_btn.bind("<Button-1>", lambda _e: self._toggle_enabled())

        self.hint = tk.Label(
            self.frame,
            text="Quit shortcut: Ctrl+Alt+Q",
            font=("Segoe UI", 10),
            anchor="w",
        )
        self.hint.pack(fill="x", pady=(8, 4))

    def _ui(self) -> dict:
        return UI[self.theme_var.get()]

    def _apply_ui_theme(self) -> None:
        c = self._ui()
        self.root.configure(bg=c["bg"])
        for w in (
            self.frame,
            self.theme_row,
            self.toggle_row,
            self.preview_card,
        ):
            w.configure(bg=c["bg"] if w is not self.preview_card else c["card"])

        self.preview_card.configure(bg=c["card"], highlightbackground=c["border"], highlightthickness=1)
        self.preview_canvas.configure(bg=c["card"])

        self.title.configure(bg=c["bg"], fg=c["text"])
        self.subtitle.configure(bg=c["bg"], fg=c["muted"])
        self.theme_header.configure(bg=c["bg"], fg=c["text"])
        self.preview_label.configure(bg=c["card"], fg=c["muted"])
        self.toggle_text.configure(bg=c["bg"], fg=c["text"])
        self.hint.configure(bg=c["bg"], fg=c["muted"])
        self.toggle_btn.configure(bg=c["bg"])

        selected = self.theme_var.get()
        for name, btn in (("light", self.light_btn), ("dark", self.dark_btn)):
            if name == selected:
                btn.configure(bg=c["accent"], fg=c["accent_text"], activebackground=c["accent"], activeforeground=c["accent_text"])
            else:
                btn.configure(
                    bg=c["card"],
                    fg=c["text"],
                    activebackground=c["border"],
                    activeforeground=c["text"],
                    highlightbackground=c["border"],
                    highlightthickness=1,
                )

        self._draw_toggle()
        self._refresh_preview()

    def _draw_toggle(self) -> None:
        c = self._ui()
        on = self.enabled_var.get()
        self.toggle_btn.delete("all")
        fill = c["accent"] if on else c["toggle_off"]
        # track
        self.toggle_btn.create_oval(1, 1, 29, 29, fill=fill, outline="")
        self.toggle_btn.create_oval(23, 1, 51, 29, fill=fill, outline="")
        self.toggle_btn.create_rectangle(15, 1, 37, 29, fill=fill, outline="")
        # knob
        kx = 28 if on else 2
        self.toggle_btn.create_oval(kx, 3, kx + 24, 27, fill="#ffffff", outline="")

    def _refresh_preview(self) -> None:
        theme = THEMES[self.theme_var.get()]
        draw_keys_group(
            self.preview_canvas,
            ["⇪"],
            theme,
            key_size=64,
            pad_x=6,
            pad_y=6,
        )

    def _set_theme(self, name: str) -> None:
        self.theme_var.set(name)
        self.overlay.set_theme(name)
        self.settings["theme"] = name
        save_settings(self.settings)
        self._apply_ui_theme()

    def _toggle_enabled(self) -> None:
        value = not self.enabled_var.get()
        self.enabled_var.set(value)
        self.overlay.set_enabled(value)
        self.settings["enabled"] = value
        save_settings(self.settings)
        self._draw_toggle()

    def _on_close(self) -> None:
        save_settings(
            {"theme": self.theme_var.get(), "enabled": self.enabled_var.get()}
        )
        self.overlay.stop()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()
        self.overlay.stop()


def main() -> None:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass

    App().run()


if __name__ == "__main__":
    main()
