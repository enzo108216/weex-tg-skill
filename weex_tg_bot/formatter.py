from __future__ import annotations

from decimal import Decimal
import re
from typing import Any, Mapping, Sequence

from .models import RebateSummary
from .i18n import load_locale_catalog, locale_base, translate


_CATALOG = load_locale_catalog()


_PERIOD_KEYS = {"1d": "window_1d", "1w": "window_1w", "1m": "window_1m", "1y": "window_1y"}


def _schedule_descriptor(language: str, schedule_key: str) -> str:
    """Turn the internal scheduler key into readable message text."""
    match = re.fullmatch(r"(.+):(\d{2}:\d{2})=([^@]+)@(.+)", str(schedule_key))
    if not match:
        return str(schedule_key)
    timezone_name, schedule_time, period, start_date = match.groups()
    if period in _PERIOD_KEYS:
        period_text = translate(_CATALOG, language, _PERIOD_KEYS[period])
    elif period.endswith("d") and period[:-1].isdigit():
        period_text = translate(_CATALOG, language, "custom_window").replace("N", period[:-1])
    else:
        period_text = period
    descriptor = f"{timezone_name} {schedule_time} · {period_text}"
    if start_date and start_date != "-":
        descriptor += f" · {translate(_CATALOG, language, 'start_date_utc')} {start_date}"
    return descriptor


def localized_trigger(language: str, kind: str, schedule_key: str = "") -> str:
    """Return a localized trigger label used in the Telegram message."""
    if kind == "manual":
        return translate(_CATALOG, language, "trigger_manual")
    if schedule_key:
        return translate(
            _CATALOG,
            language,
            "trigger_scheduled_with_key",
            schedule=_schedule_descriptor(language, schedule_key),
        )
    return translate(_CATALOG, language, "trigger_scheduled")


def _money(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.00000001")), "f").rstrip("0").rstrip(".") or "0"


def _scope_text(scope: Mapping[str, Any] | None, language: str) -> str:
    value = dict(scope or {})
    if value.get("mode") == "all":
        return translate(_CATALOG, language, "scope_all_confirmed" if value.get("all_confirmed") is True else "scope_all_unconfirmed")
    if value.get("mode") == "uids":
        uids = value.get("uids") or ()
        normalized = sorted({str(item) for item in uids}, key=lambda item: int(item) if item.isdigit() else item)
        separator = "、" if locale_base(language) in {"zh", "ja"} else ", "
        return translate(_CATALOG, language, "scope_uids", uids=separator.join(normalized)) if normalized else translate(_CATALOG, language, "scope_unknown")
    return translate(_CATALOG, language, "scope_unknown")


def _time_text(value: str) -> str:
    return str(value).replace("T", " ").removesuffix("Z")


def format_summary(
    summary: RebateSummary,
    *,
    trigger: str = "",
    profile: str = "",
    scope: Mapping[str, Any] | None = None,
    product_types: Sequence[str] = (),
    bot_name: str = "",
    target_label: str = "",
    language: str = "zh",
) -> str:
    if summary.utc_start and summary.utc_end:
        range_to = translate(_CATALOG, language, "range_to")
        query_window = f"{_time_text(summary.utc_start)}{range_to}{_time_text(summary.utc_end)}"
    else:
        range_to = translate(_CATALOG, language, "range_to")
        query_window = f"{summary.utc_date} 00:00:00{range_to}{summary.utc_date} 23:59:59.999"
    separator = "、" if locale_base(language) == "zh" else ", "
    products = separator.join(str(value).upper() for value in product_types) or translate(_CATALOG, language, "scope_unknown")
    target = f"{bot_name} / {target_label}" if bot_name and target_label else bot_name or target_label
    label_sep = "：" if locale_base(language) == "zh" else ": "
    lines = [
        translate(_CATALOG, language, "message_title"),
        "",
        translate(_CATALOG, language, "query_info"),
        f"{translate(_CATALOG, language, 'trigger')}{label_sep}{trigger or translate(_CATALOG, language, 'scope_unknown')}",
        f"{translate(_CATALOG, language, 'profile_label')}{label_sep}{profile or translate(_CATALOG, language, 'scope_unknown')}",
        f"{translate(_CATALOG, language, 'scope_label')}{label_sep}{_scope_text(scope, language)}",
        f"{translate(_CATALOG, language, 'time_range_label')}{label_sep}{query_window}",
        f"{translate(_CATALOG, language, 'products_label')}{label_sep}{products}",
        f"{translate(_CATALOG, language, 'coin_label')}{label_sep}{summary.coin}",
    ]
    if target:
        lines.append(f"{translate(_CATALOG, language, 'target_label')}{label_sep}{target}")
    lines.extend(
        [
            "",
            translate(_CATALOG, language, "metrics"),
            f"{translate(_CATALOG, language, 'trading_volume')}{label_sep}{_money(summary.trading_volume)} {summary.coin}",
            f"{translate(_CATALOG, language, 'fee')}{label_sep}{_money(summary.fee)} {summary.coin}",
            f"{translate(_CATALOG, language, 'commission')}{label_sep}{_money(summary.commission)} {summary.coin}",
            f"{translate(_CATALOG, language, 'sub_affiliate_commission')}{label_sep}{_money(summary.sub_affiliate_commission)} {summary.coin}",
            f"{translate(_CATALOG, language, 'final_income')}{label_sep}{_money(summary.final_income)} {summary.coin}",
            "",
            translate(_CATALOG, language, "formula_subaffiliate" if summary.formula == "commission_minus_subaffiliate_commission" else "formula_commission"),
            translate(_CATALOG, language, "data_complete"),
        ]
    )
    return "\n".join(lines)
