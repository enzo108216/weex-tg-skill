from __future__ import annotations

import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import textwrap
import venv
from typing import Any


RUNTIME_ACTIVE_ENV = "WEEX_TG_GUI_RUNTIME_ACTIVE"
RUNTIME_HOME_ENV = "WEEX_TG_GUI_RUNTIME_HOME"


def runtime_root() -> Path:
    override = os.environ.get(RUNTIME_HOME_ENV)
    if override:
        return Path(override).expanduser()
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home()))
    elif platform.system() == "Darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "weex-tg-skill" / "gui-runtime"


def managed_venv_dir(root: Path | None = None) -> Path:
    return Path(root or runtime_root()) / "venv"


def managed_python_path(root: Path | None = None, *, system_name: str | None = None) -> Path:
    system = system_name or platform.system()
    if system == "Windows":
        return managed_venv_dir(root) / "Scripts" / "python.exe"
    return managed_venv_dir(root) / "bin" / "python"


def managed_runtime_setup_command(system_name: str | None = None) -> str:
    launcher = "py -3" if (system_name or platform.system()) == "Windows" else "python3"
    return f"{launcher} -m weex_tg_bot gui-install --accept-managed-runtime"


def _probe_script() -> str:
    return textwrap.dedent(
        """
        import importlib
        import json
        import sys
        payload = {"python": sys.executable}
        try:
            import tkinter as tk
            root = tk.Tk()
            root.withdraw()
            root.update_idletasks()
            root.destroy()
            payload["tkinter"] = True
        except Exception as exc:
            payload["tkinter"] = False
            payload["tkinter_error"] = f"{type(exc).__name__}: {exc}"
        # Token storage is SQLite-backed; an OS keyring is not required.
        payload["keyring"] = False
        try:
            importlib.import_module("weex_tg_bot")
            payload["package"] = True
        except Exception as exc:
            payload["package"] = False
            payload["package_error"] = f"{type(exc).__name__}: {exc}"
        payload["ready"] = bool(payload.get("tkinter") and payload.get("package"))
        print(json.dumps(payload, ensure_ascii=False))
        raise SystemExit(0 if payload["ready"] else 2)
        """
    )


def _probe_python(python: Path) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            [str(python), "-c", _probe_script()],
            text=True,
            capture_output=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ready": False, "error": f"{type(exc).__name__}: {exc}"}
    payload: dict[str, Any] = {}
    for line in reversed(completed.stdout.splitlines()):
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            payload = value
            break
    payload.setdefault("ready", False)
    payload["returncode"] = completed.returncode
    if completed.stderr.strip():
        payload["stderr"] = completed.stderr.strip()[-2000:]
    return payload


def build_runtime_preflight(root: Path | None = None) -> dict[str, Any]:
    runtime = Path(root or runtime_root()).expanduser()
    python = managed_python_path(runtime)
    if not python.is_file():
        return {
            "os": platform.system(),
            "runtime_root": str(runtime),
            "venv": str(managed_venv_dir(runtime)),
            "python": str(python),
            "ready": False,
            "requires_install": True,
            "reason": "managed_runtime_missing",
            "setup_command": managed_runtime_setup_command(),
            "probe": None,
        }
    probe = _probe_python(python)
    ready = probe.get("ready") is True
    return {
        "os": platform.system(),
        "runtime_root": str(runtime),
        "venv": str(managed_venv_dir(runtime)),
        "python": str(python),
        "ready": ready,
        "requires_install": not ready,
        "reason": "ok" if ready else "managed_runtime_unusable",
        "setup_command": managed_runtime_setup_command(),
        "probe": probe,
    }


def ensure_managed_runtime(*, accept_managed_runtime: bool, root: Path | None = None) -> dict[str, Any]:
    before = build_runtime_preflight(root)
    if before["ready"]:
        before["action"] = "reused"
        return before
    if not accept_managed_runtime:
        before["requires_user_consent"] = True
        return before
    runtime = Path(root or runtime_root()).expanduser()
    runtime.mkdir(parents=True, exist_ok=True)
    try:
        venv.EnvBuilder(with_pip=True, clear=False).create(managed_venv_dir(runtime))
        python = managed_python_path(runtime)
        project_root = Path(__file__).resolve().parents[1]
        commands = [
            [str(python), "-m", "pip", "install", "-r", str(project_root / "gui-requirements.txt")],
            [str(python), "-m", "pip", "install", "-e", str(project_root)],
        ]
        for command in commands:
            completed = subprocess.run(command, text=True, capture_output=True, check=False, timeout=600)
            if completed.returncode != 0:
                detail = (completed.stderr or completed.stdout or "").strip()[-4000:]
                raise RuntimeError(f"GUI runtime dependency install failed: {detail}")
    except Exception as exc:
        return {
            **before,
            "ready": False,
            "requires_install": True,
            "reason": "install_failed",
            "error": str(exc),
        }
    after = build_runtime_preflight(runtime)
    after["action"] = "created"
    return after


def reexec_under_managed_runtime(argv: list[str] | None = None) -> None:
    if os.environ.get(RUNTIME_ACTIVE_ENV) == "1":
        return
    report = build_runtime_preflight()
    if not report["ready"]:
        raise RuntimeError(
            "Managed GUI runtime is not ready. Run "
            f"{report['setup_command']} after reviewing gui-preflight."
        )
    python = Path(report["python"])
    env = os.environ.copy()
    env[RUNTIME_ACTIVE_ENV] = "1"
    args = [str(python), "-m", "weex_tg_bot", "gui", *(argv or [])]
    os.execve(str(python), args, env)
