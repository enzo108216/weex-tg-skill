from __future__ import annotations

from datetime import date, datetime, time, timezone
import json
from typing import Iterable

from .aggregate import aggregate_records
from .formatter import format_summary, localized_trigger
from .ledger import DeliveryLedger
from .models import AppConfig, BotConfig, DeliveryResult, GroupConfig, PushTaskConfig, RebateSummary
from .periods import PeriodWindow


class RebateService:
    def __init__(self, config: AppConfig, partner, telegram, ledger: DeliveryLedger) -> None:
        self.config = config
        self.partner = partner
        self.telegram = telegram
        self.ledger = ledger

    def _targets(
        self,
        groups: Iterable[GroupConfig] | None = None,
        bots: Iterable[BotConfig] | None = None,
    ) -> tuple[BotConfig, ...]:
        if bots is None and groups is None and self.config.tasks:
            return self._task_targets()
        if bots is not None:
            return tuple(bots)
        if groups is not None:
            base = next((bot for bot in self.config.bots if bot.name == "main"), None)
            if base is None:
                raise ValueError("main bot is required when selecting groups")
            return (BotConfig(base.name, base.token, tuple(groups)),)
        return tuple(self.config.bots)

    def _task_targets(self, task_ids: Iterable[str] | None = None) -> tuple[BotConfig, ...]:
        selected = set(task_ids or ())
        bot_map = {bot.name: bot for bot in self.config.bots}
        grouped: dict[str, list[GroupConfig]] = {}
        for task in self.config.tasks:
            if selected and task.task_id not in selected:
                continue
            bot = bot_map.get(task.bot_name)
            if bot is None:
                continue
            catalog_group = next((group for group in bot.groups if group.chat_id == task.chat_id), None)
            grouped.setdefault(task.bot_name, []).append(
                GroupConfig(
                    chat_id=task.chat_id,
                    label=(catalog_group.label if catalog_group else "") or task.name,
                    profile=task.profile,
                    query=task.query,
                    schedules=task.schedules,
                    language=task.language,
                )
            )
        return tuple(
            BotConfig(name, bot_map[name].token, tuple(groups))
            for name, groups in grouped.items()
        )

    def send_task_for_date(self, task_id: str, utc_date: date, *, force: bool = False) -> DeliveryResult:
        targets = self._task_targets((task_id,))
        if sum(len(bot.groups) for bot in targets) != 1:
            raise ValueError(f"push task not found: {task_id}")
        return self.send_for_date(utc_date, force=force, bots=targets)

    @staticmethod
    def _target_label(bot: BotConfig, chat_id: str) -> str:
        return chat_id if bot.name == "main" else f"{bot.name}:{chat_id}"

    @staticmethod
    def _validate_targets(targets: tuple[BotConfig, ...]) -> None:
        if not targets:
            raise ValueError("at least one Telegram bot is required")
        for bot in targets:
            if not bot.token:
                raise ValueError(f"Telegram bot token is required for bot {bot.name}")
            if not bot.groups:
                raise ValueError(f"at least one Telegram group is required for bot {bot.name}")
            for group in bot.groups:
                if not group.profile:
                    raise ValueError(
                        f"WEEX profile is required for {bot.name}:{group.chat_id}"
                    )

    @staticmethod
    def _query_key(group: GroupConfig) -> tuple[str, str]:
        return (
            group.profile,
            json.dumps(group.query.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        )

    @staticmethod
    def _utc_bounds(start_date: date, end_date: date) -> tuple[str, str]:
        start = datetime.combine(start_date, time.min, timezone.utc)
        end = datetime.combine(end_date, time.max, timezone.utc).replace(microsecond=999000)
        return (
            start.isoformat(timespec="seconds").replace("+00:00", "Z"),
            end.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        )

    @staticmethod
    def _format_for_binding(
        summary: RebateSummary,
        bot: BotConfig,
        group: GroupConfig,
        *,
        trigger: str | None = None,
        trigger_kind: str | None = None,
        schedule_key: str = "",
    ) -> str:
        if trigger_kind:
            trigger = localized_trigger(group.language, trigger_kind, schedule_key)
        return format_summary(
            summary,
            trigger=trigger or "",
            profile=group.profile,
            scope=group.query.scope,
            product_types=group.query.product_types,
            bot_name=bot.name,
            target_label=group.label or group.chat_id,
            language=group.language,
        )

    def _prepare_summaries(
        self,
        utc_date: date,
        targets: tuple[BotConfig, ...],
        *,
        trigger: str = "手动查询",
    ) -> dict[tuple[str, str], tuple[str, str, RebateSummary]]:
        """Fetch and aggregate all unique bindings before any Telegram send."""
        cache: dict[tuple[str, str], RebateSummary] = {}
        prepared: dict[tuple[str, str], tuple[str, str, RebateSummary]] = {}
        utc_start, utc_end = self._utc_bounds(utc_date, utc_date)
        for bot in targets:
            for group in bot.groups:
                key = self._query_key(group)
                if key not in cache:
                    records = self.partner.fetch_records(group.profile, utc_date, group.query)
                    summary = aggregate_records(
                        records,
                        utc_date=utc_date.isoformat(),
                        coin=group.query.coin,
                        formula=group.query.formula,
                        utc_start=utc_start,
                        utc_end=utc_end,
                    )
                    cache[key] = summary
                summary = cache[key]
                text = self._format_for_binding(summary, bot, group, trigger_kind="manual")
                prepared[(bot.name, group.chat_id)] = (group.profile, text, summary)
        return prepared

    def _prepare_window_summaries(
        self,
        window: PeriodWindow,
        targets: tuple[BotConfig, ...],
        *,
        schedule_key: str = "",
    ) -> dict[tuple[str, str], tuple[str, str, RebateSummary]]:
        cache: dict[tuple[str, str], RebateSummary] = {}
        prepared: dict[tuple[str, str], tuple[str, str, RebateSummary]] = {}
        utc_start, utc_end = self._utc_bounds(window.start, window.end)
        for bot in targets:
            for group in bot.groups:
                key = self._query_key(group)
                if key not in cache:
                    records = self.partner.fetch_records_for_range(
                        group.profile,
                        window.start,
                        window.end,
                        group.query,
                    )
                    summary = aggregate_records(
                        records,
                        utc_date=window.key,
                        utc_start=utc_start,
                        utc_end=utc_end,
                        coin=group.query.coin,
                        formula=group.query.formula,
                    )
                    cache[key] = summary
                summary = cache[key]
                text = self._format_for_binding(summary, bot, group, trigger_kind="scheduled", schedule_key=schedule_key)
                prepared[(bot.name, group.chat_id)] = (group.profile, text, summary)
        return prepared

    def send_for_date(
        self,
        utc_date: date,
        *,
        force: bool = False,
        groups: Iterable[GroupConfig] | None = None,
        bots: Iterable[BotConfig] | None = None,
    ) -> DeliveryResult:
        targets = self._targets(groups=groups, bots=bots)
        self._validate_targets(targets)
        prepared = self._prepare_summaries(utc_date, targets, trigger="手动查询")
        return self._send_prepared(utc_date.isoformat(), targets, prepared, force=force)

    def send_for_window(
        self,
        window: PeriodWindow,
        *,
        force: bool = False,
        bots: Iterable[BotConfig] | None = None,
        schedule_key: str | None = None,
    ) -> DeliveryResult:
        targets = self._targets(bots=bots)
        self._validate_targets(targets)
        prepared = self._prepare_window_summaries(window, targets, schedule_key=schedule_key or "")
        delivery_key = f"{window.key}@{schedule_key}" if schedule_key else window.key
        return self._send_prepared(delivery_key, targets, prepared, force=force)

    def _send_prepared(
        self,
        delivery_key: str,
        targets: tuple[BotConfig, ...],
        prepared: dict[tuple[str, str], tuple[str, str, RebateSummary]],
        *,
        force: bool,
    ) -> DeliveryResult:
        sent: list[str] = []
        skipped: list[str] = []
        failed: list[str] = []
        errors: list[str] = []
        summaries: list[RebateSummary] = []
        for bot in targets:
            for group in bot.groups:
                label = self._target_label(bot, group.chat_id)
                profile, text, summary = prepared[(bot.name, group.chat_id)]
                summaries.append(summary)
                if not self.ledger.reserve(
                    profile,
                    delivery_key,
                    group.chat_id,
                    bot_name=bot.name,
                    force=force,
                ):
                    skipped.append(label)
                    continue
                try:
                    self.telegram.send(bot.token, group.chat_id, text)
                except Exception as exc:
                    message = str(exc) or "Telegram send failed"
                    self.ledger.mark_failed(
                        profile,
                        delivery_key,
                        group.chat_id,
                        message,
                        bot_name=bot.name,
                    )
                    failed.append(label)
                    errors.append(f"{label}: {message}")
                else:
                    self.ledger.mark_sent(
                        profile,
                        delivery_key,
                        group.chat_id,
                        bot_name=bot.name,
                    )
                    sent.append(label)
        return DeliveryResult(
            ok=not failed,
            utc_date=delivery_key,
            sent=tuple(sent),
            skipped=tuple(skipped),
            failed=tuple(failed),
            error_messages=tuple(errors),
            summary=summaries[0] if summaries else None,
        )

    def _select_binding(
        self,
        *,
        bot_name: str | None = None,
        chat_id: str | None = None,
    ) -> tuple[BotConfig, GroupConfig]:
        if self.config.tasks:
            bot_map = {bot.name: bot for bot in self.config.bots}
            task_candidates = [
                task for task in self.config.tasks
                if (bot_name is None or task.bot_name == bot_name)
                and (chat_id is None or task.chat_id == chat_id)
            ]
            if len(task_candidates) == 1:
                task = task_candidates[0]
                bot = bot_map.get(task.bot_name)
                if bot is not None:
                    catalog_group = next((group for group in bot.groups if group.chat_id == task.chat_id), None)
                    return bot, GroupConfig(
                        chat_id=task.chat_id,
                        label=(catalog_group.label if catalog_group else "") or task.name,
                        profile=task.profile,
                        query=task.query,
                        schedules=task.schedules,
                        language=task.language,
                    )
        candidates = [
            (bot, group)
            for bot in self.config.bots
            for group in bot.groups
            if (bot_name is None or bot.name == bot_name)
            and (chat_id is None or group.chat_id == chat_id)
        ]
        if len(candidates) != 1:
            raise ValueError("send-result requires exactly one configured --bot and --chat-id binding")
        return candidates[0]

    def send_records_for_date(
        self,
        utc_date: date,
        records,
        *,
        force: bool = False,
        groups: Iterable[GroupConfig] | None = None,
        bots: Iterable[BotConfig] | None = None,
        bot_name: str | None = None,
        chat_id: str | None = None,
    ) -> DeliveryResult:
        if bot_name is not None or chat_id is not None:
            bot, group = self._select_binding(bot_name=bot_name, chat_id=chat_id)
            targets = (BotConfig(bot.name, bot.token, (group,)),)
        elif groups is not None or bots is not None:
            targets = self._targets(groups=groups, bots=bots)
            if sum(len(bot.groups) for bot in targets) != 1:
                raise ValueError("send-result requires exactly one configured binding")
        else:
            targets = self._targets()
            if sum(len(bot.groups) for bot in targets) != 1:
                raise ValueError("send-result requires exactly one configured binding")
        self._validate_targets(targets)
        group = targets[0].groups[0]
        summary = aggregate_records(
            records,
            utc_date=utc_date.isoformat(),
            utc_start=self._utc_bounds(utc_date, utc_date)[0],
            utc_end=self._utc_bounds(utc_date, utc_date)[1],
            coin=group.query.coin,
            formula=group.query.formula,
        )
        prepared = {
            (targets[0].name, group.chat_id): (
                group.profile,
                self._format_for_binding(summary, targets[0], group, trigger_kind="manual"),
                summary,
            )
        }
        return self._send_prepared(utc_date.isoformat(), targets, prepared, force=force)
