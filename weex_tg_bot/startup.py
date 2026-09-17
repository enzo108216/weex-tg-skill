from __future__ import annotations

import os
from pathlib import Path
import platform
import shlex
import subprocess
import tempfile


APP_LABEL = "WEEX Telegram Push"
LAUNCH_AGENT_LABEL = "com.weex.tg.skill.scheduler"
SUPPORTED_SYSTEMS = {"Darwin", "Windows", "Linux"}
TARGETS = {"autostart", "desktop"}
COMMAND_MODES = {"scheduler", "gui"}


def _system_name(system_name: str | None) -> str:
    system = system_name or platform.system()
    if system not in SUPPORTED_SYSTEMS:
        raise ValueError(f"unsupported operating system: {system}")
    return system


def _desktop_dir(home: Path, desktop: Path | None) -> Path:
    return Path(desktop).expanduser() if desktop is not None else home / "Desktop"


def launcher_path(
    system_name: str | None,
    target: str,
    home: Path | None = None,
    *,
    desktop: Path | None = None,
    appdata: Path | None = None,
) -> Path:
    system = _system_name(system_name)
    if target not in TARGETS:
        raise ValueError(f"unknown startup target: {target}")
    home_path = Path(home or Path.home()).expanduser()
    if target == "desktop":
        base = _desktop_dir(home_path, desktop)
        if system == "Darwin":
            return base / f"{APP_LABEL}.command"
        if system == "Windows":
            return base / f"{APP_LABEL}.cmd"
        return base / "weex-tg-skill.desktop"
    if system == "Darwin":
        return home_path / "Library" / "LaunchAgents" / f"{LAUNCH_AGENT_LABEL}.plist"
    if system == "Windows":
        roaming = Path(appdata or os.environ.get("APPDATA", home_path / "AppData" / "Roaming")).expanduser()
        return roaming / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "weex-tg-skill-scheduler.vbs"
    return home_path / ".config" / "autostart" / "weex-tg-skill.desktop"


def _command(executable: str, command_mode: str) -> list[str]:
    if command_mode not in COMMAND_MODES:
        raise ValueError(f"unknown launcher command mode: {command_mode}")
    return [executable, "-m", "weex_tg_bot", "gui", "--language", "auto"] if command_mode == "gui" else [executable, "-m", "weex_tg_bot", "run"]


def _xml_escape(value: str) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def _plist(executable: str, working_directory: Path) -> str:
    args = _command(executable, "scheduler")
    arguments = "\n".join(f"        <string>{_xml_escape(item)}</string>" for item in args)
    workdir = _xml_escape(str(working_directory.expanduser().resolve()))
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{LAUNCH_AGENT_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
{arguments}
    </array>
    <key>WorkingDirectory</key>
    <string>{workdir}</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>
</dict>
</plist>
'''


def _shell_quote(value: str) -> str:
    return shlex.quote(str(value))


def _mac_desktop(executable: str, working_directory: Path) -> str:
    command = " ".join(_shell_quote(item) for item in _command(executable, "gui"))
    return f"#!/bin/sh\ncd {_shell_quote(working_directory.expanduser().resolve())}\nexec {command}\n"


def _linux_desktop(executable: str, working_directory: Path, command_mode: str) -> str:
    command = " ".join(_shell_quote(item) for item in _command(executable, command_mode))
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={APP_LABEL}\n"
        f"Exec={command}\n"
        f"Path={working_directory.expanduser().resolve()}\n"
        "Terminal=false\n"
        "X-GNOME-Autostart-enabled=true\n"
    )


def _windows_vbs(executable: str, working_directory: Path) -> str:
    args = " ".join('"' + item.replace('"', '""') + '"' for item in _command(executable, "scheduler")[1:])
    executable_value = str(Path(executable).expanduser()).replace('"', '""')
    workdir = str(working_directory.expanduser().resolve()).replace('"', '""')
    return (
        'Set shell = CreateObject("WScript.Shell")\n'
        f'shell.CurrentDirectory = "{workdir}"\n'
        f'shell.Run """{executable_value}"" {args}", 0, False\n'
    )


def _windows_cmd(executable: str, working_directory: Path, command_mode: str) -> str:
    args = " ".join(subprocess.list2cmdline([item]) for item in _command(executable, command_mode)[1:])
    return (
        "@echo off\n"
        f'cd /d "{working_directory.expanduser().resolve()}"\n'
        f'start "{APP_LABEL}" "{executable}" {args}\n'
    )


def build_launcher(
    *,
    target: str,
    system_name: str | None = None,
    executable: str,
    working_directory: Path,
    command_mode: str,
) -> str:
    system = _system_name(system_name)
    if target not in TARGETS:
        raise ValueError(f"unknown startup target: {target}")
    if target == "autostart" and command_mode != "scheduler":
        raise ValueError("autostart launchers must start the headless scheduler")
    if system == "Darwin":
        return _plist(executable, working_directory) if target == "autostart" else _mac_desktop(executable, working_directory)
    if system == "Windows":
        return _windows_vbs(executable, working_directory) if target == "autostart" else _windows_cmd(executable, working_directory, command_mode)
    return _linux_desktop(executable, working_directory, command_mode)


def install_launcher(
    *,
    target: str,
    system_name: str | None = None,
    home: Path | None = None,
    desktop: Path | None = None,
    appdata: Path | None = None,
    executable: str,
    working_directory: Path,
    command_mode: str,
) -> Path:
    path = launcher_path(system_name, target, home, desktop=desktop, appdata=appdata)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = build_launcher(
        target=target,
        system_name=system_name,
        executable=executable,
        working_directory=working_directory,
        command_mode=command_mode,
    )
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(content)
    try:
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()
    if (system_name or platform.system()) != "Windows":
        path.chmod(0o755)
    return path


def remove_launcher(path: Path) -> bool:
    target = Path(path).expanduser()
    if not target.exists():
        return False
    if not target.is_file() and not target.is_symlink():
        raise ValueError(f"startup target is not a file: {target}")
    target.unlink()
    return True
