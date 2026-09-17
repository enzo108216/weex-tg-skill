from __future__ import annotations

import importlib
import os
import platform
from typing import Any

from .discovery import discover_skill_roots
from .runtime import build_runtime_preflight


def _probe_tkinter() -> bool:
    try:
        tkinter = importlib.import_module("tkinter")
        root = tkinter.Tk()
        root.withdraw()
        root.update_idletasks()
        root.destroy()
        return True
    except Exception:
        return False


def _probe_desktop(system_name: str) -> bool:
    if os.environ.get("WEEX_TG_HEADLESS") == "1" or os.environ.get("CI") == "1":
        return False
    if system_name == "Linux":
        return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
    # Windows and macOS desktop sessions do not require DISPLAY/WAYLAND_DISPLAY.
    return system_name in {"Windows", "Darwin"}


def _probe_keyring() -> bool:
    try:
        keyring = importlib.import_module("keyring")
        backend = keyring.get_keyring()
        return backend.__class__.__module__ != "keyring.backends.fail"
    except Exception:
        return False


def build_report(
    *,
    system_name: str | None = None,
    tkinter_importable: bool | None = None,
    desktop_available: bool | None = None,
    keyring_available: bool | None = None,
    managed_runtime_ready: bool | None = None,
) -> dict[str, Any]:
    system = system_name or platform.system()
    tk_ready = _probe_tkinter() if tkinter_importable is None else bool(tkinter_importable)
    desktop_ready = _probe_desktop(system) if desktop_available is None else bool(desktop_available)
    # Tokens are stored in SQLite; OS keyring availability does not gate GUI readiness.
    keyring_ready = False
    if managed_runtime_ready is None:
        managed = build_runtime_preflight()
        managed_ready = bool(managed.get("ready"))
    else:
        managed = None
        managed_ready = bool(managed_runtime_ready)
    reasons: list[str] = []
    if system not in {"Windows", "Darwin", "Linux"}:
        reasons.append(f"unsupported operating system: {system}")
    if not tk_ready:
        reasons.append("Tkinter is unavailable")
    if not desktop_ready:
        reasons.append("no interactive desktop session is available")
    if not managed_ready:
        reasons.append("managed GUI virtual environment is not ready")
    gui_capable = system in {"Windows", "Darwin", "Linux"} and tk_ready and desktop_ready
    gui_ready = gui_capable and managed_ready
    if gui_ready:
        recommendation = "gui"
    elif gui_capable:
        recommendation = "gui-install"
    else:
        recommendation = "command"
    return {
        "os": system,
        "tkinter_importable": tk_ready,
        "desktop_available": desktop_ready,
        "keyring_available": keyring_ready,
        "token_storage": "sqlite",
        "managed_runtime_ready": managed_ready,
        "managed_runtime": managed,
        "gui_capable": gui_capable,
        "gui_ready": gui_ready,
        "recommendation": recommendation,
        "reasons": reasons,
        "skill_root_candidates": list(discover_skill_roots()),
        "gui_command": "python -m weex_tg_bot gui --language auto",
        "command_hint": "python -m weex_tg_bot config show",
    }
