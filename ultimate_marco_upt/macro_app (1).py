#!/usr/bin/env python3
"""
MacroMaster Pro - Configurable Macro Tool
A feature-rich macro application with anti-lag system and beautiful UI.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import json
import time
import os
import sys
import copy


# ─────────────────────────────────────────────
#  Check dependencies before importing
# ─────────────────────────────────────────────
def check_dependencies():
    missing = []
    for pkg in ["pynput", "pyautogui"]:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    if missing:
        print(f"Missing packages: {', '.join(missing)}")
        print(f"Install with: pip install {' '.join(missing)}")
        sys.exit(1)


check_dependencies()

import pyautogui
pyautogui.FAILSAFE = False   # ปิด kill-switch เมื่อเลื่อนเมาส์มุมจอ
pyautogui.PAUSE = 0          # ควบคุม delay เองทั้งหมด

from pynput.keyboard import Key, Listener as KeyboardListener

# ─────────────────────────────────────────────
#  Constants
# ─────────────────────────────────────────────
CONFIG_FILE = "macros_config.json"
APP_VERSION = "1.0.0"

ACTION_TYPES = ["key_press", "type_text", "mouse_click", "delay"]

ACTION_HINTS = {
    "key_press":    "Key name: a-z, 0-9, f1-f12, enter, space, tab, esc, ctrl, alt, shift, up/down/left/right, backspace, delete, home, end",
    "type_text":    "Text to type (e.g.: Hello World!)",
    "mouse_click":  "Button: left, right, or middle",
    "delay":        "Wait time in seconds (e.g.: 0.5 = half a second, 1.0 = one second)",
}

# Color palette
COLORS = {
    "bg":        "#0e0e1a",
    "bg2":       "#14142a",
    "bg3":       "#1a1a35",
    "panel":     "#11111f",
    "accent":    "#7c3aed",
    "accent2":   "#5b21b6",
    "accent3":   "#4c1d95",
    "green":     "#059669",
    "green2":    "#047857",
    "red":       "#dc2626",
    "red2":      "#b91c1c",
    "yellow":    "#d97706",
    "text":      "#e2e8f0",
    "text2":     "#94a3b8",
    "text3":     "#64748b",
    "border":    "#2d2d50",
    "highlight": "#8b5cf6",
    "glow":      "#a78bfa",
    "row_alt":   "#16162c",
}


# ─────────────────────────────────────────────
#  Data Models
# ─────────────────────────────────────────────
class MacroAction:
    """A single step in a macro sequence."""

    def __init__(self, action_type: str = "key_press",
                 value: str = "",
                 delay_after: float = 0.05):
        self.action_type = action_type
        self.value = value
        self.delay_after = float(delay_after)

    def to_dict(self) -> dict:
        return {
            "action_type": self.action_type,
            "value": self.value,
            "delay_after": self.delay_after,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "MacroAction":
        return cls(
            action_type=d.get("action_type", "key_press"),
            value=str(d.get("value", "")),
            delay_after=float(d.get("delay_after", 0.05)),
        )

    def display_type(self) -> str:
        icons = {
            "key_press": "⌨️ key_press",
            "type_text": "📝 type_text",
            "mouse_click": "🖱️ mouse_click",
            "delay": "⏱️ delay",
        }
        return icons.get(self.action_type, self.action_type)


class Macro:
    """A complete macro with trigger key and action list."""

    def __init__(self, name: str = "New Macro",
                 trigger_key: str = "",
                 actions=None):
        self.name = name
        self.trigger_key = trigger_key
        self.actions: list[MacroAction] = actions if actions is not None else []
        self.enabled = True
        self.loop = False
        self.loop_count = 1

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "trigger_key": self.trigger_key,
            "actions": [a.to_dict() for a in self.actions],
            "enabled": self.enabled,
            "loop": self.loop,
            "loop_count": self.loop_count,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Macro":
        m = cls(
            name=d.get("name", "Macro"),
            trigger_key=d.get("trigger_key", ""),
        )
        m.enabled = bool(d.get("enabled", True))
        m.loop = bool(d.get("loop", False))
        m.loop_count = max(1, int(d.get("loop_count", 1)))
        for ad in d.get("actions", []):
            m.actions.append(MacroAction.from_dict(ad))
        return m


# ─────────────────────────────────────────────
#  Macro Engine (anti-lag / thread-safe)
# ─────────────────────────────────────────────
class MacroEngine:
    """
    Thread-safe macro execution engine.
    ใช้ pyautogui สำหรับ inject key/mouse → ทำงานได้แม้แอพอื่นจะ focus อยู่

    Anti-lag features:
    - Each macro runs in a daemon thread → UI stays responsive.
    - Per-macro debounce: ignores triggers fired too quickly.
    - Global concurrent limit: caps simultaneous running macros.
    - Minimum action delay (1 ms) prevents CPU spinning.
    - Threading lock guards shared state.
    """

    # pyautogui key name map (ชื่อที่ผู้ใช้พิมพ์ → pyautogui key string)
    PYAG_KEY_MAP = {
        "enter": "enter", "return": "enter",
        "space": "space", "tab": "tab",
        "backspace": "backspace", "delete": "delete",
        "esc": "esc", "escape": "esc",
        "up": "up", "down": "down", "left": "left", "right": "right",
        "f1": "f1", "f2": "f2", "f3": "f3", "f4": "f4",
        "f5": "f5", "f6": "f6", "f7": "f7", "f8": "f8",
        "f9": "f9", "f10": "f10", "f11": "f11", "f12": "f12",
        "ctrl": "ctrl", "ctrl_l": "ctrlleft", "ctrl_r": "ctrlright",
        "alt": "alt", "alt_l": "altleft", "alt_r": "altright",
        "shift": "shift", "shift_l": "shiftleft", "shift_r": "shiftright",
        "home": "home", "end": "end",
        "page_up": "pageup", "page_down": "pagedown",
        "caps_lock": "capslock", "num_lock": "numlock",
        "print_screen": "printscreen", "pause": "pause",
        "insert": "insert", "win": "win", "windows": "win",
        # numpad
        "num0": "num0", "num1": "num1", "num2": "num2", "num3": "num3",
        "num4": "num4", "num5": "num5", "num6": "num6", "num7": "num7",
        "num8": "num8", "num9": "num9",
    }

    def __init__(self):
        self.speed_multiplier: float = 1.0
        self.debounce_delay: float = 0.3
        self.max_concurrent: int = 5
        self.active: bool = True

        self._lock = threading.Lock()
        self._last_trigger: dict = {}
        self._running_threads: list = []

    # ── Public ──────────────────────────────
    def execute(self, macro: Macro) -> None:
        """Trigger a macro (non-blocking)."""
        if not self.active or not macro.enabled:
            return
        if not self._debounce_ok(macro.name):
            return
        with self._lock:
            self._running_threads = [t for t in self._running_threads if t.is_alive()]
            if len(self._running_threads) >= self.max_concurrent:
                return
            t = threading.Thread(
                target=self._run,
                args=(copy.deepcopy(macro),),
                daemon=True,
                name=f"macro-{macro.name}",
            )
            self._running_threads.append(t)
        t.start()

    def stop_all(self) -> None:
        self.active = False

    def resume(self) -> None:
        self.active = True

    # ── Internal ────────────────────────────
    def _debounce_ok(self, name: str) -> bool:
        now = time.monotonic()
        with self._lock:
            last = self._last_trigger.get(name, 0.0)
            if now - last < self.debounce_delay:
                return False
            self._last_trigger[name] = now
        return True

    def _run(self, macro: Macro) -> None:
        try:
            count = macro.loop_count if macro.loop else 1
            for _ in range(count):
                if not self.active:
                    break
                for action in macro.actions:
                    if not self.active:
                        break
                    self._exec_action(action)
        except Exception as exc:
            print(f"[MacroEngine] Error in '{macro.name}': {exc}")

    def _exec_action(self, action: MacroAction) -> None:
        try:
            spd = max(0.01, self.speed_multiplier)

            if action.action_type == "key_press":
                key_str = action.value.strip().lower()
                pyag_key = self._to_pyag_key(key_str)
                if pyag_key:
                    pyautogui.keyDown(pyag_key)
                    time.sleep(max(0.001, 0.03 / spd))
                    pyautogui.keyUp(pyag_key)

            elif action.action_type == "type_text":
                if action.value:
                    # ตรวจสอบว่าเป็น ASCII หรือไม่
                    try:
                        action.value.encode("ascii")
                        is_ascii = True
                    except UnicodeEncodeError:
                        is_ascii = False

                    if is_ascii:
                        # ASCII ใช้ typewrite ได้ปกติ
                        pyautogui.typewrite(action.value, interval=max(0.001, 0.02 / spd))
                    else:
                        # Unicode (ไทย, ญี่ปุ่น ฯลฯ) → copy แล้ว Ctrl+V
                        try:
                            import pyperclip
                            pyperclip.copy(action.value)
                            time.sleep(0.05)
                            pyautogui.hotkey("ctrl", "v")
                        except ImportError:
                            # fallback: typewrite เฉพาะส่วน ASCII
                            safe = action.value.encode("ascii", "ignore").decode()
                            if safe:
                                pyautogui.typewrite(safe, interval=max(0.001, 0.02 / spd))

            elif action.action_type == "mouse_click":
                btn_map = {"right": "right", "middle": "middle"}
                btn = btn_map.get(action.value.strip().lower(), "left")
                pyautogui.click(button=btn)

            elif action.action_type == "delay":
                try:
                    wait = float(action.value) / spd
                    time.sleep(max(0.001, wait))
                except (ValueError, ZeroDivisionError):
                    pass
                return  # ไม่ต้องทำ post-action delay ซ้ำ

            # Post-action delay
            tail = action.delay_after / spd
            if tail > 0:
                time.sleep(max(0.001, tail))

        except Exception as exc:
            print(f"[MacroEngine] Action error ({action.action_type}): {exc}")

    def _to_pyag_key(self, key_str: str):
        """แปลงชื่อปุ่มเป็น pyautogui key string"""
        # ค้นใน map ก่อน
        if key_str in self.PYAG_KEY_MAP:
            return self.PYAG_KEY_MAP[key_str]
        # single char → ใช้ตรงได้เลย
        if len(key_str) == 1:
            return key_str
        # ลองส่งตรงให้ pyautogui (อาจรู้จักอยู่แล้ว)
        if key_str in pyautogui.KEYBOARD_KEYS:
            return key_str
        return None


# ─────────────────────────────────────────────
#  Action Edit Dialog
# ─────────────────────────────────────────────
class ActionDialog:
    """Popup dialog to add or edit a MacroAction."""

    def __init__(self, parent: tk.Misc, action: MacroAction = None,
                 default_type: str = "key_press"):
        self.result: MacroAction | None = None
        C = COLORS

        self.win = tk.Toplevel(parent)
        self.win.title("Edit Action")
        self.win.configure(bg=C["bg2"])
        self.win.resizable(False, False)
        self.win.grab_set()
        self.win.transient(parent)

        # Center on parent
        parent.update_idletasks()
        px = parent.winfo_rootx() + parent.winfo_width() // 2
        py = parent.winfo_rooty() + parent.winfo_height() // 2
        self.win.geometry(f"460x320+{px - 230}+{py - 160}")

        self._build(action, default_type, C)

    def _label(self, parent, text):
        return tk.Label(parent, text=text, bg=COLORS["bg2"],
                        fg=COLORS["text"], font=("Consolas", 10, "bold"))

    def _build(self, action, default_type, C):
        # Title bar
        title_bar = tk.Frame(self.win, bg=C["accent"], height=40)
        title_bar.pack(fill="x")
        title_bar.pack_propagate(False)
        tk.Label(title_bar, text="  ✏️  Edit Action",
                 bg=C["accent"], fg="white",
                 font=("Consolas", 11, "bold")).pack(side="left", padx=10, pady=8)

        body = tk.Frame(self.win, bg=C["bg2"])
        body.pack(fill="both", expand=True, padx=20, pady=15)

        # Type
        self._label(body, "Action Type").grid(row=0, column=0, sticky="w", pady=6)
        self.type_var = tk.StringVar(value=action.action_type if action else default_type)
        combo = ttk.Combobox(body, textvariable=self.type_var,
                             values=ACTION_TYPES, state="readonly", width=22)
        combo.grid(row=0, column=1, sticky="w", padx=(12, 0), pady=6)
        combo.bind("<<ComboboxSelected>>", self._update_hint)

        # Value
        self._label(body, "Value").grid(row=1, column=0, sticky="w", pady=6)
        self.value_var = tk.StringVar(value=action.value if action else "")
        entry = ttk.Entry(body, textvariable=self.value_var, width=30)
        entry.grid(row=1, column=1, sticky="ew", padx=(12, 0), pady=6)
        body.columnconfigure(1, weight=1)

        # Hint
        self.hint_var = tk.StringVar()
        tk.Label(body, textvariable=self.hint_var,
                 bg=C["bg2"], fg=C["text3"],
                 font=("Consolas", 8),
                 wraplength=320, justify="left").grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(0, 6))

        # Delay
        self._label(body, "Delay After (s)").grid(row=3, column=0, sticky="w", pady=6)
        self.delay_var = tk.StringVar(
            value=f"{action.delay_after:.3f}" if action else "0.050")
        delay_entry = ttk.Entry(body, textvariable=self.delay_var, width=12)
        delay_entry.grid(row=3, column=1, sticky="w", padx=(12, 0), pady=6)

        # Buttons
        btn_row = tk.Frame(body, bg=C["bg2"])
        btn_row.grid(row=4, column=0, columnspan=2, pady=(12, 0), sticky="e")

        self._btn(btn_row, "Cancel", C["bg3"], self.win.destroy).pack(side="right", padx=(6, 0))
        self._btn(btn_row, "✅  OK", C["green"], self._ok).pack(side="right")

        self._update_hint()

    def _btn(self, parent, text, color, cmd):
        return tk.Button(parent, text=text, bg=color, fg="white",
                         font=("Consolas", 10, "bold"),
                         relief="flat", padx=14, pady=6,
                         cursor="hand2", command=cmd,
                         activebackground=color)

    def _update_hint(self, *_):
        self.hint_var.set(ACTION_HINTS.get(self.type_var.get(), ""))

    def _ok(self):
        try:
            delay = float(self.delay_var.get())
        except ValueError:
            delay = 0.05
        delay = max(0.0, delay)
        self.result = MacroAction(
            action_type=self.type_var.get(),
            value=self.value_var.get(),
            delay_after=delay,
        )
        self.win.destroy()


# ─────────────────────────────────────────────
#  Main Application
# ─────────────────────────────────────────────
class MacroApp:
    """Main MacroMaster Pro application."""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title(f"MacroMaster Pro  v{APP_VERSION}")
        self.root.geometry("1040x680")
        self.root.minsize(860, 560)
        self.root.configure(bg=COLORS["bg"])

        self.macros: list[Macro] = []
        self.engine = MacroEngine()
        self.kb_listener: KeyboardListener | None = None
        self.is_running = False
        self.selected_idx: int | None = None
        self._recording_trigger = False
        self._record_listener: KeyboardListener | None = None

        self._setup_styles()
        self._build_ui()
        self._load_config()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ═══════════════════════════════════════════
    #  Styles
    # ═══════════════════════════════════════════
    def _setup_styles(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        C = COLORS

        style.configure("TFrame",       background=C["bg"])
        style.configure("Panel.TFrame", background=C["bg2"])
        style.configure("Card.TFrame",  background=C["bg3"])

        style.configure("TLabel", background=C["bg"], foreground=C["text"],
                         font=("Consolas", 10))
        style.configure("H1.TLabel", background=C["bg2"], foreground=C["text"],
                         font=("Consolas", 15, "bold"))
        style.configure("H2.TLabel", background=C["bg2"], foreground=C["glow"],
                         font=("Consolas", 11, "bold"))
        style.configure("Muted.TLabel", background=C["bg2"], foreground=C["text2"],
                         font=("Consolas", 9))
        style.configure("Card.TLabel", background=C["bg3"], foreground=C["text"],
                         font=("Consolas", 10))

        style.configure("TButton",
                         background=C["bg3"], foreground=C["text"],
                         font=("Consolas", 9, "bold"),
                         padding=(10, 5), relief="flat", borderwidth=0)
        style.map("TButton",
                   background=[("active", C["accent2"]), ("pressed", C["accent3"])],
                   foreground=[("active", "white")])

        style.configure("Primary.TButton",
                         background=C["accent"], foreground="white",
                         font=("Consolas", 9, "bold"), padding=(10, 5))
        style.map("Primary.TButton",
                   background=[("active", C["accent2"]), ("pressed", C["accent3"])])

        style.configure("Success.TButton",
                         background=C["green"], foreground="white",
                         font=("Consolas", 9, "bold"), padding=(10, 5))
        style.map("Success.TButton",
                   background=[("active", C["green2"]), ("pressed", "#065f46")])

        style.configure("Danger.TButton",
                         background=C["red"], foreground="white",
                         font=("Consolas", 9, "bold"), padding=(10, 5))
        style.map("Danger.TButton",
                   background=[("active", C["red2"]), ("pressed", "#991b1b")])

        style.configure("TEntry",
                         fieldbackground=C["bg3"], foreground=C["text"],
                         insertcolor=C["text"], font=("Consolas", 10),
                         bordercolor=C["border"], lightcolor=C["border"],
                         darkcolor=C["border"])

        style.configure("TSpinbox",
                         fieldbackground=C["bg3"], foreground=C["text"],
                         font=("Consolas", 10), arrowcolor=C["text2"],
                         bordercolor=C["border"])

        style.configure("TCombobox",
                         fieldbackground=C["bg3"], foreground=C["text"],
                         background=C["bg3"], font=("Consolas", 10),
                         arrowcolor=C["text2"],
                         selectbackground=C["accent"],
                         selectforeground="white")
        style.map("TCombobox",
                   fieldbackground=[("readonly", C["bg3"])],
                   selectbackground=[("readonly", C["accent"])])

        style.configure("TCheckbutton",
                         background=C["bg2"], foreground=C["text"],
                         font=("Consolas", 10))
        style.map("TCheckbutton",
                   background=[("active", C["bg2"])],
                   foreground=[("active", C["glow"])])

        style.configure("TScale",
                         background=C["bg2"], troughcolor=C["bg3"],
                         sliderrelief="flat", sliderlength=18,
                         troughrelief="flat")
        style.map("TScale",
                   background=[("active", C["accent"])])

        style.configure("TScrollbar",
                         background=C["bg3"], troughcolor=C["bg2"],
                         arrowcolor=C["text3"], relief="flat",
                         borderwidth=0)
        style.map("TScrollbar",
                   background=[("active", C["accent"])])

        style.configure("Treeview",
                         background=C["bg2"], foreground=C["text"],
                         fieldbackground=C["bg2"], rowheight=30,
                         font=("Consolas", 9), borderwidth=0,
                         relief="flat")
        style.configure("Treeview.Heading",
                         background=C["bg3"], foreground=C["glow"],
                         font=("Consolas", 9, "bold"), relief="flat",
                         borderwidth=0)
        style.map("Treeview",
                   background=[("selected", C["accent"])],
                   foreground=[("selected", "white")])

        style.configure("TNotebook",
                         background=C["bg"], tabmargins=[0, 4, 0, 0])
        style.configure("TNotebook.Tab",
                         background=C["bg3"], foreground=C["text2"],
                         padding=[16, 8], font=("Consolas", 10))
        style.map("TNotebook.Tab",
                   background=[("selected", C["bg2"])],
                   foreground=[("selected", C["glow"])])
        style.layout("TNotebook.Tab", [
            ("Notebook.tab", {"sticky": "nswe", "children": [
                ("Notebook.padding", {"side": "top", "sticky": "nswe", "children": [
                    ("Notebook.label", {"side": "top", "sticky": ""})
                ]})
            ]})
        ])

        self.root.option_add("*TCombobox*Listbox.background", C["bg3"])
        self.root.option_add("*TCombobox*Listbox.foreground", C["text"])
        self.root.option_add("*TCombobox*Listbox.selectBackground", C["accent"])
        self.root.option_add("*TCombobox*Listbox.font", "Consolas 10")

    # ═══════════════════════════════════════════
    #  UI Layout
    # ═══════════════════════════════════════════
    def _build_ui(self):
        C = COLORS
        self._build_header()
        self._build_main()
        self._build_footer()

    def _build_header(self):
        C = COLORS
        hdr = tk.Frame(self.root, bg=C["accent"], height=56)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        tk.Label(hdr, text="  ⚡  MacroMaster Pro",
                 bg=C["accent"], fg="white",
                 font=("Consolas", 18, "bold")).pack(side="left", padx=8)

        # Status pill (right side)
        pill = tk.Frame(hdr, bg=C["accent"])
        pill.pack(side="right", padx=18)
        self._status_dot = tk.Label(pill, text="●",
                                    bg=C["accent"], fg="#f87171",
                                    font=("Consolas", 14))
        self._status_dot.pack(side="left")
        self._status_lbl = tk.Label(pill, text=" STOPPED ",
                                    bg=C["accent"], fg="#f87171",
                                    font=("Consolas", 11, "bold"))
        self._status_lbl.pack(side="left")

    def _build_main(self):
        C = COLORS
        main = tk.Frame(self.root, bg=C["bg"])
        main.pack(fill="both", expand=True, padx=10, pady=(8, 0))

        # ── Left: macro list ──────────────────
        left = tk.Frame(main, bg=C["bg2"], width=260)
        left.pack(side="left", fill="y", padx=(0, 8))
        left.pack_propagate(False)
        self._build_left_panel(left)

        # ── Right: notebook ───────────────────
        right = tk.Frame(main, bg=C["bg"])
        right.pack(side="left", fill="both", expand=True)

        nb = ttk.Notebook(right)
        nb.pack(fill="both", expand=True)

        editor_tab = ttk.Frame(nb, style="Panel.TFrame")
        nb.add(editor_tab, text="  📝  Macro Editor  ")
        self._build_editor_tab(editor_tab)

        settings_tab = ttk.Frame(nb, style="Panel.TFrame")
        nb.add(settings_tab, text="  ⚙️  Settings  ")
        self._build_settings_tab(settings_tab)

    def _build_footer(self):
        C = COLORS
        bar = tk.Frame(self.root, bg=C["bg3"], height=52)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)

        # Big toggle button
        self._toggle_btn = tk.Button(
            bar, text="  ▶  START MACROS  ",
            bg=C["green"], fg="white",
            font=("Consolas", 12, "bold"),
            relief="flat", cursor="hand2",
            activebackground=C["green2"], activeforeground="white",
            command=self.toggle_macros, padx=8, pady=8)
        self._toggle_btn.pack(side="left", padx=12, pady=8)

        self._tkbtn(bar, "  💾 Save All  ", self._save_config, C["accent"]).pack(
            side="left", padx=(0, 6), pady=8)
        self._tkbtn(bar, "  📂 Load  ", self._load_config, C["bg"]).pack(
            side="left", pady=8)

        self._macro_count_lbl = tk.Label(
            bar, text="0 macros",
            bg=C["bg3"], fg=C["text2"],
            font=("Consolas", 10))
        self._macro_count_lbl.pack(side="right", padx=15)

    # ── Left Panel ──────────────────────────────
    def _build_left_panel(self, parent):
        C = COLORS

        tk.Label(parent, text="  Macros",
                 bg=C["bg2"], fg=C["glow"],
                 font=("Consolas", 12, "bold")).pack(anchor="w", pady=(10, 6), padx=4)

        # Listbox
        lf = tk.Frame(parent, bg=C["bg2"])
        lf.pack(fill="both", expand=True, padx=4)

        vsb = ttk.Scrollbar(lf)
        vsb.pack(side="right", fill="y")

        self._listbox = tk.Listbox(
            lf, bg=C["bg2"], fg=C["text"],
            selectbackground=C["accent"],
            selectforeground="white",
            font=("Consolas", 10),
            relief="flat", borderwidth=0,
            activestyle="none",
            cursor="hand2",
            yscrollcommand=vsb.set)
        self._listbox.pack(fill="both", expand=True)
        vsb.config(command=self._listbox.yview)
        self._listbox.bind("<<ListboxSelect>>", self._on_list_select)

        # Action buttons
        bf = tk.Frame(parent, bg=C["bg2"])
        bf.pack(fill="x", padx=4, pady=(6, 4))

        self._tkbtn(bf, "+ Add", self._add_macro, C["green"]).pack(
            side="left", expand=True, fill="x", padx=(0, 3))
        self._tkbtn(bf, "🗑 Del", self._delete_macro, C["red"]).pack(
            side="left", expand=True, fill="x")

        bf2 = tk.Frame(parent, bg=C["bg2"])
        bf2.pack(fill="x", padx=4, pady=(0, 6))
        self._tkbtn(bf2, "⬆", self._move_up, C["bg3"]).pack(side="left", expand=True, fill="x", padx=(0, 3))
        self._tkbtn(bf2, "⬇", self._move_down, C["bg3"]).pack(side="left", expand=True, fill="x")

    # ── Editor Tab ──────────────────────────────
    def _build_editor_tab(self, parent):
        C = COLORS

        # Placeholder when nothing is selected
        self._editor_placeholder = tk.Frame(parent, bg=C["bg2"])
        self._editor_placeholder.pack(fill="both", expand=True)
        tk.Label(self._editor_placeholder,
                 text="← Select or create a macro",
                 bg=C["bg2"], fg=C["text3"],
                 font=("Consolas", 13)).pack(expand=True)

        # Real editor (hidden initially)
        self._editor_frame = tk.Frame(parent, bg=C["bg2"])
        self._build_editor_widgets(self._editor_frame)

    def _build_editor_widgets(self, parent):
        C = COLORS
        PAD = {"padx": 16, "pady": 5}

        # ── Name ───────────────────────────────
        r = self._row(parent)
        self._lbl(r, "Name:", width=14)
        self.name_var = tk.StringVar()
        self.name_var.trace_add("write", self._on_name_change)
        ttk.Entry(r, textvariable=self.name_var, width=32).pack(side="left", fill="x", expand=True)

        # ── Trigger Key ────────────────────────
        r = self._row(parent)
        self._lbl(r, "Trigger Key:", width=14)
        self.trigger_var = tk.StringVar()
        ttk.Entry(r, textvariable=self.trigger_var, state="readonly", width=14).pack(side="left", padx=(0, 8))
        self._record_btn = self._tkbtn(r, "🎯 Record Key", self._start_record, C["accent"])
        self._record_btn.pack(side="left", padx=(0, 6))
        self._tkbtn(r, "Clear", lambda: self.trigger_var.set(""), C["bg3"]).pack(side="left")

        # ── Options ───────────────────────────
        r = self._row(parent)
        self._lbl(r, "Options:", width=14)
        self.enabled_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(r, text="Enabled", variable=self.enabled_var,
                         command=self._on_enabled_change).pack(side="left", padx=(0, 16))
        self.loop_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(r, text="Loop", variable=self.loop_var,
                         command=self._sync_macro_opts).pack(side="left", padx=(0, 8))
        tk.Label(r, text="× ", bg=C["bg2"], fg=C["text2"],
                 font=("Consolas", 10)).pack(side="left")
        self.loop_count_var = tk.StringVar(value="1")
        ttk.Spinbox(r, from_=1, to=9999, textvariable=self.loop_count_var,
                    width=6, command=self._sync_macro_opts).pack(side="left")

        # ── Actions header ────────────────────
        sep = tk.Frame(parent, bg=C["border"], height=1)
        sep.pack(fill="x", padx=16, pady=(8, 0))

        ah = tk.Frame(parent, bg=C["bg2"])
        ah.pack(fill="x", padx=16, pady=(8, 4))
        tk.Label(ah, text="Actions", bg=C["bg2"], fg=C["glow"],
                 font=("Consolas", 12, "bold")).pack(side="left")

        # Add-action buttons
        for label, atype in [("+ Key", "key_press"), ("+ Text", "type_text"),
                              ("+ Click", "mouse_click"), ("+ Delay", "delay")]:
            self._tkbtn(ah, label, lambda t=atype: self._add_action(t), C["accent2"]).pack(
                side="left", padx=(6, 0))

        # ── Treeview ──────────────────────────
        tv_frame = tk.Frame(parent, bg=C["bg2"])
        tv_frame.pack(fill="both", expand=True, padx=16, pady=(0, 4))

        cols = ("Type", "Value", "Delay (s)")
        self._tree = ttk.Treeview(tv_frame, columns=cols, show="headings", height=7)
        self._tree.heading("Type",     text="Type",     anchor="w")
        self._tree.heading("Value",    text="Value",    anchor="w")
        self._tree.heading("Delay (s)",text="Delay (s)", anchor="center")
        self._tree.column("Type",      width=130, minwidth=100, anchor="w")
        self._tree.column("Value",     width=240, minwidth=100, anchor="w")
        self._tree.column("Delay (s)", width=90,  minwidth=70,  anchor="center")

        vsb = ttk.Scrollbar(tv_frame, command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self._tree.bind("<Double-1>", lambda _: self._edit_action())
        self._tree.tag_configure("odd", background=C["row_alt"])

        # ── Action control buttons ────────────
        ctrl = tk.Frame(parent, bg=C["bg2"])
        ctrl.pack(fill="x", padx=16, pady=(0, 4))

        for label, cmd, clr in [
            ("✏️ Edit",  self._edit_action,   C["bg3"]),
            ("🗑 Remove", self._remove_action, C["red"]),
            ("⬆ Up",     self._move_action_up, C["bg3"]),
            ("⬇ Down",   self._move_action_down, C["bg3"]),
        ]:
            self._tkbtn(ctrl, label, cmd, clr).pack(side="left", padx=(0, 6))

        # ── Save button ───────────────────────
        sep2 = tk.Frame(parent, bg=C["border"], height=1)
        sep2.pack(fill="x", padx=16, pady=(4, 6))

        self._tkbtn(parent, "  💾  Save Macro  ",
                    self._save_macro, C["green"]).pack(
            padx=16, pady=(0, 12), anchor="w")

    # ── Settings Tab ────────────────────────────
    def _build_settings_tab(self, parent):
        C = COLORS

        canvas = tk.Canvas(parent, bg=C["bg2"], highlightthickness=0)
        vsb = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        sf = tk.Frame(canvas, bg=C["bg2"])

        sf.bind("<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfig(win_id, width=e.width))

        win_id = canvas.create_window((0, 0), window=sf, anchor="nw")
        canvas.configure(yscrollcommand=vsb.set)
        canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        def _scroll(e):
            canvas.yview_scroll(-1 * (e.delta // 120), "units")

        canvas.bind("<MouseWheel>", _scroll)
        sf.bind("<MouseWheel>", _scroll)

        # ── Speed ─────────────────────────────
        self._settings_section(sf, "⚡  Speed Multiplier",
                                "Higher = faster macro execution (all delays divided by this value)")
        sp_row = tk.Frame(sf, bg=C["bg2"])
        sp_row.pack(fill="x", padx=20, pady=(0, 4))

        self.speed_var = tk.DoubleVar(value=1.0)
        ttk.Scale(sp_row, from_=0.1, to=10.0, orient="horizontal",
                  variable=self.speed_var,
                  command=self._on_speed_change).pack(
            side="left", fill="x", expand=True, padx=(0, 12))
        self._speed_lbl = tk.Label(sp_row, text="1.0×",
                                   bg=C["bg2"], fg=C["glow"],
                                   font=("Consolas", 13, "bold"), width=6)
        self._speed_lbl.pack(side="left")

        preset_row = tk.Frame(sf, bg=C["bg2"])
        preset_row.pack(fill="x", padx=20, pady=(2, 0))
        tk.Label(preset_row, text="Presets:", bg=C["bg2"], fg=C["text2"],
                 font=("Consolas", 9)).pack(side="left", padx=(0, 8))
        for v in [0.5, 1.0, 2.0, 5.0, 10.0]:
            self._tkbtn(preset_row, f"{v}×",
                        lambda val=v: self._set_speed(val), C["accent2"]).pack(
                side="left", padx=3)

        self._settings_sep(sf)

        # ── Debounce ──────────────────────────
        self._settings_section(sf, "🛡️  Anti-Lag / Debounce Delay",
                                "Minimum seconds between trigger activations — prevents accidental re-fires and freezing")
        db_row = tk.Frame(sf, bg=C["bg2"])
        db_row.pack(fill="x", padx=20, pady=(0, 4))

        self.debounce_var = tk.DoubleVar(value=0.3)
        ttk.Scale(db_row, from_=0.0, to=3.0, orient="horizontal",
                  variable=self.debounce_var,
                  command=self._on_debounce_change).pack(
            side="left", fill="x", expand=True, padx=(0, 12))
        self._debounce_lbl = tk.Label(db_row, text="0.30s",
                                      bg=C["bg2"], fg=C["glow"],
                                      font=("Consolas", 13, "bold"), width=7)
        self._debounce_lbl.pack(side="left")

        self._settings_sep(sf)

        # ── Max concurrent ────────────────────
        self._settings_section(sf, "🔢  Max Concurrent Macros",
                                "Hard limit on simultaneously running macros — guards against system overload")
        mc_row = tk.Frame(sf, bg=C["bg2"])
        mc_row.pack(fill="x", padx=20, pady=(0, 4))
        self.max_concurrent_var = tk.StringVar(value="5")
        ttk.Spinbox(mc_row, from_=1, to=20,
                    textvariable=self.max_concurrent_var,
                    command=self._on_max_concurrent_change,
                    width=6).pack(side="left")
        tk.Label(mc_row, text="  macros", bg=C["bg2"], fg=C["text2"],
                 font=("Consolas", 10)).pack(side="left")
        self.max_concurrent_var.trace_add("write", lambda *_: self._on_max_concurrent_change())

        self._settings_sep(sf)

        # ── Info card ─────────────────────────
        info = tk.Frame(sf, bg=C["bg3"], relief="flat")
        info.pack(fill="x", padx=20, pady=(4, 20))
        tk.Label(info, text="  ℹ️  Anti-Lag System Details",
                 bg=C["bg3"], fg=C["highlight"],
                 font=("Consolas", 10, "bold")).pack(anchor="w", padx=12, pady=(10, 4))
        lines = [
            "• Each macro runs in its own daemon thread → UI always stays responsive",
            "• Per-macro debounce prevents rapid accidental re-triggers",
            "• Max-concurrent cap guards against thread explosion and lag spikes",
            "• Minimum action delay (1 ms) prevents CPU busy-spinning",
            "• Thread-safe lock protects shared state from race conditions",
        ]
        tk.Label(info, text="\n".join(lines),
                 bg=C["bg3"], fg=C["text2"],
                 font=("Consolas", 9), justify="left").pack(
            anchor="w", padx=12, pady=(0, 12))

    # ═══════════════════════════════════════════
    #  Macro List Operations
    # ═══════════════════════════════════════════
    def _add_macro(self):
        m = Macro(name=f"Macro {len(self.macros) + 1}")
        self.macros.append(m)
        self._refresh_list()
        self._listbox.selection_clear(0, "end")
        self._listbox.selection_set(len(self.macros) - 1)
        self._listbox.see(len(self.macros) - 1)
        self._on_list_select()

    def _delete_macro(self):
        idx = self._get_list_sel()
        if idx is None:
            messagebox.showwarning("No Selection", "Please select a macro to delete.")
            return
        name = self.macros[idx].name
        if messagebox.askyesno("Delete Macro", f"Delete «{name}»?"):
            self.macros.pop(idx)
            self.selected_idx = None
            self._refresh_list()
            self._show_placeholder()

    def _move_up(self):
        idx = self._get_list_sel()
        if idx is None or idx == 0:
            return
        self.macros[idx], self.macros[idx - 1] = self.macros[idx - 1], self.macros[idx]
        self._refresh_list()
        self._listbox.selection_set(idx - 1)
        self._on_list_select()

    def _move_down(self):
        idx = self._get_list_sel()
        if idx is None or idx >= len(self.macros) - 1:
            return
        self.macros[idx], self.macros[idx + 1] = self.macros[idx + 1], self.macros[idx]
        self._refresh_list()
        self._listbox.selection_set(idx + 1)
        self._on_list_select()

    def _refresh_list(self):
        self._listbox.delete(0, "end")
        for m in self.macros:
            icon = "✅" if m.enabled else "⭕"
            trigger = f"  [{m.trigger_key}]" if m.trigger_key else ""
            self._listbox.insert("end", f"  {icon}  {m.name}{trigger}")
        self._macro_count_lbl.config(
            text=f"{len(self.macros)} macro{'s' if len(self.macros) != 1 else ''}")

    def _on_list_select(self, event=None):
        idx = self._get_list_sel()
        if idx is None:
            return
        self.selected_idx = idx
        self._load_macro_to_editor(self.macros[idx])

    def _get_list_sel(self) -> int | None:
        sel = self._listbox.curselection()
        if not sel:
            return None
        idx = sel[0]
        if idx >= len(self.macros):
            return None
        return idx

    # ═══════════════════════════════════════════
    #  Editor Operations
    # ═══════════════════════════════════════════
    def _show_placeholder(self):
        self._editor_frame.pack_forget()
        self._editor_placeholder.pack(fill="both", expand=True)

    def _show_editor(self):
        self._editor_placeholder.pack_forget()
        self._editor_frame.pack(fill="both", expand=True)

    def _load_macro_to_editor(self, macro: Macro):
        self._show_editor()
        self.name_var.set(macro.name)
        self.trigger_var.set(macro.trigger_key)
        self.enabled_var.set(macro.enabled)
        self.loop_var.set(macro.loop)
        self.loop_count_var.set(str(macro.loop_count))
        self._refresh_tree(macro)

    def _refresh_tree(self, macro: Macro = None):
        if macro is None:
            if self.selected_idx is None:
                return
            macro = self.macros[self.selected_idx]
        self._tree.delete(*self._tree.get_children())
        for i, a in enumerate(macro.actions):
            tag = "odd" if i % 2 else ""
            self._tree.insert("", "end", iid=str(i),
                              values=(a.display_type(), a.value, f"{a.delay_after:.3f}"),
                              tags=(tag,))

    def _on_name_change(self, *_):
        if self.selected_idx is not None:
            self.macros[self.selected_idx].name = self.name_var.get()

    def _on_enabled_change(self):
        if self.selected_idx is not None:
            self.macros[self.selected_idx].enabled = self.enabled_var.get()
            self._refresh_list()

    def _sync_macro_opts(self, *_):
        if self.selected_idx is None:
            return
        m = self.macros[self.selected_idx]
        m.loop = self.loop_var.get()
        try:
            m.loop_count = max(1, int(self.loop_count_var.get()))
        except ValueError:
            pass

    # ── Trigger recording ────────────────────
    def _start_record(self):
        if self.selected_idx is None:
            messagebox.showwarning("No Macro", "Please select a macro first.")
            return
        if self._recording_trigger:
            return
        self._recording_trigger = True
        self._record_btn.config(text="🔴 Press any key…")

        def on_press(key):
            if not self._recording_trigger:
                return False
            key_str = self._key_to_str(key)
            self._recording_trigger = False
            self.trigger_var.set(key_str)
            if self.selected_idx is not None:
                self.macros[self.selected_idx].trigger_key = key_str
            self.root.after(0, lambda: self._record_btn.config(text="🎯 Record Key"))
            return False  # stop listener

        # Stop any previous record listener
        if self._record_listener and self._record_listener.is_alive():
            self._record_listener.stop()
        self._record_listener = KeyboardListener(on_press=on_press)
        self._record_listener.daemon = True
        self._record_listener.start()

    # ── Actions CRUD ─────────────────────────
    def _add_action(self, atype: str = "key_press"):
        if self.selected_idx is None:
            messagebox.showwarning("No Macro", "Please select a macro first.")
            return
        dlg = ActionDialog(self.root, default_type=atype)
        self.root.wait_window(dlg.win)
        if dlg.result:
            self.macros[self.selected_idx].actions.append(dlg.result)
            self._refresh_tree()

    def _edit_action(self):
        sel = self._tree.selection()
        if not sel or self.selected_idx is None:
            return
        idx = int(sel[0])
        macro = self.macros[self.selected_idx]
        if idx >= len(macro.actions):
            return
        dlg = ActionDialog(self.root, action=macro.actions[idx])
        self.root.wait_window(dlg.win)
        if dlg.result:
            macro.actions[idx] = dlg.result
            self._refresh_tree()

    def _remove_action(self):
        sel = self._tree.selection()
        if not sel or self.selected_idx is None:
            return
        idx = int(sel[0])
        macro = self.macros[self.selected_idx]
        if idx < len(macro.actions):
            macro.actions.pop(idx)
            self._refresh_tree()

    def _move_action_up(self):
        sel = self._tree.selection()
        if not sel or self.selected_idx is None:
            return
        idx = int(sel[0])
        macro = self.macros[self.selected_idx]
        if idx > 0:
            macro.actions[idx], macro.actions[idx - 1] = macro.actions[idx - 1], macro.actions[idx]
            self._refresh_tree()
            self._tree.selection_set(str(idx - 1))

    def _move_action_down(self):
        sel = self._tree.selection()
        if not sel or self.selected_idx is None:
            return
        idx = int(sel[0])
        macro = self.macros[self.selected_idx]
        if idx < len(macro.actions) - 1:
            macro.actions[idx], macro.actions[idx + 1] = macro.actions[idx + 1], macro.actions[idx]
            self._refresh_tree()
            self._tree.selection_set(str(idx + 1))

    def _save_macro(self):
        if self.selected_idx is None:
            return
        m = self.macros[self.selected_idx]
        m.name = self.name_var.get().strip() or m.name
        m.trigger_key = self.trigger_var.get()
        m.enabled = self.enabled_var.get()
        m.loop = self.loop_var.get()
        try:
            m.loop_count = max(1, int(self.loop_count_var.get()))
        except ValueError:
            m.loop_count = 1
        self._refresh_list()
        self._save_config()
        messagebox.showinfo("Saved", f"✅  Macro «{m.name}» saved.")

    # ═══════════════════════════════════════════
    #  Settings Operations
    # ═══════════════════════════════════════════
    def _on_speed_change(self, *_):
        v = round(float(self.speed_var.get()), 1)
        self._speed_lbl.config(text=f"{v:.1f}×")
        self.engine.speed_multiplier = max(0.01, v)

    def _set_speed(self, val: float):
        self.speed_var.set(val)
        self._on_speed_change()

    def _on_debounce_change(self, *_):
        v = round(float(self.debounce_var.get()), 2)
        self._debounce_lbl.config(text=f"{v:.2f}s")
        self.engine.debounce_delay = v

    def _on_max_concurrent_change(self, *_):
        try:
            self.engine.max_concurrent = max(1, int(self.max_concurrent_var.get()))
        except ValueError:
            pass

    # ═══════════════════════════════════════════
    #  Macro Engine Control
    # ═══════════════════════════════════════════
    def toggle_macros(self):
        if self.is_running:
            self._stop_macros()
        else:
            self._start_macros()

    def _start_macros(self):
        self.is_running = True
        self.engine.resume()

        self._toggle_btn.config(text="  ⏹  STOP MACROS  ",
                                 bg=COLORS["red"],
                                 activebackground=COLORS["red2"])
        self._status_dot.config(fg="#4ade80")
        self._status_lbl.config(text=" RUNNING ", fg="#4ade80")

        def on_press(key):
            if not self.is_running:
                return False
            key_str = self._key_to_str(key)
            for m in self.macros:
                if m.enabled and m.trigger_key == key_str:
                    self.engine.execute(m)
                    break  # one trigger per keypress

        if self.kb_listener and self.kb_listener.is_alive():
            self.kb_listener.stop()

        self.kb_listener = KeyboardListener(on_press=on_press)
        self.kb_listener.daemon = True
        self.kb_listener.start()

    def _stop_macros(self):
        self.is_running = False
        self.engine.stop_all()

        if self.kb_listener:
            self.kb_listener.stop()
            self.kb_listener = None

        # Re-enable engine for next start
        self.engine.active = True

        self._toggle_btn.config(text="  ▶  START MACROS  ",
                                 bg=COLORS["green"],
                                 activebackground=COLORS["green2"])
        self._status_dot.config(fg="#f87171")
        self._status_lbl.config(text=" STOPPED ", fg="#f87171")

    # ═══════════════════════════════════════════
    #  Config Persistence
    # ═══════════════════════════════════════════
    def _save_config(self):
        cfg = {
            "version": APP_VERSION,
            "macros": [m.to_dict() for m in self.macros],
            "settings": {
                "speed": float(self.speed_var.get()),
                "debounce": float(self.debounce_var.get()),
                "max_concurrent": int(self.engine.max_concurrent),
            },
        }
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
        except OSError as exc:
            messagebox.showerror("Save Error", str(exc))

    def _load_config(self):
        if not os.path.exists(CONFIG_FILE):
            return
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            self.macros = [Macro.from_dict(d) for d in cfg.get("macros", [])]
            s = cfg.get("settings", {})
            self.speed_var.set(float(s.get("speed", 1.0)))
            self.debounce_var.set(float(s.get("debounce", 0.3)))
            self.max_concurrent_var.set(str(int(s.get("max_concurrent", 5))))
            self._on_speed_change()
            self._on_debounce_change()
            self._on_max_concurrent_change()
            self._refresh_list()
        except Exception as exc:
            messagebox.showerror("Load Error", f"Failed to load config:\n{exc}")

    # ═══════════════════════════════════════════
    #  Utilities
    # ═══════════════════════════════════════════
    def _on_close(self):
        self._stop_macros()
        if self._record_listener and self._record_listener.is_alive():
            self._record_listener.stop()
        self._save_config()
        self.root.destroy()

    @staticmethod
    def _key_to_str(key) -> str:
        try:
            if hasattr(key, "char") and key.char:
                return key.char
            name = str(key).replace("Key.", "")
            return name
        except Exception:
            return str(key)

    @staticmethod
    def _tkbtn(parent, text, cmd, color) -> tk.Button:
        C = COLORS
        return tk.Button(parent, text=text, command=cmd,
                         bg=color, fg="white",
                         font=("Consolas", 9, "bold"),
                         relief="flat", cursor="hand2",
                         activebackground=color, activeforeground="white",
                         padx=8, pady=5)

    @staticmethod
    def _row(parent) -> tk.Frame:
        f = tk.Frame(parent, bg=COLORS["bg2"])
        f.pack(fill="x", padx=16, pady=5)
        return f

    @staticmethod
    def _lbl(parent, text: str, width: int = 0) -> tk.Label:
        return tk.Label(parent, text=text, bg=COLORS["bg2"], fg=COLORS["text2"],
                         font=("Consolas", 10, "bold"),
                         width=width, anchor="w").pack(side="left") or None

    @staticmethod
    def _settings_section(parent, title: str, subtitle: str = ""):
        C = COLORS
        tk.Label(parent, text=title,
                 bg=C["bg2"], fg=C["glow"],
                 font=("Consolas", 11, "bold")).pack(anchor="w", padx=20, pady=(14, 2))
        if subtitle:
            tk.Label(parent, text=subtitle,
                     bg=C["bg2"], fg=C["text3"],
                     font=("Consolas", 9), wraplength=520,
                     justify="left").pack(anchor="w", padx=20, pady=(0, 6))

    @staticmethod
    def _settings_sep(parent):
        tk.Frame(parent, bg=COLORS["border"], height=1).pack(
            fill="x", padx=20, pady=8)

    def run(self):
        self.root.mainloop()


# ─────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────
if __name__ == "__main__":
    app = MacroApp()
    app.run()
