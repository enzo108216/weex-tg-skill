from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys
import time
import uuid
from zoneinfo import ZoneInfo

from .config import ConfigStore
from .doctor import build_report
from .i18n import available_locales
from .ledger import DeliveryLedger
from .models import AppConfig, BotConfig, GroupConfig, PushTaskConfig, QueryConfig, ScheduleConfig
from .partner import PartnerClient, records_from_partner_envelopes
from .periods import previous_natural_period
from .runtime import ensure_managed_runtime, build_runtime_preflight, reexec_under_managed_runtime
from .service import RebateService
from .telegram import TelegramSender


def _store() -> ConfigStore:
    return ConfigStore()


def _parse_date(value: str | None) -> date:
    if value:
        return date.fromisoformat(value)
    return datetime.now(timezone.utc).date() - timedelta(days=1)


def _service(store: ConfigStore) -> RebateService:
    config = store.load()
    client = PartnerClient(config.skill_root or os.environ.get("WEEX_AGENT_SKILLS_ROOT"))
    return RebateService(config, client, TelegramSender(), DeliveryLedger(store.root / "deliveries.sqlite3"))


def _read_token(args: argparse.Namespace, current: str) -> str:
    if args.token_stdin:
        return sys.stdin.readline().rstrip("\r\n")
    if args.token_env:
        return os.environ.get(args.token_env, "")
    return current


def _config_set(args: argparse.Namespace) -> int:
    store = _store()
    config = store.load()
    current_bot = next((bot for bot in config.bots if bot.name == args.bot), BotConfig(args.bot))
    token = _read_token(args, current_bot.token)
    updated_bot = BotConfig(args.bot, token, current_bot.groups)
    bots = [updated_bot if bot.name == args.bot else bot for bot in config.bots]
    if not any(bot.name == args.bot for bot in bots):
        bots.append(updated_bot)
    updated = AppConfig(
        skill_root=args.skill_root if args.skill_root is not None else config.skill_root,
        bots=tuple(bots),
        groups=config.groups,
        tasks=config.tasks,
    )
    store.update(updated, allow_plaintext=args.allow_plaintext_token)
    print(json.dumps(store.display(), ensure_ascii=False, indent=2))
    return 0


def _scope_from_args(args: argparse.Namespace) -> dict[str, object]:
    if args.all_confirmed:
        return {"mode": "all", "all_confirmed": True}
    if args.uids:
        try:
            values = [int(item.strip()) for item in args.uids.split(",") if item.strip()]
        except ValueError as exc:
            raise ValueError("--uids must be comma-separated positive integers") from exc
        return {"mode": "uids", "uids": values}
    raise ValueError("choose exactly one of --all-confirmed or --uids")


def _parse_schedule_values(values: list[str] | None, *, timezone_name: str = "UTC") -> tuple[ScheduleConfig, ...] | None:
    if values is None:
        return None
    schedules: list[ScheduleConfig] = []
    for value in values:
        text = str(value).strip()
        if "=" not in text:
            raise ValueError("--schedule must use HH:MM=1d|1w|1m|1y|Nd[@YYYY-MM-DD]")
        schedule_time, period = text.split("=", 1)
        start_date = ""
        if "@" in period:
            period, start_date = period.split("@", 1)
        schedules.append(ScheduleConfig(schedule_time, period, start_date=start_date, timezone=timezone_name))
    return tuple(schedules)


def _binding_from_args(args: argparse.Namespace, current: GroupConfig | None = None) -> GroupConfig:
    return GroupConfig(chat_id=args.chat_id, label=args.label or "")


def _config_group(args: argparse.Namespace) -> int:
    store = _store()
    config = store.load()
    group = _binding_from_args(args)
    groups = [item for item in config.groups if item.chat_id != group.chat_id]
    groups.append(group)
    store.update(config.with_groups(tuple(groups)), allow_plaintext=True)
    print(json.dumps(store.display(), ensure_ascii=False, indent=2))
    return 0


def _config_find(args: argparse.Namespace) -> int:
    display = _store().display()
    query = str(args.query or "").casefold()
    if args.kind == "bot":
        matches = [item for item in display["bots"] if query in str(item["name"]).casefold()]
        payload = {"bots": matches}
    else:
        matches = [
            item
            for item in display["groups"]
            if query in str(item.get("group_name") or item.get("label") or "").casefold()
            or query in str(item["chat_id"]).casefold()
        ]
        payload = {"groups": matches}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _config_task(args: argparse.Namespace) -> int:
    store = _store()
    config = store.load()
    bot = next((item for item in config.bots if item.name == args.bot), None)
    if bot is None:
        raise ValueError(f"Bot not found: {args.bot}")
    group = next((item for item in config.groups if item.chat_id == args.chat_id), None)
    if group is None:
        raise ValueError(f"group not found for {args.bot}:{args.chat_id}")
    products = tuple(item.strip().upper() for item in (args.product_types or "SPOT,FUTURES").split(",") if item.strip())
    task = PushTaskConfig(
        task_id=args.task_id or uuid.uuid4().hex,
        name=args.task_name,
        bot_name=args.bot,
        chat_id=group.chat_id,
        profile=args.profile,
        query=QueryConfig(
            coin=args.coin or "USDT",
            product_types=products,
            scope=_scope_from_args(args),
            formula=args.formula or "commission_minus_subaffiliate_commission",
        ),
        schedules=_parse_schedule_values(args.schedule, timezone_name=args.timezone) or (),
        language=args.language,
    )
    tasks = [item for item in config.tasks if item.task_id != task.task_id]
    tasks.append(task)
    store.update(config.with_tasks(tuple(tasks)), allow_plaintext=args.allow_plaintext_token)
    print(json.dumps(store.display(), ensure_ascii=False, indent=2))
    return 0


def _find_group(config: AppConfig, bot_name: str, chat_id: str) -> tuple[BotConfig, GroupConfig]:
    bot = next((item for item in config.bots if item.name == bot_name), None)
    group = next((item for item in (bot.groups if bot else ()) if item.chat_id == chat_id), None)
    if bot is None or group is None:
        raise ValueError(f"binding not found for {bot_name}:{chat_id}")
    return bot, group


def _config_add_schedule(args: argparse.Namespace) -> int:
    store = _store()
    config = store.load()
    _, group = _find_group(config, args.bot, args.chat_id)
    schedule = ScheduleConfig(args.schedule_time, args.period)
    updated = GroupConfig(
        chat_id=group.chat_id,
        label=group.label,
        profile=group.profile,
        query=group.query,
        schedules=group.schedules + (schedule,),
        language=group.language,
    )
    store.upsert_group(updated, bot_name=args.bot)
    print(json.dumps(store.display(), ensure_ascii=False, indent=2))
    return 0


def _config_remove_schedule(args: argparse.Namespace) -> int:
    store = _store()
    config = store.load()
    _, group = _find_group(config, args.bot, args.chat_id)
    schedules = tuple(
        item
        for item in group.schedules
        if not (item.schedule_time == args.schedule_time and item.period == args.period)
    )
    updated = GroupConfig(
        chat_id=group.chat_id,
        label=group.label,
        profile=group.profile,
        query=group.query,
        schedules=schedules,
        language=group.language,
    )
    store.upsert_group(updated, bot_name=args.bot)
    print(json.dumps(store.display(), ensure_ascii=False, indent=2))
    return 0


def _add_binding_args(parser: argparse.ArgumentParser, *, chat_positional: bool = False) -> None:
    if chat_positional:
        parser.add_argument("chat_id")
    else:
        parser.add_argument("--chat-id", required=True)
    parser.add_argument("--label", "--group-name", dest="label", default="", metavar="GROUP_NAME")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="WEEX daily rebate Telegram bot")
    sub = parser.add_subparsers(dest="command", required=True)

    config = sub.add_parser("config", help="manage SQLite-backed Telegram/Partner configuration")
    config_sub = config.add_subparsers(dest="config_command", required=True)
    show = config_sub.add_parser("show")
    show.set_defaults(handler=lambda args: (print(json.dumps(_store().display(), ensure_ascii=False, indent=2)) or 0))

    set_cmd = config_sub.add_parser("set", help="set a Bot token and global runtime settings")
    set_cmd.add_argument("--bot", "--bot-name", dest="bot", default="main", metavar="BOT_NAME")
    set_cmd.add_argument("--skill-root", help="local checkout of https://github.com/weex-labs/weex-agent-skills")
    set_cmd.add_argument("--token-stdin", action="store_true", help="read the Bot token from stdin")
    set_cmd.add_argument("--token-env", help="read the Bot token from this environment variable")
    set_cmd.add_argument("--allow-plaintext-token", action="store_true")
    set_cmd.set_defaults(handler=_config_set)

    add = config_sub.add_parser("add-group", help="create or replace a standalone group")
    _add_binding_args(add, chat_positional=True)
    add.set_defaults(handler=_config_group)

    find = config_sub.add_parser("find", help="find Bots or standalone groups")
    find.add_argument("kind", choices=("bot", "group"))
    find.add_argument("query", nargs="?", default="")
    find.set_defaults(handler=_config_find)

    task = config_sub.add_parser("add-task", help="create an independent push task for an existing Bot/group")
    task.add_argument("chat_id")
    task.add_argument("--bot", "--bot-name", dest="bot", default="main", metavar="BOT_NAME")
    task.add_argument("--task-name", required=True)
    task.add_argument("--task-id")
    task.add_argument("--profile", required=True)
    task.add_argument("--coin", default="USDT")
    task.add_argument("--product-types", default="SPOT,FUTURES")
    scope = task.add_mutually_exclusive_group(required=True)
    scope.add_argument("--all-confirmed", action="store_true")
    scope.add_argument("--uids", help="comma-separated direct/referral UIDs")
    task.add_argument("--formula", choices=("commission_minus_subaffiliate_commission", "commission"), default="commission_minus_subaffiliate_commission")
    task.add_argument("--schedule", action="append", help="schedule HH:MM=1d|1w|1m|1y|Nd@YYYY-MM-DD; use --timezone for the push clock")
    task.add_argument("--timezone", default="UTC", help="IANA timezone for push times; default UTC")
    task.add_argument("--language", choices=available_locales(), default="zh")
    task.add_argument("--allow-plaintext-token", action="store_true")
    task.set_defaults(handler=_config_task)

    remove = config_sub.add_parser("remove-group", help="delete a standalone group and its push tasks")
    remove.add_argument("chat_id")
    remove.set_defaults(handler=lambda args: (_store().remove_group(args.chat_id) or print("group removed") or 0))

    remove_bot = config_sub.add_parser("remove-bot", help="delete a Bot and its push tasks")
    remove_bot.add_argument("bot_name")
    remove_bot.set_defaults(handler=lambda args: (_store().remove_bot(args.bot_name) or print("Bot removed") or 0))

    clear = config_sub.add_parser("clear-token", help="remove the stored Telegram token")
    clear.add_argument("--bot", "--bot-name", dest="bot", default="main", metavar="BOT_NAME")
    clear.set_defaults(handler=lambda args: (_store().clear_bot_token(args.bot) or print("token cleared") or 0))

    send = sub.add_parser("send", help="send one UTC daily summary to every configured binding")
    send.add_argument("--date", dest="utc_date", help="YYYY-MM-DD; defaults to yesterday UTC")
    send.add_argument("--force", action="store_true", help="re-send a previously sent delivery")
    send.set_defaults(handler=_send)

    result_cmd = sub.add_parser("send-result", help="send records returned by the installed weex-partner-skill to one binding")
    result_cmd.add_argument("--date", dest="utc_date", required=True, help="YYYY-MM-DD UTC date")
    result_cmd.add_argument("--input", dest="input_path", default="-", help="Partner result JSON file; '-' reads stdin")
    result_cmd.add_argument("--bot", "--bot-name", dest="bot", required=True, metavar="BOT_NAME")
    result_cmd.add_argument("--chat-id", required=True)
    result_cmd.add_argument("--force", action="store_true", help="re-send a previously sent delivery")
    result_cmd.set_defaults(handler=_send_result)

    test = sub.add_parser("test-telegram", help="send a test message to one configured group")
    test.add_argument("--bot", "--bot-name", dest="bot", default="main", metavar="BOT_NAME")
    test.add_argument("--chat-id")
    test.add_argument("--message", default="WEEX Telegram bot connection test")
    test.add_argument("--token-stdin", action="store_true")
    test.set_defaults(handler=_test_telegram)

    run = sub.add_parser("run", help="run the UTC scheduler")
    run.add_argument("--once", action="store_true", help="execute the configured daily job immediately")
    run.set_defaults(handler=_run)

    gui = sub.add_parser("gui", help="open the Windows/macOS Tk configuration window")
    gui.add_argument("--language", choices=("auto", *available_locales()), default="auto")
    gui.set_defaults(handler=_gui)

    gui_preflight = sub.add_parser("gui-preflight", help="check the managed GUI virtual environment")
    gui_preflight.add_argument("--json", action="store_true", dest="as_json")
    gui_preflight.set_defaults(handler=_gui_preflight)

    gui_install = sub.add_parser("gui-install", help="create the managed GUI virtual environment")
    gui_install.add_argument("--accept-managed-runtime", action="store_true")
    gui_install.add_argument("--json", action="store_true", dest="as_json")
    gui_install.set_defaults(handler=_gui_install)

    doctor = sub.add_parser("doctor", help="detect OS/GUI/keyring readiness and recommend GUI or CLI")
    doctor.add_argument("--json", action="store_true", dest="as_json")
    doctor.set_defaults(handler=_doctor)
    return parser


def _result_payload(result) -> dict[str, object]:
    return {
        "ok": result.ok,
        "date": result.utc_date,
        "sent": result.sent,
        "skipped": result.skipped,
        "failed": result.failed,
        "errors": result.error_messages,
    }


def _scheduled_tasks(
    config: AppConfig,
    now: datetime | None = None,
    *,
    enabled_only: bool = False,
) -> tuple[tuple[BotConfig, GroupConfig, ScheduleConfig], ...]:
    current_time = now.astimezone(timezone.utc).strftime("%H:%M") if now else None
    tasks: list[tuple[BotConfig, GroupConfig, ScheduleConfig]] = []
    if config.tasks:
        bot_map = {bot.name: bot for bot in config.bots}
        for task in config.tasks:
            bot = bot_map.get(task.bot_name)
            if bot is None:
                continue
            catalog_group = next((group for group in bot.groups if group.chat_id == task.chat_id), None)
            group = GroupConfig(
                chat_id=task.chat_id,
                label=(catalog_group.label if catalog_group else "") or task.name,
                profile=task.profile,
                query=task.query,
                schedules=task.schedules,
                language=task.language,
            )
            for schedule in task.schedules:
                if not schedule.enabled:
                    continue
                if current_time is not None:
                    local_time = now.astimezone(ZoneInfo(schedule.timezone)).strftime("%H:%M")
                    if schedule.schedule_time != local_time:
                        continue
                tasks.append((BotConfig(bot.name, bot.token, (group,)), group, schedule))
        return tuple(tasks)
    for bot in config.bots:
        for group in bot.groups:
            for schedule in group.schedules:
                if not schedule.enabled:
                    continue
                if current_time is not None:
                    local_time = now.astimezone(ZoneInfo(schedule.timezone)).strftime("%H:%M")
                    if schedule.schedule_time != local_time:
                        continue
                tasks.append((bot, group, schedule))
    return tuple(tasks)


def _scheduled_bots(config: AppConfig, now: datetime) -> tuple[BotConfig, ...]:
    """Compatibility helper returning due groups, used by older callers."""
    tasks = _scheduled_tasks(config, now)
    grouped: dict[str, BotConfig] = {}
    for bot, group, _ in tasks:
        current = grouped.get(bot.name)
        if current is None:
            grouped[bot.name] = BotConfig(bot.name, bot.token, (group,))
        else:
            grouped[bot.name] = BotConfig(bot.name, bot.token, current.groups + (group,))
    return tuple(grouped.values())


def _send_scheduled_task(
    store: ConfigStore,
    task: tuple[BotConfig, GroupConfig, ScheduleConfig],
    now: datetime,
    *,
    force: bool = False,
) -> int:
    bot, group, schedule = task
    try:
        window = previous_natural_period(
            schedule.period,
            now.astimezone(timezone.utc).date(),
            start_date=schedule.start_date or None,
        )
    except ValueError as exc:
        # An anchored custom window has not completed yet; it is not a task failure.
        if "no completed window" in str(exc):
            return 0
        raise
    service = _service(store)
    result = service.send_for_window(
        window,
        force=force,
        bots=(BotConfig(bot.name, bot.token, (group,)),),
        schedule_key=f"{schedule.timezone}:{schedule.schedule_time}={schedule.period}@{schedule.start_date or '-'}",
    )
    print(json.dumps(_result_payload(result), ensure_ascii=False, indent=2))
    return 0 if result.ok else 2


def _send(args: argparse.Namespace) -> int:
    result = _service(_store()).send_for_date(
        _parse_date(args.utc_date),
        force=args.force,
        bots=getattr(args, "bots", None),
    )
    print(json.dumps(_result_payload(result), ensure_ascii=False, indent=2))
    return 0 if result.ok else 2


def _send_result(args: argparse.Namespace) -> int:
    raw = sys.stdin.read() if args.input_path == "-" else Path(args.input_path).read_text(encoding="utf-8")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("Partner result input is not valid JSON") from exc
    records = records_from_partner_envelopes(payload)
    result = _service(_store()).send_records_for_date(
        _parse_date(args.utc_date),
        records,
        force=args.force,
        bot_name=args.bot,
        chat_id=args.chat_id,
    )
    print(json.dumps(_result_payload(result), ensure_ascii=False, indent=2))
    return 0 if result.ok else 2


def _test_telegram(args: argparse.Namespace) -> int:
    store = _store()
    config = store.load()
    bot = next((item for item in config.bots if item.name == args.bot), None)
    token = bot.token if bot else ""
    if args.token_stdin:
        token = sys.stdin.readline().rstrip("\r\n")
    chat_id = args.chat_id or (bot.groups[0].chat_id if bot and bot.groups else "")
    TelegramSender().send(token, chat_id, args.message)
    print("Telegram message sent")
    return 0


def _run(args: argparse.Namespace) -> int:
    store = _store()
    config = store.load()
    if args.once:
        tasks = _scheduled_tasks(config, enabled_only=True)
        if not tasks:
            raise ValueError("no scheduled bindings are enabled")
        now = datetime.now(timezone.utc)
        codes = [_send_scheduled_task(store, task, now) for task in tasks]
        return 0 if all(code == 0 for code in codes) else 2
    if not _scheduled_tasks(config):
        raise ValueError("no scheduled push tasks are enabled; add a task with config add-task and --schedule")
    print("scheduler active with per-task timezone schedules and natural periods; press Ctrl-C to stop")
    last_key = None
    while True:
        now = datetime.now(timezone.utc)
        key = f"{now.date().isoformat()} {now.strftime('%H:%M')}"
        due = _scheduled_tasks(config, now)
        if due and key != last_key:
            for task in due:
                _send_scheduled_task(store, task, now)
            last_key = key
        time.sleep(20)


def _gui(args: argparse.Namespace | None = None) -> int:
    language = getattr(args, "language", "auto")
    reexec_under_managed_runtime(["--language", language])
    from .gui import launch

    launch(_store(), language=language)
    return 0


def _gui_preflight(args: argparse.Namespace) -> int:
    report = build_runtime_preflight()
    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Managed GUI runtime: {'ready' if report['ready'] else 'not ready'}")
        print(f"Reason: {report['reason']}")
        print(f"Python: {report['python']}")
        if report.get("setup_command"):
            print(f"Setup: {report['setup_command']}")
        if report.get("error"):
            print(f"Error: {report['error']}")
    return 0 if report["ready"] else 2


def _gui_install(args: argparse.Namespace) -> int:
    report = ensure_managed_runtime(accept_managed_runtime=args.accept_managed_runtime)
    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Managed GUI runtime: {'ready' if report['ready'] else 'not ready'}")
        print(f"Reason: {report['reason']}")
        if report.get("setup_command"):
            print(f"Setup: {report['setup_command']}")
        if report.get("error"):
            print(f"Error: {report['error']}")
    return 0 if report["ready"] else 2


def _doctor(args: argparse.Namespace) -> int:
    report = build_report()
    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"OS: {report['os']}")
        print(f"Tkinter: {'ready' if report['tkinter_importable'] else 'missing'}")
        print(f"Desktop session: {'ready' if report['desktop_available'] else 'missing'}")
        print(f"GUI capable: {'yes' if report['gui_capable'] else 'no'}")
        print(f"OS keyring: {'ready' if report['keyring_available'] else 'missing'}")
        print(f"Recommendation: {report['recommendation']}")
        candidates = report.get("skill_root_candidates") or ()
        print(f"Partner skill candidates: {', '.join(candidates) if candidates else 'none found'}")
        for reason in report["reasons"]:
            print(f"- {reason}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.handler(args))
    except KeyboardInterrupt:
        print("stopped")
        return 130
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
