"""
PUBG Mouse Helper - Recoil Compensation Tool
Moves the mouse down while the fire button is held to reduce recoil.
Settings are saved to a JSON file and restored on startup.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import json
import os
import sys
import threading
import time
import ctypes
from ctypes import wintypes

# ─── Win32 API Constants & Functions ────────────────────────────────────────
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

INPUT_MOUSE = 0
MOUSEEVENTF_MOVE = 0x0001

VK_LBUTTON = 0x01  # Left mouse button
VK_RBUTTON = 0x02  # Right mouse button
VK_MBUTTON = 0x04  # Middle mouse button
VK_XBUTTON1 = 0x05
VK_XBUTTON2 = 0x06
VK_SHIFT = 0x10
VK_CONTROL = 0x11

# ─── Mouse Input Structures ────────────────────────────────────────────────
class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]

class INPUT(ctypes.Structure):
    class _INPUT(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT)]
    _fields_ = [
        ("type", ctypes.c_ulong),
        ("_input", _INPUT),
    ]

def move_mouse(dx, dy):
    """Move the mouse relative to current position using SendInput."""
    extra = ctypes.c_ulong(0)
    inp = INPUT()
    inp.type = INPUT_MOUSE
    inp._input.mi = MOUSEINPUT(dx, dy, 0, MOUSEEVENTF_MOVE, 0, ctypes.pointer(extra))
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))

def is_key_pressed(vk_code):
    """Check if a virtual key is currently pressed."""
    return user32.GetAsyncKeyState(vk_code) & 0x8000 != 0

# ─── Key Name Mapping ──────────────────────────────────────────────────────
KEY_MAP = {
    "Left Mouse Button": VK_LBUTTON,
    "Right Mouse Button": VK_RBUTTON,
    "Middle Mouse Button": VK_MBUTTON,
    "Mouse X1": VK_XBUTTON1,
    "Mouse X2": VK_XBUTTON2,
    "Shift": VK_SHIFT,
    "Ctrl": VK_CONTROL,
}

# Add letter keys
for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
    KEY_MAP[c] = ord(c)

# Add F keys
for i in range(1, 13):
    KEY_MAP[f"F{i}"] = 0x70 + (i - 1)

# ─── Settings ──────────────────────────────────────────────────────────────
SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")

DEFAULT_SETTINGS = {
    "pull_strength": 3,       # How many pixels to move down per tick (dy)
    "pull_interval": 10,      # Milliseconds between each pull
    "fire_key": "Left Mouse Button",
    "toggle_key": "F6",
    "active": False,
}

def load_settings():
    """Load settings from file, falling back to defaults."""
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r") as f:
                saved = json.load(f)
            # Merge with defaults to handle missing keys
            settings = DEFAULT_SETTINGS.copy()
            settings.update(saved)
            return settings
    except Exception:
        pass
    return DEFAULT_SETTINGS.copy()

def save_settings(settings):
    """Save settings to file."""
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(settings, f, indent=2)
    except Exception as e:
        print(f"Error saving settings: {e}")


# ─── Main Application ─────────────────────────────────────────────────────
class PUBGMouseHelper:
    def __init__(self, root):
        self.root = root
        self.settings = load_settings()
        self.running = True
        self.active = self.settings.get("active", False)

        # ── Window Setup ───────────────────────────────────────────────
        self.root.title("PUBG Mouse Helper")
        self.root.geometry("420x520")
        self.root.resizable(False, False)
        self.root.configure(bg="#1a1a2e")

        # Try to set DPI awareness for crisp rendering
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

        self._build_ui()
        self._start_recoil_thread()
        self._start_toggle_listener()

        # Save on close
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        """Build the entire GUI."""
        style = ttk.Style()
        style.theme_use("clam")

        # ── Title Banner ───────────────────────────────────────────────
        title_frame = tk.Frame(self.root, bg="#16213e", pady=12)
        title_frame.pack(fill="x")

        tk.Label(
            title_frame,
            text="🎯 PUBG Mouse Helper",
            font=("Segoe UI", 18, "bold"),
            fg="#e94560",
            bg="#16213e",
        ).pack()

        tk.Label(
            title_frame,
            text="Recoil Compensation Tool",
            font=("Segoe UI", 9),
            fg="#8899aa",
            bg="#16213e",
        ).pack()

        # ── Activate / Deactivate Button ───────────────────────────────
        btn_frame = tk.Frame(self.root, bg="#1a1a2e", pady=10)
        btn_frame.pack(fill="x")

        self.toggle_btn = tk.Button(
            btn_frame,
            text="ACTIVATE" if not self.active else "DEACTIVATE",
            font=("Segoe UI", 14, "bold"),
            fg="white",
            bg="#e94560" if not self.active else "#28a745",
            activebackground="#c0392b" if not self.active else "#218838",
            activeforeground="white",
            relief="flat",
            cursor="hand2",
            width=20,
            height=1,
            command=self._toggle_active,
        )
        self.toggle_btn.pack()

        # Status label
        self.status_label = tk.Label(
            btn_frame,
            text="● INACTIVE" if not self.active else "● ACTIVE",
            font=("Segoe UI", 10, "bold"),
            fg="#e94560" if not self.active else "#28a745",
            bg="#1a1a2e",
        )
        self.status_label.pack(pady=(5, 0))

        # ── Settings Frame ─────────────────────────────────────────────
        settings_frame = tk.LabelFrame(
            self.root,
            text="  ⚙  Settings  ",
            font=("Segoe UI", 11, "bold"),
            fg="#e94560",
            bg="#1a1a2e",
            bd=1,
            relief="groove",
            padx=15,
            pady=10,
        )
        settings_frame.pack(fill="x", padx=20, pady=(10, 5))

        # Pull Strength (dy)
        tk.Label(
            settings_frame,
            text="Pull Strength (dy):",
            font=("Segoe UI", 10),
            fg="white",
            bg="#1a1a2e",
            anchor="w",
        ).grid(row=0, column=0, sticky="w", pady=5)

        self.strength_var = tk.IntVar(value=self.settings["pull_strength"])
        self.strength_scale = tk.Scale(
            settings_frame,
            from_=1, to=20,
            orient="horizontal",
            variable=self.strength_var,
            bg="#1a1a2e",
            fg="white",
            highlightbackground="#1a1a2e",
            troughcolor="#16213e",
            activebackground="#e94560",
            length=200,
            command=lambda v: self._on_setting_change(),
        )
        self.strength_scale.grid(row=0, column=1, sticky="ew", pady=5)

        self.strength_val_label = tk.Label(
            settings_frame,
            text=str(self.settings["pull_strength"]),
            font=("Segoe UI", 10, "bold"),
            fg="#e94560",
            bg="#1a1a2e",
            width=3,
        )
        self.strength_val_label.grid(row=0, column=2, padx=(5, 0))

        # Pull Interval (ms)
        tk.Label(
            settings_frame,
            text="Pull Interval (ms):",
            font=("Segoe UI", 10),
            fg="white",
            bg="#1a1a2e",
            anchor="w",
        ).grid(row=1, column=0, sticky="w", pady=5)

        self.interval_var = tk.IntVar(value=self.settings["pull_interval"])
        self.interval_scale = tk.Scale(
            settings_frame,
            from_=1, to=50,
            orient="horizontal",
            variable=self.interval_var,
            bg="#1a1a2e",
            fg="white",
            highlightbackground="#1a1a2e",
            troughcolor="#16213e",
            activebackground="#e94560",
            length=200,
            command=lambda v: self._on_setting_change(),
        )
        self.interval_scale.grid(row=1, column=1, sticky="ew", pady=5)

        self.interval_val_label = tk.Label(
            settings_frame,
            text=str(self.settings["pull_interval"]),
            font=("Segoe UI", 10, "bold"),
            fg="#e94560",
            bg="#1a1a2e",
            width=3,
        )
        self.interval_val_label.grid(row=1, column=2, padx=(5, 0))

        settings_frame.columnconfigure(1, weight=1)

        # ── Key Bindings Frame ─────────────────────────────────────────
        keys_frame = tk.LabelFrame(
            self.root,
            text="  🎮  Key Bindings  ",
            font=("Segoe UI", 11, "bold"),
            fg="#e94560",
            bg="#1a1a2e",
            bd=1,
            relief="groove",
            padx=15,
            pady=10,
        )
        keys_frame.pack(fill="x", padx=20, pady=(10, 5))

        # Fire Key
        tk.Label(
            keys_frame,
            text="Fire Key:",
            font=("Segoe UI", 10),
            fg="white",
            bg="#1a1a2e",
            anchor="w",
        ).grid(row=0, column=0, sticky="w", pady=5)

        self.fire_key_var = tk.StringVar(value=self.settings["fire_key"])
        fire_key_combo = ttk.Combobox(
            keys_frame,
            textvariable=self.fire_key_var,
            values=list(KEY_MAP.keys()),
            state="readonly",
            width=22,
            font=("Segoe UI", 9),
        )
        fire_key_combo.grid(row=0, column=1, sticky="ew", pady=5, padx=(10, 0))
        fire_key_combo.bind("<<ComboboxSelected>>", lambda e: self._on_setting_change())

        # Toggle Key
        tk.Label(
            keys_frame,
            text="Toggle Key:",
            font=("Segoe UI", 10),
            fg="white",
            bg="#1a1a2e",
            anchor="w",
        ).grid(row=1, column=0, sticky="w", pady=5)

        self.toggle_key_var = tk.StringVar(value=self.settings["toggle_key"])
        toggle_key_combo = ttk.Combobox(
            keys_frame,
            textvariable=self.toggle_key_var,
            values=list(KEY_MAP.keys()),
            state="readonly",
            width=22,
            font=("Segoe UI", 9),
        )
        toggle_key_combo.grid(row=1, column=1, sticky="ew", pady=5, padx=(10, 0))
        toggle_key_combo.bind("<<ComboboxSelected>>", lambda e: self._on_setting_change())

        keys_frame.columnconfigure(1, weight=1)

        # ── Info Bar ───────────────────────────────────────────────────
        info_frame = tk.Frame(self.root, bg="#0f3460", pady=8)
        info_frame.pack(fill="x", side="bottom")

        self.info_label = tk.Label(
            info_frame,
            text=f"Toggle: {self.settings['toggle_key']}  |  Fire: {self.settings['fire_key']}",
            font=("Segoe UI", 9),
            fg="#a8b8c8",
            bg="#0f3460",
        )
        self.info_label.pack()

    def _on_setting_change(self):
        """Called whenever a setting is changed by the user."""
        self.settings["pull_strength"] = self.strength_var.get()
        self.settings["pull_interval"] = self.interval_var.get()
        self.settings["fire_key"] = self.fire_key_var.get()
        self.settings["toggle_key"] = self.toggle_key_var.get()

        # Update value labels
        self.strength_val_label.config(text=str(self.settings["pull_strength"]))
        self.interval_val_label.config(text=str(self.settings["pull_interval"]))

        # Update info bar
        self.info_label.config(
            text=f"Toggle: {self.settings['toggle_key']}  |  Fire: {self.settings['fire_key']}"
        )

        save_settings(self.settings)

    def _toggle_active(self):
        """Toggle the active state."""
        self.active = not self.active
        self._update_active_ui()
        self.settings["active"] = self.active
        save_settings(self.settings)

    def _update_active_ui(self):
        """Update UI elements to reflect the current active state."""
        if self.active:
            self.toggle_btn.config(
                text="DEACTIVATE",
                bg="#28a745",
                activebackground="#218838",
            )
            self.status_label.config(text="● ACTIVE", fg="#28a745")
        else:
            self.toggle_btn.config(
                text="ACTIVATE",
                bg="#e94560",
                activebackground="#c0392b",
            )
            self.status_label.config(text="● INACTIVE", fg="#e94560")

    def _start_recoil_thread(self):
        """Start the background thread that handles recoil compensation."""
        def recoil_loop():
            while self.running:
                if self.active:
                    fire_key_name = self.settings.get("fire_key", "Left Mouse Button")
                    vk = KEY_MAP.get(fire_key_name, VK_LBUTTON)

                    if is_key_pressed(vk):
                        dy = self.settings["pull_strength"]
                        move_mouse(0, dy)

                interval_ms = self.settings.get("pull_interval", 10)
                time.sleep(interval_ms / 1000.0)

        t = threading.Thread(target=recoil_loop, daemon=True)
        t.start()

    def _start_toggle_listener(self):
        """Poll for the toggle key press to activate/deactivate."""
        toggle_key_name = self.settings.get("toggle_key", "F6")
        vk = KEY_MAP.get(toggle_key_name, 0x75)  # F6 default

        def check_toggle():
            if not self.running:
                return
            # Re-read current toggle key in case user changed it
            current_toggle = self.settings.get("toggle_key", "F6")
            current_vk = KEY_MAP.get(current_toggle, 0x75)

            if is_key_pressed(current_vk):
                self._toggle_active()
                # Debounce — wait until key is released
                while is_key_pressed(current_vk) and self.running:
                    time.sleep(0.05)

            self.root.after(100, check_toggle)

        self.root.after(100, check_toggle)

    def _on_close(self):
        """Handle window close."""
        self.running = False
        self.settings["active"] = self.active
        save_settings(self.settings)
        self.root.destroy()


# ─── Entry Point ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    root = tk.Tk()
    app = PUBGMouseHelper(root)
    root.mainloop()
