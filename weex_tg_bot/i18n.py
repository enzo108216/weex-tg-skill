from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


LOCALE_DIR = Path(__file__).resolve().parent / "locales"
RTL_BASE_LANGUAGES = {"ar", "fa", "he", "ur"}


def normalize_locale(value: str | None) -> str:
    raw = str(value or "en_us").strip().lower().replace("-", "_")
    return raw or "en_us"


def locale_base(value: str | None) -> str:
    return normalize_locale(value).split("_", 1)[0]


def is_rtl(value: str | None) -> bool:
    return locale_base(value) in RTL_BASE_LANGUAGES


def load_locale_catalog(defaults: Mapping[str, Mapping[str, str]] | None = None) -> dict[str, dict[str, str]]:
    catalog = {language: dict(values) for language, values in (defaults or {}).items()}
    if LOCALE_DIR.is_dir():
        for path in sorted(LOCALE_DIR.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(payload, dict) and all(isinstance(key, str) and isinstance(value, str) for key, value in payload.items()):
                catalog.setdefault(normalize_locale(path.stem), {}).update(payload)
    return catalog


def translate(catalog: Mapping[str, Mapping[str, str]], language: str, key: str, **values: Any) -> str:
    exact = normalize_locale(language)
    base = locale_base(exact)
    value = catalog.get(exact, {}).get(key) or catalog.get(base, {}).get(key) or catalog.get("en_us", {}).get(key) or catalog.get("en", {}).get(key) or key
    return value.format(**values) if values else value


def available_locales(catalog: Mapping[str, Mapping[str, str]] | None = None) -> tuple[str, ...]:
    values = catalog or load_locale_catalog()
    return tuple(sorted(values))


def locale_display_name(catalog: Mapping[str, Mapping[str, str]], language: str) -> str:
    """Return the native-language label stored by a locale catalog."""
    normalized = normalize_locale(language)
    value = translate(catalog, normalized, "language_name")
    return value if value != "language_name" else normalized


def locale_options(catalog: Mapping[str, Mapping[str, str]] | None = None) -> tuple[tuple[str, str], ...]:
    """Return selectable (locale code, native display name) pairs.

    Bare language aliases such as ``en`` and ``zh`` are hidden when a regional
    catalog is present, preventing duplicate entries in the GUI while keeping
    those aliases available for fallback and existing configuration values.
    """
    values = catalog or load_locale_catalog()
    locales = set(available_locales(values))
    aliases = {
        language
        for language in locales
        if "_" not in language and any(item.startswith(f"{language}_") for item in locales)
    }
    return tuple(
        (language, locale_display_name(values, language))
        for language in sorted(locales - aliases)
    )
