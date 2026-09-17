from __future__ import annotations

from dataclasses import dataclass, field, replace
from decimal import Decimal
import re
from typing import Any, Mapping
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from .i18n import normalize_locale


class ConfigValidationError(ValueError):
    """Raised when persisted or user-provided configuration is unsafe."""


_CHAT_ID = re.compile(r"^-?\d+$")
_USERNAME = re.compile(r"^@[A-Za-z0-9_]{5,32}$")
_FORMULAS = {"commission_minus_subaffiliate_commission", "commission"}
_SCHEDULE_PERIODS = {"1d", "1w", "1m", "1y"}


def validate_chat_id(value: str) -> str:
    text = str(value or "").strip()
    if not (_CHAT_ID.fullmatch(text) or _USERNAME.fullmatch(text)):
        raise ConfigValidationError("chat_id must be a Telegram numeric ID or @username")
    return text


def validate_token(value: str) -> str:
    text = str(value or "")
    if not text or text.strip() != text or any(char.isspace() for char in text):
        raise ConfigValidationError("Telegram bot token must be a non-empty single-line value")
    return text


def validate_bot_name(value: str) -> str:
    text = str(value or "").strip()
    if not text or len(text) > 64 or any(ord(char) < 32 or ord(char) == 127 for char in text):
        raise ConfigValidationError(
            "bot name must be 1-64 characters and cannot contain control characters")
    return text


@dataclass(frozen=True)
class QueryConfig:
    coin: str = "USDT"
    product_types: tuple[str, ...] = ("SPOT", "FUTURES")
    scope: Mapping[str, Any] = field(
        default_factory=lambda: {"mode": "all", "all_confirmed": False}
    )
    formula: str = "commission_minus_subaffiliate_commission"

    def __post_init__(self) -> None:
        coin = str(self.coin or "").upper()
        if not coin or any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in coin):
            raise ConfigValidationError("coin must be a non-empty single-line value")
        products = tuple(str(value).upper() for value in self.product_types)
        if not products or any(not value or any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in value) for value in products):
            raise ConfigValidationError("product_types must contain non-empty single-line values")
        if len(set(products)) != len(products):
            raise ConfigValidationError("product_types must not contain duplicates")
        scope = dict(self.scope)
        mode = scope.get("mode")
        if mode == "all":
            scope = {"mode": "all", "all_confirmed": scope.get("all_confirmed") is True}
        elif mode == "uids":
            raw_uids = scope.get("uids")
            if not isinstance(raw_uids, (list, tuple)) or not raw_uids:
                raise ConfigValidationError("uids scope requires at least one UID")
            uids: list[int] = []
            for raw in raw_uids:
                try:
                    uid = int(str(raw))
                except (TypeError, ValueError) as exc:
                    raise ConfigValidationError("UIDs must be positive integers") from exc
                if uid <= 0 or uid >= 2**63:
                    raise ConfigValidationError("UIDs must be positive signed 64-bit integers")
                uids.append(uid)
            scope = {"mode": "uids", "uids": sorted(set(uids))}
        else:
            raise ConfigValidationError("scope.mode must be all or uids")
        formula = str(self.formula or "")
        if formula not in _FORMULAS:
            raise ConfigValidationError("unsupported final income formula")
        object.__setattr__(self, "coin", coin)
        object.__setattr__(self, "product_types", products)
        object.__setattr__(self, "scope", scope)
        object.__setattr__(self, "formula", formula)

    def to_dict(self) -> dict[str, Any]:
        return {
            "coin": self.coin,
            "product_types": list(self.product_types),
            "scope": dict(self.scope),
            "formula": self.formula,
        }


@dataclass(frozen=True)
class ScheduleConfig:
    schedule_time: str
    period: str
    enabled: bool = True
    start_date: str = ""
    timezone: str = "UTC"

    def __post_init__(self) -> None:
        schedule = str(self.schedule_time or "").strip()
        if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", schedule):
            raise ConfigValidationError("schedule_time must be HH:MM")
        period = str(self.period or "").strip().lower()
        if period not in _SCHEDULE_PERIODS and not re.fullmatch(r"[1-9]\d*d", period):
            raise ConfigValidationError("schedule period must be 1d, 1w, 1m, 1y, or Nd")
        start_date = str(self.start_date or "").strip()
        timezone_name = str(self.timezone or "UTC").strip()
        try:
            ZoneInfo(timezone_name)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ConfigValidationError("timezone must be a valid IANA timezone") from exc
        if period not in _SCHEDULE_PERIODS and re.fullmatch(r"[1-9]\d*d", period):
            if not start_date:
                raise ConfigValidationError("custom Nd schedule requires start_date")
            try:
                from datetime import date
                date.fromisoformat(start_date)
            except ValueError as exc:
                raise ConfigValidationError("start_date must use YYYY-MM-DD") from exc
        elif start_date:
            raise ConfigValidationError("start_date is only valid for custom Nd schedules")
        object.__setattr__(self, "schedule_time", schedule)
        object.__setattr__(self, "period", period)
        object.__setattr__(self, "start_date", start_date)
        object.__setattr__(self, "timezone", timezone_name)
        object.__setattr__(self, "enabled", bool(self.enabled))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schedule_time": self.schedule_time,
            "period": self.period,
            "start_date": self.start_date,
            "timezone": self.timezone,
            "enabled": self.enabled,
        }


@dataclass(frozen=True)
class GroupConfig:
    chat_id: str
    label: str = ""
    profile: str = ""
    query: QueryConfig = field(default_factory=QueryConfig)
    schedules: tuple[ScheduleConfig, ...] = ()
    language: str = "zh"

    def __post_init__(self) -> None:
        object.__setattr__(self, "chat_id", validate_chat_id(self.chat_id))
        object.__setattr__(self, "label", str(self.label or "").strip())
        object.__setattr__(self, "profile", str(self.profile or "").strip())
        language = normalize_locale(self.language or "zh_cn")
        if not re.fullmatch(r"[a-z]{2,3}(?:_[a-z0-9]{2,8})?", language):
            raise ConfigValidationError("language must be a valid locale code")
        object.__setattr__(self, "language", language)
        if not isinstance(self.query, QueryConfig):
            object.__setattr__(self, "query", QueryConfig(**dict(self.query)))
        schedules: list[ScheduleConfig] = []
        seen_schedules: set[tuple[str, str]] = set()
        for item in self.schedules:
            schedule = item if isinstance(item, ScheduleConfig) else ScheduleConfig(**dict(item))
            key = (schedule.schedule_time, schedule.period)
            if key not in seen_schedules:
                schedules.append(schedule)
                seen_schedules.add(key)
        object.__setattr__(self, "schedules", tuple(schedules))

    def to_dict(self) -> dict[str, Any]:
        return {
            "chat_id": self.chat_id,
            # `label` is the persisted/backward-compatible field; expose the
            # user-facing name explicitly for config/skill consumers.
            "group_name": self.label,
            "label": self.label,
            "profile": self.profile,
            "query": self.query.to_dict(),
            "schedules": [schedule.to_dict() for schedule in self.schedules],
            "language": self.language,
        }


@dataclass(frozen=True)
class PushTaskConfig:
    task_id: str
    name: str
    bot_name: str
    chat_id: str
    profile: str
    query: QueryConfig = field(default_factory=QueryConfig)
    schedules: tuple[ScheduleConfig, ...] = ()
    language: str = "zh"

    def __post_init__(self) -> None:
        task_id = str(self.task_id or "").strip()
        name = str(self.name or "").strip()
        if not task_id or len(task_id) > 128 or any(ord(char) < 32 or ord(char) == 127 for char in task_id):
            raise ConfigValidationError("task_id must be a non-empty safe value")
        if not name:
            raise ConfigValidationError("push task name is required")
        object.__setattr__(self, "task_id", task_id)
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "bot_name", validate_bot_name(self.bot_name))
        object.__setattr__(self, "chat_id", validate_chat_id(self.chat_id))
        object.__setattr__(self, "profile", str(self.profile or "").strip())
        language = normalize_locale(self.language or "zh")
        if not re.fullmatch(r"[a-z]{2,3}(?:_[a-z0-9]{2,8})?", language):
            raise ConfigValidationError("language must be a valid locale code")
        object.__setattr__(self, "language", language)
        if not isinstance(self.query, QueryConfig):
            object.__setattr__(self, "query", QueryConfig(**dict(self.query)))
        schedules: list[ScheduleConfig] = []
        seen: set[tuple[str, str]] = set()
        for item in self.schedules:
            schedule = item if isinstance(item, ScheduleConfig) else ScheduleConfig(**dict(item))
            key = (schedule.schedule_time, schedule.period)
            if key not in seen:
                schedules.append(schedule)
                seen.add(key)
        object.__setattr__(self, "schedules", tuple(schedules))

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "name": self.name,
            "bot_name": self.bot_name,
            "chat_id": self.chat_id,
            "profile": self.profile,
            "query": self.query.to_dict(),
            "schedules": [schedule.to_dict() for schedule in self.schedules],
            "language": self.language,
        }


@dataclass(frozen=True)
class BotConfig:
    name: str
    token: str = ""
    groups: tuple[GroupConfig, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", validate_bot_name(self.name))
        object.__setattr__(self, "token", str(self.token or ""))
        groups: list[GroupConfig] = []
        seen: set[str] = set()
        for item in self.groups:
            group = item if isinstance(item, GroupConfig) else GroupConfig(**item)
            if group.chat_id not in seen:
                groups.append(group)
                seen.add(group.chat_id)
        object.__setattr__(self, "groups", tuple(groups))

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "bot_name": self.name,
            "groups": [group.to_dict() for group in self.groups],
        }

    def with_group(self, group: GroupConfig) -> "BotConfig":
        groups = [item for item in self.groups if item.chat_id != group.chat_id]
        groups.append(group)
        return replace(self, groups=tuple(groups))


@dataclass(frozen=True)
class AppConfig:
    skill_root: str = ""
    bots: tuple[BotConfig, ...] = ()
    groups: tuple[GroupConfig, ...] = ()
    tasks: tuple[PushTaskConfig, ...] = ()

    def __post_init__(self) -> None:
        normalized_bots: list[BotConfig] = []
        seen_names: set[str] = set()
        for item in self.bots:
            bot = item if isinstance(item, BotConfig) else BotConfig(**item)
            if bot.name in seen_names:
                raise ConfigValidationError(f"duplicate bot name: {bot.name}")
            normalized_bots.append(bot)
            seen_names.add(bot.name)
        object.__setattr__(self, "skill_root", str(self.skill_root or "").strip())
        object.__setattr__(self, "bots", tuple(normalized_bots))
        normalized_groups: list[GroupConfig] = []
        seen_group_ids: set[str] = set()
        for item in self.groups:
            group = item if isinstance(item, GroupConfig) else GroupConfig(**dict(item))
            if group.chat_id in seen_group_ids:
                continue
            normalized_groups.append(group)
            seen_group_ids.add(group.chat_id)
        object.__setattr__(self, "groups", tuple(normalized_groups))
        normalized_tasks: list[PushTaskConfig] = []
        seen_task_ids: set[str] = set()
        for item in self.tasks:
            task = item if isinstance(item, PushTaskConfig) else PushTaskConfig(**dict(item))
            if task.task_id in seen_task_ids:
                raise ConfigValidationError(f"duplicate push task id: {task.task_id}")
            normalized_tasks.append(task)
            seen_task_ids.add(task.task_id)
        object.__setattr__(self, "tasks", tuple(normalized_tasks))

    def with_bots(self, bots: tuple[BotConfig, ...]) -> "AppConfig":
        return replace(self, bots=bots)

    def with_tasks(self, tasks: tuple[PushTaskConfig, ...]) -> "AppConfig":
        return replace(self, tasks=tasks)

    def with_groups(self, groups: tuple[GroupConfig, ...]) -> "AppConfig":
        return replace(self, groups=groups)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": 3,
            "skill_root": self.skill_root,
            "bots": [bot.to_dict() for bot in self.bots],
            "groups": [group.to_dict() for group in self.groups],
            "tasks": [task.to_dict() for task in self.tasks],
        }


@dataclass(frozen=True)
class RebateSummary:
    utc_date: str
    coin: str
    trading_volume: Decimal
    fee: Decimal
    commission: Decimal
    sub_affiliate_commission: Decimal
    final_income: Decimal
    formula: str
    utc_start: str = ""
    utc_end: str = ""


@dataclass(frozen=True)
class DeliveryResult:
    ok: bool
    utc_date: str
    sent: tuple[str, ...] = ()
    skipped: tuple[str, ...] = ()
    failed: tuple[str, ...] = ()
    error_messages: tuple[str, ...] = ()
    summary: RebateSummary | None = None
