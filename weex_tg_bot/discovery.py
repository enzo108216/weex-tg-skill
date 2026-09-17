from __future__ import annotations

import os
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Iterable


PARTNER_CLI_NAME = "weex_partner_cli.py"


def _root_from_cli(path: Path) -> Path | None:
    candidate = path.expanduser().resolve()
    if not candidate.is_file() or candidate.name != PARTNER_CLI_NAME:
        return None
    if candidate.parent.name == "scripts" and candidate.parent.parent.name == "weex-partner-skill":
        return candidate.parent.parent
    if candidate.parent.name == "scripts":
        return candidate.parent.parent
    return candidate.parent


def _root_candidates(value: str | Path) -> Iterable[Path]:
    path = Path(value).expanduser()
    cli_root = _root_from_cli(path)
    if cli_root:
        yield cli_root
        return
    if (path / "scripts" / PARTNER_CLI_NAME).is_file():
        yield path
    nested = path / "weex-partner-skill"
    if (nested / "scripts" / PARTNER_CLI_NAME).is_file():
        yield nested
    nested = path / "skills" / "weex-partner-skill"
    if (nested / "scripts" / PARTNER_CLI_NAME).is_file():
        yield nested
    if path.is_dir():
        for child in sorted(path.iterdir()):
            if child.is_dir() and (child / "scripts" / PARTNER_CLI_NAME).is_file():
                yield child


def _current_ai_tool_skill_roots() -> tuple[Path, ...]:
    """Return skill roots exposed by the active AI tool, read-only.

    AI tools do not share one standard directory. Prefer explicit environment
    roots exposed by the host, then inspect the current Codex home and the
    common local skill roots for tools that use the same convention.
    """
    values: list[Path] = []
    for key, value in os.environ.items():
        if value and (key.endswith("_SKILLS_ROOT") or key in {"AI_SKILLS_ROOT", "CURRENT_AI_SKILLS_ROOT"}):
            values.append(Path(value).expanduser())
    codex_home = os.environ.get("CODEX_HOME")
    if codex_home:
        base = Path(codex_home).expanduser()
        values.extend((base / "skills", base / "vendor_imports" / "skills"))
    home = Path.home()
    values.extend(
        (
            home / ".codex" / "skills",
            home / ".codex" / "vendor_imports" / "skills",
            home / ".claude" / "skills",
            home / ".gemini" / "skills",
            home / ".cursor" / "skills",
        )
    )
    return tuple(values)


def discover_skill_roots(
    *,
    search_roots: Iterable[str | Path] | None = None,
    explicit_values: Iterable[str | Path] | None = None,
) -> tuple[str, ...]:
    """Read-only discovery of installed weex-partner-skill roots.

    The function never creates files, imports the discovered skill, or changes
    configuration. Callers must still show the candidates and obtain user
    confirmation before persisting one as the runtime skill root.
    """
    values: list[str | Path] = []
    values.extend(explicit_values or ())
    for key in ("WEEX_PARTNER_CLI", "WEEX_AGENT_SKILLS_ROOT"):
        value = os.environ.get(key)
        if value:
            values.append(value)
    values.extend(_current_ai_tool_skill_roots())
    if search_roots is not None:
        values.extend(search_roots)
    else:
        home = Path.home()
        values.extend(
            (
                home / ".codex" / "skills",
                home / "DoubaoWork" / "skills",
                Path.cwd().parent,
            )
        )

    found: list[str] = []
    seen: set[str] = set()
    for value in values:
        for root in _root_candidates(value):
            resolved = str(root.resolve())
            if resolved not in seen:
                found.append(resolved)
                seen.add(resolved)
    return tuple(found)


def discover_commission_filters(skill_root: str | Path | None = None) -> dict[str, object]:
    """Read the official get-commission filter vocabulary from its catalog."""
    roots = [str(skill_root)] if skill_root else list(discover_skill_roots())
    catalog_paths: list[Path] = []
    for root in roots:
        path = Path(root).expanduser()
        candidates = (
            path / "references" / "partner-field-catalog.json",
            path / "skills" / "weex-partner-skill" / "references" / "partner-field-catalog.json",
        )
        catalog_paths.extend(candidate for candidate in candidates if candidate.is_file())
    for catalog_path in catalog_paths:
        try:
            payload = json.loads(catalog_path.read_text(encoding="utf-8"))
            fields = payload["operations"]["get-commission"]["request_fields"]
            descriptions = " ".join(
                str(field.get("official_description_zh", "")) + " " + str(field.get("official_description_en", ""))
                for field in fields
                if field.get("wire_name") in {"coin", "product_type", "productType"}
                or field.get("internal_name") in {"coin", "product_type"}
            )
            coins = tuple(dict.fromkeys(re.findall(r"(?:USDT|BTC)", descriptions, flags=re.IGNORECASE)))
            products = tuple(dict.fromkeys(re.findall(r"(?:SPOT|FUTURES)", descriptions, flags=re.IGNORECASE)))
            return {"coins": tuple(item.upper() for item in coins), "products": tuple(item.upper() for item in products), "source": str(catalog_path)}
        except (OSError, KeyError, TypeError, json.JSONDecodeError):
            continue
    return {"coins": (), "products": (), "source": None}


def discover_saved_profiles(trader_root: str | Path | None = None) -> tuple[str, ...]:
    """Read saved profile display names through the official Trader skill CLI."""
    roots: list[Path] = []
    if trader_root:
        roots.append(Path(trader_root).expanduser())
    env_root = os.environ.get("WEEX_TRADER_SKILL_ROOT")
    if env_root:
        roots.append(Path(env_root).expanduser())
    home = Path.home()
    roots.extend(
        (
            home / "DoubaoWork" / "skills" / "weex-trader-skill",
            home / ".codex" / "skills" / "weex-trader-skill",
        )
    )
    for root in roots:
        script = root / "scripts" / "weex_profiles.py"
        if not script.is_file():
            continue
        try:
            completed = subprocess.run(
                [sys.executable, str(script), "list", "--pretty"],
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
            payload = json.loads(completed.stdout)
            profiles = payload.get("profiles") if isinstance(payload, dict) else None
            if completed.returncode == 0 and isinstance(profiles, list):
                return tuple(
                    str(item["name"])
                    for item in profiles
                    if isinstance(item, dict) and str(item.get("name") or "").strip()
                )
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError, TypeError, KeyError):
            continue
    return ()
