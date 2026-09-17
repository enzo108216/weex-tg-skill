from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import calendar
from zoneinfo import available_timezones
import locale
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Any
import uuid

from .config import ConfigStore, mask_token
from .discovery import discover_commission_filters, discover_saved_profiles, discover_skill_roots
from .i18n import (
    is_rtl,
    load_locale_catalog,
    locale_base,
    locale_display_name,
    locale_options,
    normalize_locale,
    translate,
)
from .ledger import DeliveryLedger
from .models import AppConfig, BotConfig, GroupConfig, PushTaskConfig, QueryConfig, ScheduleConfig
from .partner import PartnerClient
from .service import RebateService
from .scheduler import GuiScheduler
from .telegram import TelegramSender


BUILTIN_TRANSLATIONS: dict[str, dict[str, str]] = {
    "zh": {
        "window_title": "WEEX 返佣推送",
        "subtitle": "先管理 Bot，再关联群组和推送查询",
        "language": "语言",
        "overview": "概览",
        "bots_tab": "Bot 管理",
        "groups_tab": "群组与推送",
        "tasks_tab": "推送任务",
        "help": "使用说明",
        "overview_hint": "从这里查看所有 Bot、群组和关联关系；新建推送时直接选择已添加的 Bot 与群组。",
        "bots": "Bot 数量",
        "bindings": "群组绑定",
        "schedules": "定时任务",
        "skill_root": "Partner skill",
        "keyring": "Token 存储",
        "ready": "已配置",
        "not_configured": "未配置",
        "available": "可用",
        "unavailable": "不可用",
        "bot_list": "已添加的 Bot",
        "group_list": "群组关联查询",
        "bot_details": "Bot 信息",
        "group_details": "群组与查询",
        "task_details": "推送任务配置",
        "task_list": "推送任务列表",
        "task_status": "状态",
        "run_task": "立即发送",
        "test_task": "测试 Telegram",
        "all_tasks": "全部任务",
        "bot_name": "Bot 名称",
        "group_name": "群名称",
        "chat_id": "Chat ID",
        "profile": "WEEX 账号 profile",
        "token": "Telegram Bot Token",
        "bot_selector": "选择 Bot",
        "group_selector": "选择群组",
        "task_name": "任务名称",
        "task_selector": "选择推送任务",
        "groups_count": "群组数",
        "token_state": "Token 状态",
        "configured": "已配置",
        "missing": "缺失",
        "new_bot": "新建 Bot",
        "edit_bot": "编辑选中 Bot",
        "save_bot": "保存 Bot",
        "new_group": "新建群组",
        "edit_group": "编辑选中群组",
        "save_group": "保存群组",
        "new_task": "新建推送任务",
        "edit_task": "编辑推送任务",
        "save_task": "保存推送任务",
        "refresh": "刷新",
        "use_detected": "使用发现路径",
        "detected_skill": "AI 发现的 skill 路径",
        "destination": "推送目标",
        "query": "查询口径",
        "coin": "结算币种",
        "products": "产品类型",
        "uids": "下级 UID（逗号分隔）",
        "all_scope": "确认查询全部下级",
        "formula": "Final Income 公式",
        "runtime": "运行设置",
        "execution_time": "执行时间（任务时区）",
        "periods": "选择周期（可多选）",
        "selected_schedules": "已添加的定时",
        "query_window": "查询范围（多选）",
        "push_time": "推送时间",
        "timezone": "时区",
        "timezone_search": "搜索时区",
        "range_to": " 至 ",
        "selected_windows": "已选查询窗口",
        "selected_times": "已选推送时间",
        "add_window": "添加近 N 天",
        "add_push_time": "添加时间",
        "select_date": "选择日期",
        "date_picker": "选择 UTC 开始日期",
        "add_schedule": "添加定时",
        "remove_schedule": "移除选中",
        "manual_only": "仅手动",
        "skill_path": "Partner skill 路径",
        "browse": "选择目录",
        "plaintext": "Token 保存到本地 SQLite 数据库",
        "clear_token": "清除 Token",
        "test": "测试 Telegram",
        "send": "发送上一完整 UTC 日",
        "help_title": "使用说明",
        "help_body": "1. “概览”显示 Bot 状态、群组目录、任务数量和调度数量；使用“新建/编辑”按钮打开对应弹窗。Bot 可保存名称、Token 和 Partner skill 路径；群组只保存群名称与 Chat ID。\n\n2. 在“推送任务”页新建或编辑任务，选择 Bot、群组、已保存的 WEEX profile 和任务 language。一个 Bot 可对应多个群组，一个群组也可被多个任务复用；修改群组 Chat ID 会同步任务目标。\n\n3. 任务配置支持动态发现的币种/产品提示、全部下级确认或通过官方 list-referral-uids 加载并搜索多选 UID，并支持 Final Income 公式选择。\n\n4. 查询范围支持上一完整 UTC 日/周/月/年和自定义 N 天；自定义窗口必须填写 UTC 开始日期。推送时间可添加多个时间，并使用任务自己的 IANA timezone（支持夏令时）；查询窗口仍按 UTC 计算。\n\n5. 任务列表可编辑、测试 Telegram 或立即发送上一完整 UTC 日。GUI 打开期间会运行后台 scheduler，关闭窗口后停止；右上角 language selector 可切换已安装语言。\n\n安全提示：Token 默认保存到本地 SQLite 数据库，数据库文件权限为 600。",
        "saved": "配置已保存",
        "success": "成功",
        "telegram_sent": "Telegram 消息已发送",
        "configuration_error": "配置错误",
        "telegram_test_failed": "Telegram 测试失败",
        "send_failed": "发送失败",
        "clear_title": "清除 Token",
        "clear_confirm": "确定清除当前 Bot 的 Token 吗？",
        "bot_missing": "请先添加 Bot。",
        "group_missing": "请先选择 Bot 并填写群组信息。",
        "scope_error": "请确认全部下级，或填写至少一个 UID。",
        "schedule_error": "定时需要有效的时间、IANA 时区和 1d|1w|1m|1y 或带 UTC 起始日期的 Nd 窗口。",
        "period_error": "请至少选择一个周期。",
        "select_binding": "请先选择一个 Bot 或群组。",
        "status_configured": "配置已加载",
        "status_empty": "尚未配置 Bot/群组",
        "cancel": "取消",
        "load_uids": "加载 UID",
        "custom_window": "近 N 天（不含今天）",
        "start_date_utc": "开始日期（UTC）",
        "positive_integer_error": "N 必须是正整数",
        "invalid_time": "时间格式无效",
        "select_profile_first": "请先选择或填写 WEEX profile",
        "confirm_skill_path": "请先确认 Partner skill 路径",
        "select_product": "至少选择一个产品类型",
        "select_query_window": "请至少选择一个查询范围",
        "window_1d": "上一完整自然日",
        "window_1w": "上一完整自然周",
        "window_1m": "上一完整自然月",
        "window_1y": "上一完整自然年",
        "product_spot": "现货交易",
        "product_futures": "合约交易",
        "trigger_manual": "手动查询",
        "trigger_scheduled": "定时任务",
        "trigger_scheduled_with_key": "定时任务（{schedule}）",
        "test_message": "WEEX Telegram 机器人连接测试",
        "task_count": "{count} 个任务",
        "weekday_names": "一,二,三,四,五,六,日",
        "group_in_use": "群组正在被推送任务使用，请先修改任务目标。",
        "formula_option_subaffiliate": "佣金 - 下级返佣",
        "formula_option_commission": "佣金",
    },
    "en": {
        "window_title": "WEEX Rebate Delivery",
        "subtitle": "Add Bots first, then associate groups and push queries",
        "language": "Language",
        "overview": "Overview",
        "bots_tab": "Bot management",
        "groups_tab": "Groups & push",
        "tasks_tab": "Push tasks",
        "help": "Help",
        "overview_hint": "Inspect every Bot, group, and association here; create pushes by selecting existing targets.",
        "bots": "Bots",
        "bindings": "Group bindings",
        "schedules": "Schedules",
        "skill_root": "Partner skill",
        "keyring": "Token storage",
        "ready": "Configured",
        "not_configured": "Not configured",
        "available": "Available",
        "unavailable": "Unavailable",
        "bot_list": "Added Bots",
        "group_list": "Group associations",
        "bot_details": "Bot details",
        "group_details": "Group and query",
        "task_details": "Push task configuration",
        "task_list": "Push task list",
        "task_status": "Status",
        "run_task": "Send now",
        "test_task": "Test Telegram",
        "all_tasks": "All tasks",
        "bot_name": "Bot name",
        "group_name": "Group name",
        "chat_id": "Chat ID",
        "profile": "WEEX profile",
        "token": "Telegram Bot Token",
        "bot_selector": "Select Bot",
        "group_selector": "Select group",
        "task_name": "Task name",
        "task_selector": "Select push task",
        "groups_count": "Groups",
        "token_state": "Token",
        "configured": "Configured",
        "missing": "Missing",
        "new_bot": "New Bot",
        "edit_bot": "Edit selected Bot",
        "save_bot": "Save Bot",
        "new_group": "New group",
        "edit_group": "Edit selected group",
        "save_group": "Save group",
        "new_task": "New push task",
        "edit_task": "Edit push task",
        "save_task": "Save push task",
        "refresh": "Refresh",
        "use_detected": "Use detected path",
        "detected_skill": "Skill path discovered by AI",
        "destination": "Destination",
        "query": "Query contract",
        "coin": "Settlement coin",
        "products": "Product type",
        "uids": "Referral UIDs (comma-separated)",
        "all_scope": "Confirm all-referrals scope",
        "formula": "Final Income formula",
        "runtime": "Runtime",
        "execution_time": "Execution time (task timezone)",
        "periods": "Periods (multi-select)",
        "selected_schedules": "Configured schedules",
        "query_window": "Query windows (multi-select)",
        "push_time": "Push time",
        "timezone": "Timezone",
        "timezone_search": "Search time zones",
        "range_to": " to ",
        "selected_windows": "Selected query windows",
        "selected_times": "Selected push times",
        "add_window": "Add N-day window",
        "add_push_time": "Add time",
        "select_date": "Choose date",
        "date_picker": "Choose UTC start date",
        "add_schedule": "Add schedule",
        "remove_schedule": "Remove selected",
        "manual_only": "Manual only",
        "skill_path": "Partner skill path",
        "browse": "Browse",
        "plaintext": "Store the Telegram token in the local SQLite database",
        "clear_token": "Clear token",
        "test": "Test Telegram",
        "send": "Send previous complete UTC day",
        "help_title": "How it works",
        "help_body": "1. Overview shows Bot status, the group catalog, task counts, and schedule counts; use New/Edit buttons to open the corresponding modal. A Bot stores its name, token, and Partner skill path; a group stores only its name and Chat ID.\n\n2. In Push tasks, create or edit a task by selecting a Bot, group, saved WEEX profile, and task language. One Bot can serve many groups, and a group can be reused by multiple tasks; editing a group Chat ID updates task targets.\n\n3. Task setup uses dynamically discovered coin/product hints, supports confirmed all-referrals or loading, searching, and multi-selecting UIDs through the official list-referral-uids operation, and lets you choose the Final Income formula.\n\n4. Query windows support the previous complete UTC day/week/month/year and custom N-day windows; custom windows require a UTC start date. Add multiple push times and use the task's own IANA timezone (including DST); query windows remain UTC.\n\n5. The task list can edit, test Telegram, or send the previous complete UTC day immediately. The GUI runs a background scheduler while open and stops it on close; switch the installed language with the top-right language selector.\n\nSecurity: tokens are stored in the local SQLite database with file permissions 600.",
        "saved": "Configuration saved",
        "success": "Success",
        "telegram_sent": "Telegram message sent",
        "configuration_error": "Configuration error",
        "telegram_test_failed": "Telegram test failed",
        "send_failed": "Send failed",
        "clear_title": "Clear token",
        "clear_confirm": "Clear the token for the current Bot?",
        "bot_missing": "Add a Bot first.",
        "group_missing": "Select a Bot and complete the group fields first.",
        "scope_error": "Confirm all referrals or enter at least one UID.",
        "schedule_error": "Choose a valid time, IANA timezone, and a 1d|1w|1m|1y or anchored Nd window.",
        "period_error": "Select at least one period.",
        "select_binding": "Select a Bot or group first.",
        "status_configured": "Configuration loaded",
        "status_empty": "No Bot or group configured",
        "cancel": "Cancel",
        "load_uids": "Load UIDs",
        "custom_window": "Last N days (excluding today)",
        "start_date_utc": "Start date (UTC)",
        "positive_integer_error": "N must be a positive integer",
        "invalid_time": "Invalid time",
        "select_profile_first": "Select or enter a WEEX profile first",
        "confirm_skill_path": "Confirm the Partner skill path first",
        "select_product": "Select at least one product type",
        "select_query_window": "Select at least one query window",
        "window_1d": "Previous complete natural day",
        "window_1w": "Previous complete natural week",
        "window_1m": "Previous complete natural month",
        "window_1y": "Previous complete natural year",
        "product_spot": "Spot trading",
        "product_futures": "Futures trading",
        "trigger_manual": "Manual query",
        "trigger_scheduled": "Scheduled task",
        "trigger_scheduled_with_key": "Scheduled task ({schedule})",
        "test_message": "WEEX Telegram bot connection test",
        "task_count": "{count} task(s)",
        "weekday_names": "Mo,Tu,We,Th,Fr,Sa,Su",
        "group_in_use": "This group is used by a push task; edit the task target first.",
        "formula_option_subaffiliate": "Commission - Sub-affiliate Commission",
        "formula_option_commission": "Commission",
    },
}

TRANSLATIONS = load_locale_catalog(BUILTIN_TRANSLATIONS)


def detect_language(requested: str | None = None) -> str:
    value = normalize_locale(requested)
    if requested and str(requested).strip().lower() not in {"auto", ""}:
        return value if value in TRANSLATIONS or locale_base(value) in TRANSLATIONS else ("en" if "en" in TRANSLATIONS else "en_us")
    try:
        system_locale = locale.getlocale()[0] or locale.getdefaultlocale()[0] or ""
    except (ValueError, AttributeError):
        system_locale = ""
    detected = normalize_locale(system_locale)
    return detected if detected in TRANSLATIONS else locale_base(detected) if locale_base(detected) in TRANSLATIONS else ("en" if "en" in TRANSLATIONS else "en_us")


def text_for(key: str, language: str = "en", **values: Any) -> str:
    return translate(TRANSLATIONS, language, key, **values)


WINDOW_KEYS = {"1d": "window_1d", "1w": "window_1w", "1m": "window_1m", "1y": "window_1y"}
PRODUCT_KEYS = {"SPOT": "product_spot", "FUTURES": "product_futures"}


def period_label(period: str, language: str) -> str:
    """Render an internal period code as a localized, user-facing label."""
    if period in WINDOW_KEYS:
        return text_for(WINDOW_KEYS[period], language)
    if period.endswith("d") and period[:-1].isdigit():
        return text_for("custom_window", language).replace("N", period[:-1])
    return period


def filter_timezones(values: tuple[str, ...] | list[str], query: str) -> tuple[str, ...]:
    """Filter IANA timezone names by a case-insensitive substring query."""
    needle = str(query or "").strip().casefold()
    if not needle:
        return tuple(values)
    return tuple(value for value in values if needle in value.casefold())


def resolve_timezone_query(
    values: tuple[str, ...] | list[str],
    current: str,
    query: str,
) -> str:
    """Resolve a search query when it identifies exactly one IANA timezone."""
    matches = filter_timezones(values, query)
    return matches[0] if len(matches) == 1 else current


def merge_schedule_entries(
    existing: tuple[tuple[str, str], ...] | list[tuple[str, str]],
    schedule_time: str,
    periods: list[str] | tuple[str, ...],
) -> tuple[tuple[str, str], ...]:
    merged = set(existing)
    for period in periods:
        ScheduleConfig(schedule_time, period)
        merged.add((schedule_time, period))
    return tuple(sorted(merged))


def resolve_push_times(
    existing: tuple[str, ...] | list[str],
    initial_time: str,
    current_time: str,
) -> tuple[str, ...]:
    """Apply the editor's current time without losing multi-time schedules.

    When a task has only one existing time, editing the time field replaces it.
    Once multiple times exist, a changed editor value is added to the set.
    """
    ScheduleConfig(current_time, "1d")
    values = list(dict.fromkeys(existing))
    if current_time not in values:
        if len(values) == 1 and values[0] == initial_time:
            values = [current_time]
        else:
            values.append(current_time)
    return tuple(sorted(values))


def remap_task_chat_id(
    tasks: tuple[PushTaskConfig, ...] | list[PushTaskConfig],
    old_chat_id: str | None,
    new_chat_id: str,
) -> tuple[PushTaskConfig, ...]:
    """Keep push tasks linked when a saved group's Chat ID is edited."""
    if not old_chat_id or old_chat_id == new_chat_id:
        return tuple(tasks)
    return tuple(
        PushTaskConfig(
            task_id=task.task_id,
            name=task.name,
            bot_name=task.bot_name,
            chat_id=new_chat_id if task.chat_id == old_chat_id else task.chat_id,
            profile=task.profile,
            query=task.query,
            schedules=task.schedules,
            language=task.language,
        )
        for task in tasks
    )


class ConfigWindow(tk.Tk):
    def __init__(self, store: ConfigStore, language: str = "auto") -> None:
        super().__init__()
        self.store = store
        requested_language = str(language or "auto").strip()
        if requested_language.lower() in {"", "auto"}:
            requested_language = store.get_gui_language() or requested_language
        self._language = detect_language(requested_language)
        if str(language or "auto").strip().lower() not in {"", "auto"}:
            store.set_gui_language(self._language)
        self._locale_options = locale_options(TRANSLATIONS)
        self._locale_code_to_name = dict(self._locale_options)
        self._locale_name_to_code = {name: code for code, name in self._locale_options}
        self._i18n_widgets: dict[str, list[Any]] = {}
        self._bot_keys: dict[str, str] = {}
        self._group_keys: dict[str, tuple[str, str]] = {}
        self._task_keys: dict[str, str] = {}
        self._overview_bot_filter: str | None = None
        self._editing_bot_name: str | None = None
        self._editing_group_key: tuple[str, str] | None = None
        self._editing_task_id: str | None = None
        self._schedule_entries: list[tuple[str, str]] = []
        self._skill_candidates = discover_skill_roots()
        self.title(text_for("window_title", self._language))
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        window_width = min(1240, max(720, screen_width - 40))
        window_height = min(860, max(560, screen_height - 80))
        self.minsize(min(900, window_width), min(620, window_height))
        self.geometry(f"{window_width}x{window_height}")

        config = store.load()
        first_bot = config.bots[0] if config.bots else None
        first_group = first_bot.groups[0] if first_bot and first_bot.groups else None
        query = first_group.query if first_group else QueryConfig()
        self.bot_edit_name = tk.StringVar(value=first_bot.name if first_bot else "")
        self.bot_edit_token = tk.StringVar(value=first_bot.token if first_bot else "")
        self.bot_edit_skill_root = tk.StringVar(value=config.skill_root)
        self.group_bot_choice = tk.StringVar(value=first_bot.name if first_bot else "")
        self.group_choice = tk.StringVar(value=(first_group.label or first_group.chat_id) if first_group else "")
        self.task_bot_choice = tk.StringVar(value=first_bot.name if first_bot else "")
        self.task_group_choice = tk.StringVar(value=(first_group.label or first_group.chat_id) if first_group else "")
        self.task_name = tk.StringVar(value="")
        self.task_choice = tk.StringVar(value="")
        self.group_name = tk.StringVar(value=first_group.label if first_group else "")
        self.chat_id = tk.StringVar(value=first_group.chat_id if first_group else "")
        self.profile = tk.StringVar(value=first_group.profile if first_group else "")
        self.coin = tk.StringVar(value=query.coin)
        self.product_types = tk.StringVar(value=", ".join(query.product_types))
        self.uids = tk.StringVar(value=", ".join(str(item) for item in query.scope.get("uids", ())))
        self.all_confirmed = tk.BooleanVar(
            value=query.scope.get("mode") == "all" and query.scope.get("all_confirmed") is True
        )
        self.formula = tk.StringVar(value=query.formula)
        self.allow_plaintext = tk.BooleanVar(value=False)
        self.schedule_hour = tk.StringVar(value="09")
        self.schedule_minute = tk.StringVar(value="00")
        self.period_vars = {period: tk.BooleanVar(value=False) for period in ("1d", "1w", "1m", "1y")}
        self.language_choice = tk.StringVar(value=self._locale_code_to_name.get(self._language, locale_display_name(TRANSLATIONS, self._language)))
        self.status_var = tk.StringVar()
        self.skill_hint = tk.StringVar()
        self._build()
        self._refresh_all()

    def _register_i18n(self, widget: Any, key: str) -> Any:
        self._i18n_widgets.setdefault(key, []).append(widget)
        return widget

    def _label(self, parent: Any, key: str, **kwargs: Any) -> Any:
        return self._register_i18n(ttk.Label(parent, **kwargs), key)

    def _button(self, parent: Any, key: str, command: Any, **kwargs: Any) -> Any:
        return self._register_i18n(ttk.Button(parent, command=command, **kwargs), key)

    def _frame(self, parent: Any, key: str, **kwargs: Any) -> Any:
        return self._register_i18n(ttk.LabelFrame(parent, **kwargs), key)

    def _form_entry(self, parent: Any, row: int, label_key: str, variable: tk.StringVar, *, secret: bool = False, column: int = 0) -> None:
        self._label(parent, label_key).grid(row=row, column=column, sticky="w", padx=(0, 8), pady=6)
        ttk.Entry(parent, textvariable=variable, show="•" if secret else "").grid(
            row=row, column=column + 1, sticky="ew", padx=(0, 16), pady=6
        )

    def _build(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Header.TLabel", font=("Helvetica", 18, "bold"))
        style.configure("Subheader.TLabel", font=("Helvetica", 10), foreground="#5f6368")
        style.configure("CardValue.TLabel", font=("Helvetica", 18, "bold"))
        style.configure("Muted.TLabel", foreground="#5f6368")

        shell = ttk.Frame(self, padding=(22, 18, 22, 18))
        shell.pack(fill="both", expand=True)
        header = ttk.Frame(shell)
        header.pack(fill="x", pady=(0, 14))
        self._label(header, "window_title", style="Header.TLabel").pack(side="left")
        self._label(header, "subtitle", style="Subheader.TLabel").pack(side="left", padx=(14, 0), pady=(6, 0))
        language_box = ttk.Frame(header)
        language_box.pack(side="right")
        self._label(language_box, "language").pack(side="left", padx=(0, 8))
        language_combo = ttk.Combobox(
            language_box,
            textvariable=self.language_choice,
            values=tuple(name for _code, name in self._locale_options),
            state="readonly",
            width=24,
        )
        language_combo.pack(side="left")
        language_combo.bind("<<ComboboxSelected>>", self._on_language_change)
        self.status_label = self._label(shell, "status_configured", style="Muted.TLabel")
        self.status_label.pack(anchor="w", pady=(0, 10))

        self.notebook = ttk.Notebook(shell)
        self.notebook.pack(fill="both", expand=True)
        self.overview_tab = ttk.Frame(self.notebook, padding=16)
        self.tasks_tab = ttk.Frame(self.notebook, padding=16)
        self.help_tab = ttk.Frame(self.notebook, padding=16)
        for tab, key in (
            (self.overview_tab, "overview"),
            (self.tasks_tab, "tasks_tab"),
            (self.help_tab, "help"),
        ):
            self.notebook.add(tab, text=text_for(key, self._language))
        self._build_overview()
        self._build_tasks()
        self._build_help()
        self._apply_language()

    def _build_overview(self) -> None:
        self._label(self.overview_tab, "overview_hint", style="Muted.TLabel").pack(anchor="w", pady=(0, 14))
        cards = ttk.Frame(self.overview_tab)
        cards.pack(fill="x", pady=(0, 16))
        self._overview_values: dict[str, ttk.Label] = {}
        for key in ("bots", "bindings", "schedules", "skill_root", "keyring"):
            card = ttk.LabelFrame(cards, padding=(12, 8))
            card.pack(side="left", fill="both", expand=True, padx=(0, 8))
            self._label(card, key).pack(anchor="w")
            value = ttk.Label(card, text="—", style="CardValue.TLabel")
            value.pack(anchor="w", pady=(5, 0))
            self._overview_values[key] = value

        panes = ttk.PanedWindow(self.overview_tab, orient="horizontal")
        panes.pack(fill="both", expand=True)
        bot_frame = self._frame(panes, "bot_list", padding=10)
        group_frame = self._frame(panes, "group_list", padding=10)
        panes.add(bot_frame, weight=1)
        panes.add(group_frame, weight=3)

        self.bot_tree = ttk.Treeview(bot_frame, columns=("bot", "groups", "token"), show="headings", selectmode="browse")
        self._bot_headings = {"bot": "bot_name", "groups": "groups_count", "token": "token_state"}
        for column, key in self._bot_headings.items():
            self.bot_tree.heading(column, text=text_for(key, self._language))
            self.bot_tree.column(column, width=140, anchor="w")
        self.bot_tree.pack(fill="both", expand=True)
        self.bot_tree.bind("<<TreeviewSelect>>", self._on_bot_overview_select)
        self.bot_tree.bind("<Double-1>", lambda _event: self._edit_bot_selected())

        self.group_tree = ttk.Treeview(
            group_frame, columns=("bot", "group", "chat", "profile", "schedule"), show="headings", selectmode="browse"
        )
        self._group_headings = {
            "bot": "bot_name",
            "group": "group_name",
            "chat": "chat_id",
            "profile": "profile",
            "schedule": "schedules",
        }
        for column, key in self._group_headings.items():
            self.group_tree.heading(column, text=text_for(key, self._language))
            self.group_tree.column(column, width=150, anchor="w")
        self.group_tree.column("chat", width=130)
        self.group_tree.column("schedule", width=210)
        self.group_tree.bind("<Double-1>", lambda _event: self._edit_group_selected())
        self._group_scroll = ttk.Scrollbar(group_frame, orient="vertical", command=self.group_tree.yview)
        self.group_tree.configure(yscrollcommand=self._group_scroll.set)
        self._group_scroll.pack(side="right", fill="y")
        self.group_tree.pack(side="left", fill="both", expand=True)

        actions = ttk.Frame(self.overview_tab)
        actions.pack(fill="x", pady=(14, 0))
        self._button(actions, "new_bot", self._new_bot).pack(side="left")
        self._button(actions, "edit_bot", self._edit_bot_selected).pack(side="left", padx=(8, 0))
        self._button(actions, "new_group", self._new_group).pack(side="left", padx=(18, 0))
        self._button(actions, "edit_group", self._edit_group_selected).pack(side="left", padx=(8, 0))
        self._button(actions, "refresh", self._refresh_all).pack(side="left")

    def _build_bots(self) -> None:
        details = self._frame(self.bots_tab, "bot_details", padding=14)
        details.pack(fill="x", pady=(0, 12))
        details.columnconfigure(1, weight=1)
        details.columnconfigure(3, weight=1)
        self._form_entry(details, 0, "bot_name", self.bot_edit_name, column=0)
        self._form_entry(details, 0, "token", self.bot_edit_token, secret=True, column=2)
        self._label(details, "skill_path").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=6)
        ttk.Entry(details, textvariable=self.bot_edit_skill_root).grid(row=1, column=1, columnspan=3, sticky="ew", pady=6)
        self._button(details, "browse", self._browse_skill).grid(row=1, column=4, padx=(8, 0))
        self.detected_label = self._label(details, "detected_skill", style="Muted.TLabel")
        self.detected_label.grid(row=2, column=0, sticky="w", padx=(0, 8), pady=(6, 0))
        ttk.Label(details, textvariable=self.skill_hint, style="Muted.TLabel").grid(
            row=2, column=1, columnspan=3, sticky="w", pady=(6, 0)
        )
        self._button(details, "use_detected", self._use_detected_skill).grid(row=2, column=4, padx=(8, 0))
        self._register_i18n(ttk.Checkbutton(details, variable=self.allow_plaintext), "plaintext").grid(
            row=3, column=0, columnspan=4, sticky="w", pady=(8, 0)
        )
        actions = ttk.Frame(self.bots_tab)
        actions.pack(fill="x", pady=(4, 0))
        self._button(actions, "save_bot", self._save_bot).pack(side="left")
        self._button(actions, "clear_token", self._clear_bot_token).pack(side="left", padx=8)
        self._button(actions, "edit_bot", self._edit_bot_selected).pack(side="left")

    def _build_groups(self) -> None:
        selectors = self._frame(self.groups_tab, "group_details", padding=14)
        selectors.pack(fill="x", pady=(0, 12))
        selectors.columnconfigure(1, weight=1)
        selectors.columnconfigure(3, weight=1)
        self._label(selectors, "group_selector").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=6)
        self.group_combo = ttk.Combobox(selectors, textvariable=self.group_choice, state="readonly")
        self.group_combo.grid(row=0, column=1, sticky="ew", padx=(0, 16), pady=6)
        self.group_combo.bind("<<ComboboxSelected>>", self._on_group_change)
        self._form_entry(selectors, 1, "group_name", self.group_name, column=0)
        self._form_entry(selectors, 1, "chat_id", self.chat_id, column=2)
        actions = ttk.Frame(self.groups_tab)
        actions.pack(fill="x", pady=(4, 0))
        self._button(actions, "save_group", self._save_group).pack(side="left")
        self._button(actions, "new_group", self._new_group).pack(side="left", padx=8)
        self._button(actions, "refresh", self._refresh_all).pack(side="left")

    def _build_tasks(self) -> None:
        self._label(self.tasks_tab, "task_list", style="Header.TLabel").pack(anchor="w", pady=(0, 12))
        toolbar = ttk.Frame(self.tasks_tab)
        toolbar.pack(fill="x", pady=(0, 10))
        self._button(toolbar, "new_task", self._new_task).pack(side="left")
        self._button(toolbar, "refresh", self._refresh_all).pack(side="left", padx=8)
        task_table = ttk.Frame(self.tasks_tab)
        task_table.pack(fill="both", expand=True)
        self.task_tree = ttk.Treeview(
            task_table,
            columns=("name", "bot", "group", "profile", "schedules", "status"),
            show="headings",
            selectmode="browse",
        )
        headings = {
            "name": "task_name",
            "bot": "bot_name",
            "group": "group_name",
            "profile": "profile",
            "schedules": "schedules",
            "status": "task_status",
        }
        self._task_headings = headings
        for column, key in headings.items():
            self.task_tree.heading(column, text=text_for(key, self._language))
            self.task_tree.column(column, width=150, anchor="w")
        self.task_tree.column("name", width=190)
        self._task_scroll = ttk.Scrollbar(task_table, orient="vertical", command=self.task_tree.yview)
        self._task_hscroll = ttk.Scrollbar(task_table, orient="horizontal", command=self.task_tree.xview)
        self.task_tree.configure(yscrollcommand=self._task_scroll.set, xscrollcommand=self._task_hscroll.set)
        self._task_scroll.pack(side="right", fill="y")
        self._task_hscroll.pack(side="bottom", fill="x")
        self.task_tree.pack(side="left", fill="both", expand=True)
        self.task_tree.bind("<Double-1>", lambda _event: self._edit_task_selected())
        actions = ttk.Frame(self.tasks_tab)
        actions.pack(fill="x", pady=(12, 0))
        self._button(actions, "edit_task", self._edit_task_selected).pack(side="left")
        self._button(actions, "test_task", self._test_task_selected).pack(side="left", padx=8)
        self._button(actions, "run_task", self._send_task_selected).pack(side="left")

    def _build_help(self) -> None:
        self._label(self.help_tab, "help_title", style="Header.TLabel").pack(anchor="w", pady=(0, 14))
        self.help_text = tk.Text(self.help_tab, wrap="word", height=20, relief="flat", borderwidth=0)
        self.help_text.pack(fill="both", expand=True)
        self.help_text.configure(state="disabled")

    def _apply_language(self) -> None:
        self.title(text_for("window_title", self._language))
        self.language_choice.set(self._locale_code_to_name.get(self._language, locale_display_name(TRANSLATIONS, self._language)))
        for key, widgets in self._i18n_widgets.items():
            value = text_for(key, self._language)
            for widget in widgets:
                try:
                    widget.configure(text=value)
                except tk.TclError:
                    pass
        for tab, key in (
            (self.overview_tab, "overview"),
            (self.tasks_tab, "tasks_tab"),
            (self.help_tab, "help"),
        ):
            self.notebook.tab(tab, text=text_for(key, self._language))
        for column, key in self._bot_headings.items():
            self.bot_tree.heading(column, text=text_for(key, self._language))
        for column, key in self._group_headings.items():
            self.group_tree.heading(column, text=text_for(key, self._language))
        for column, key in self._task_headings.items():
            self.task_tree.heading(column, text=text_for(key, self._language))
        self.help_text.configure(state="normal")
        self.help_text.delete("1.0", "end")
        self.help_text.insert("1.0", text_for("help_body", self._language))
        self.help_text.configure(state="disabled")
        self._refresh_all()
        self._apply_direction()

    def _apply_direction(self) -> None:
        rtl = is_rtl(self._language)
        justify = "right" if rtl else "left"
        anchor = "e" if rtl else "w"
        stack = [self]
        while stack:
            widget = stack.pop()
            stack.extend(widget.winfo_children())
            try:
                widget.configure(justify=justify)
            except tk.TclError:
                pass
            try:
                if isinstance(widget, (ttk.Label, ttk.LabelFrame)):
                    widget.configure(anchor=anchor)
            except tk.TclError:
                pass

    def _on_language_change(self, _event: Any = None) -> None:
        selected = self.language_choice.get()
        self._language = normalize_locale(self._locale_name_to_code.get(selected, selected))
        self.store.set_gui_language(self._language)
        self._apply_language()

    def _refresh_all(self) -> None:
        config = self.store.load()
        groups = list(config.groups)
        self._overview_values["bots"].configure(text=str(len(config.bots)))
        self._overview_values["bindings"].configure(text=str(len(groups)))
        self._overview_values["schedules"].configure(text=str(sum(len(task.schedules) for task in config.tasks)))
        self._overview_values["skill_root"].configure(
            text=text_for("ready", self._language) if config.skill_root else text_for("not_configured", self._language)
        )
        self._overview_values["keyring"].configure(text="SQLite")
        self.status_label.configure(text=text_for("status_configured" if groups else "status_empty", self._language))
        for tree in (self.bot_tree, self.group_tree):
            for item in tree.get_children():
                tree.delete(item)
        self._bot_keys.clear()
        for bot in config.bots:
            task_count = sum(1 for task in config.tasks if task.bot_name == bot.name)
            item = self.bot_tree.insert(
                "", "end", values=(bot.name, task_count, text_for("configured", self._language) if bot.token else text_for("missing", self._language))
            )
            self._bot_keys[item] = bot.name
        self._update_bot_selectors(config)
        self._render_group_tree(groups)
        for item in self.task_tree.get_children():
            self.task_tree.delete(item)
        self._task_keys.clear()
        groups_by_chat = {group.chat_id: group for group in config.groups}
        for task in config.tasks:
            group = groups_by_chat.get(task.chat_id)
            group_label = group.label if group else task.chat_id
            schedules = ", ".join(
                f"{item.schedule_time} — {period_label(item.period, self._language)}"
                for item in task.schedules
            ) or text_for("manual_only", self._language)
            item = self.task_tree.insert("", "end", values=(task.name, task.bot_name, group_label, task.profile, schedules, text_for("configured", self._language)))
            self._task_keys[item] = task.task_id
        self.skill_hint.set(self._skill_candidates[0] if self._skill_candidates else text_for("not_configured", self._language))

    def _render_group_tree(self, groups: list[GroupConfig]) -> None:
        for item in self.group_tree.get_children():
            self.group_tree.delete(item)
        self._group_keys.clear()
        for group in groups:
            label = group.label or group.chat_id
            task_count = sum(1 for task in self.store.load().tasks if task.chat_id == group.chat_id)
            item = self.group_tree.insert("", "end", values=("", label, group.chat_id, text_for("task_count", self._language, count=task_count), ""))
            self._group_keys[item] = ("", group.chat_id)

    def _on_bot_overview_select(self, _event: Any = None) -> None:
        selected = self.bot_tree.selection()
        self._overview_bot_filter = None
        self._render_group_tree(list(self.store.load().groups))

    def _update_bot_selectors(self, config: AppConfig) -> None:
        names = [bot.name for bot in config.bots]
        if hasattr(self, "task_bot_combo"):
            self.task_bot_combo.configure(values=names)
            if self.task_bot_choice.get() not in names:
                self.task_bot_choice.set(names[0] if names else "")
        groups = config.groups
        labels = [self._group_choice_label(group, groups) for group in groups]
        if hasattr(self, "group_combo"):
            self.group_combo.configure(values=labels)
            if self.group_choice.get() not in labels:
                self.group_choice.set(labels[0] if labels else "")
        task_groups = config.groups
        task_labels = [self._group_choice_label(group, task_groups) for group in task_groups]
        if hasattr(self, "task_group_combo"):
            self.task_group_combo.configure(values=task_labels)
            if self.task_group_choice.get() not in task_labels:
                self.task_group_choice.set(task_labels[0] if task_labels else "")

    @staticmethod
    def _group_choice_label(group: GroupConfig, siblings: tuple[GroupConfig, ...] | list[GroupConfig]) -> str:
        base = group.label or group.chat_id
        if sum(1 for item in siblings if (item.label or item.chat_id) == base) > 1:
            return f"{base} ({group.chat_id})"
        return base

    def _selected_bot_name(self) -> str | None:
        selected = self.bot_tree.selection()
        return self._bot_keys.get(selected[0]) if selected else None

    def _selected_group_key(self) -> tuple[str, str] | None:
        selected = self.group_tree.selection()
        return self._group_keys.get(selected[0]) if selected else None

    def _new_bot(self) -> None:
        BotDialog(self, self.store, language=self._language, candidates=self._skill_candidates)
        self._refresh_all()

    def _edit_bot_selected(self) -> None:
        name = self._selected_bot_name()
        if not name:
            messagebox.showinfo(text_for("bots_tab", self._language), text_for("select_binding", self._language))
            return
        bot = next(bot for bot in self.store.load().bots if bot.name == name)
        BotDialog(self, self.store, language=self._language, bot=bot, candidates=self._skill_candidates)
        self._refresh_all()

    def _save_bot(self) -> bool:
        try:
            name = self.bot_edit_name.get().strip()
            if not name:
                raise ValueError(text_for("bot_missing", self._language))
            current = self.store.load()
            if name != self._editing_bot_name and any(bot.name == name for bot in current.bots):
                raise ValueError(f"duplicate bot name: {name}")
            bots: list[BotConfig] = []
            replaced = False
            for bot in current.bots:
                if bot.name == self._editing_bot_name:
                    bots.append(BotConfig(name, self.bot_edit_token.get(), bot.groups))
                    replaced = True
                else:
                    bots.append(bot)
            if not replaced:
                bots.append(BotConfig(name, self.bot_edit_token.get(), ()))
            old_name = self._editing_bot_name
            tasks = [
                PushTaskConfig(
                    task_id=task.task_id,
                    name=task.name,
                    bot_name=name if old_name and task.bot_name == old_name else task.bot_name,
                    chat_id=task.chat_id,
                    profile=task.profile,
                    query=task.query,
                    schedules=task.schedules,
                )
                for task in current.tasks
            ]
            self.store.update(AppConfig(skill_root=self.bot_edit_skill_root.get(), bots=tuple(bots), tasks=tuple(tasks)), allow_plaintext=self.allow_plaintext.get())
            self._editing_bot_name = name
            self.group_bot_choice.set(name)
        except Exception as exc:
            messagebox.showerror(text_for("configuration_error", self._language), str(exc))
            return False
        self._refresh_all()
        messagebox.showinfo(text_for("success", self._language), text_for("saved", self._language))
        return True

    def _clear_bot_token(self) -> None:
        name = self.bot_edit_name.get().strip()
        if not name:
            return
        if messagebox.askyesno(text_for("clear_token", self._language), text_for("clear_confirm", self._language)):
            self.store.clear_bot_token(name)
            self.bot_edit_token.set("")
            self._refresh_all()

    def _new_group(self) -> None:
        GroupDialog(self, self.store, language=self._language)
        self._refresh_all()

    def _edit_group_selected(self) -> None:
        key = self._selected_group_key()
        if not key:
            messagebox.showinfo(text_for("groups_tab", self._language), text_for("select_binding", self._language))
            return
        _bot_name, chat_id = key
        group = next(group for group in self.store.load().groups if group.chat_id == chat_id)
        GroupDialog(self, self.store, language=self._language, group=group)
        self._refresh_all()

    def _load_group(self, group: GroupConfig) -> None:
        self._editing_group_key = ("", group.chat_id)
        siblings = self.store.load().groups
        self.group_choice.set(self._group_choice_label(group, siblings))
        self.group_name.set(group.label)
        self.chat_id.set(group.chat_id)
        self.notebook.select(self.groups_tab)

    def _on_group_bot_change(self, _event: Any = None) -> None:
        config = self.store.load()
        self._update_bot_selectors(config)
        self._editing_group_key = None
        self._new_group()

    def _on_group_change(self, _event: Any = None) -> None:
        label = self.group_choice.get()
        groups = self.store.load().groups
        for group in groups:
            if self._group_choice_label(group, groups) == label:
                self._load_group(group)
                return

    def _add_schedule(self) -> None:
        try:
            hour = int(self.schedule_hour.get())
            minute = int(self.schedule_minute.get())
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                raise ValueError
        except ValueError:
            messagebox.showerror(text_for("configuration_error", self._language), text_for("schedule_error", self._language))
            return
        periods = [period for period, variable in self.period_vars.items() if variable.get()]
        if not periods:
            messagebox.showerror(text_for("configuration_error", self._language), text_for("period_error", self._language))
            return
        time_value = f"{hour:02d}:{minute:02d}"
        self._schedule_entries = list(merge_schedule_entries(self._schedule_entries, time_value, periods))
        self._render_schedule_list()

    def _remove_schedule(self) -> None:
        selected = list(self.schedule_listbox.curselection())
        for index in reversed(selected):
            del self._schedule_entries[index]
        self._render_schedule_list()

    def _render_schedule_list(self) -> None:
        self.schedule_listbox.delete(0, "end")
        for schedule_time, period in self._schedule_entries:
            self.schedule_listbox.insert("end", f"{schedule_time} — {period_label(period, self._language)}")

    def _browse_skill(self) -> None:
        selected = filedialog.askdirectory(title=text_for("skill_path", self._language))
        if selected:
            self.bot_edit_skill_root.set(selected)

    def _use_detected_skill(self) -> None:
        if self._skill_candidates:
            self.bot_edit_skill_root.set(self._skill_candidates[0])

    def _scope(self) -> dict[str, object]:
        if self.all_confirmed.get():
            return {"mode": "all", "all_confirmed": True}
        try:
            values = [int(item.strip()) for item in self.uids.get().split(",") if item.strip()]
        except ValueError as exc:
            raise ValueError(text_for("scope_error", self._language)) from exc
        if not values:
            raise ValueError(text_for("scope_error", self._language))
        return {"mode": "uids", "uids": values}

    def _group_from_form(self) -> GroupConfig:
        if not self.chat_id.get().strip():
            raise ValueError(text_for("group_missing", self._language))
        return GroupConfig(
            chat_id=self.chat_id.get(),
            label=self.group_name.get(),
        )

    def _save_group(self) -> bool:
        try:
            group = self._group_from_form()
            current = self.store.load()
            old_chat_id = self._editing_group_key[1] if self._editing_group_key else None
            groups = [item for item in current.groups if item.chat_id not in {old_chat_id, group.chat_id}]
            groups.append(group)
            self.store.update(
                current.with_groups(tuple(groups)).with_tasks(
                    remap_task_chat_id(current.tasks, old_chat_id, group.chat_id)
                ),
                allow_plaintext=True,
            )
            self._editing_group_key = ("", group.chat_id)
            self.group_choice.set(group.label or group.chat_id)
        except Exception as exc:
            messagebox.showerror(text_for("configuration_error", self._language), str(exc))
            return False
        self._refresh_all()
        messagebox.showinfo(text_for("success", self._language), text_for("saved", self._language))
        return True

    def _selected_bot(self, bot_name: str | None = None) -> BotConfig:
        bot = next((item for item in self.store.load().bots if item.name == (bot_name or self.group_bot_choice.get())), None)
        if bot is None:
            raise ValueError(text_for("bot_missing", self._language))
        return bot

    def _test_group(self) -> None:
        try:
            if not self._save_group():
                return
            bot = self._selected_bot()
            TelegramSender().send(bot.token, self.chat_id.get(), text_for("test_message", self._language))
        except Exception as exc:
            messagebox.showerror(text_for("telegram_test_failed", self._language), str(exc))
        else:
            messagebox.showinfo(text_for("success", self._language), text_for("telegram_sent", self._language))

    def _send_group(self) -> None:
        try:
            if not self._save_group():
                return
            config = self.store.load()
            bot = next(bot for bot in config.bots if bot.name == self.group_bot_choice.get())
            group = next(group for group in bot.groups if group.chat_id == self.chat_id.get())
            service = RebateService(
                config,
                PartnerClient(config.skill_root),
                TelegramSender(),
                DeliveryLedger(self.store.root / "deliveries.sqlite3"),
            )
            result = service.send_for_date(
                datetime.now(timezone.utc).date() - timedelta(days=1),
                force=True,
                bots=(BotConfig(bot.name, bot.token, (group,)),),
            )
            if not result.ok:
                raise RuntimeError("; ".join(result.error_messages))
        except Exception as exc:
            messagebox.showerror(text_for("send_failed", self._language), str(exc))
        else:
            messagebox.showinfo(text_for("success", self._language), text_for("telegram_sent", self._language))

    def _new_task(self) -> None:
        TaskDialog(self, self.store, language=self._language)
        self._refresh_all()

    def _on_task_bot_change(self, _event: Any = None) -> None:
        self._update_bot_selectors(self.store.load())
        self._editing_task_id = None

    def _on_task_group_change(self, _event: Any = None) -> None:
        self._editing_task_id = None

    def _on_task_change(self, _event: Any = None) -> None:
        name = self.task_choice.get()
        task = next((task for task in self.store.load().tasks if task.name == name), None)
        if task is None:
            return
        TaskDialog(self, self.store, language=self._language, task=task)
        self._refresh_all()

    def _selected_task_id(self) -> str | None:
        selected = self.task_tree.selection()
        return self._task_keys.get(selected[0]) if selected else None

    def _edit_task_selected(self) -> None:
        task_id = self._selected_task_id()
        if not task_id:
            messagebox.showinfo(text_for("tasks_tab", self._language), text_for("select_binding", self._language))
            return
        task = next((task for task in self.store.load().tasks if task.task_id == task_id), None)
        if task is not None:
            TaskDialog(self, self.store, language=self._language, task=task)
            self._refresh_all()

    def _test_task_selected(self) -> None:
        task_id = self._selected_task_id()
        if not task_id:
            messagebox.showinfo(text_for("tasks_tab", self._language), text_for("select_binding", self._language))
            return
        task = next((task for task in self.store.load().tasks if task.task_id == task_id), None)
        if task is None:
            return
        bot = next((bot for bot in self.store.load().bots if bot.name == task.bot_name), None)
        if bot is None:
            messagebox.showerror(text_for("configuration_error", self._language), text_for("bot_missing", self._language))
            return
        try:
            TelegramSender().send(bot.token, task.chat_id, text_for("test_message", self._language))
        except Exception as exc:
            messagebox.showerror(text_for("telegram_test_failed", self._language), str(exc))
        else:
            messagebox.showinfo(text_for("success", self._language), text_for("telegram_sent", self._language))

    def _send_task_selected(self) -> None:
        task_id = self._selected_task_id()
        if not task_id:
            messagebox.showinfo(text_for("tasks_tab", self._language), text_for("select_binding", self._language))
            return
        try:
            config = self.store.load()
            service = RebateService(config, PartnerClient(config.skill_root), TelegramSender(), DeliveryLedger(self.store.root / "deliveries.sqlite3"))
            result = service.send_task_for_date(
                task_id,
                datetime.now(timezone.utc).date() - timedelta(days=1),
                force=True,
            )
            if not result.ok:
                raise RuntimeError("; ".join(result.error_messages))
        except Exception as exc:
            messagebox.showerror(text_for("send_failed", self._language), str(exc))
        else:
            messagebox.showinfo(text_for("success", self._language), text_for("telegram_sent", self._language))

    def _load_task(self, task: PushTaskConfig) -> None:
        self._editing_task_id = task.task_id
        self.task_choice.set(task.name)
        self.task_name.set(task.name)
        self.task_bot_choice.set(task.bot_name)
        config = self.store.load()
        group = next((group for group in config.groups if group.chat_id == task.chat_id), None)
        if group is not None:
            self.task_group_choice.set(self._group_choice_label(group, config.groups))
        self.profile.set(task.profile)
        self.coin.set(task.query.coin)
        self.product_types.set(", ".join(task.query.product_types))
        self.uids.set(", ".join(str(item) for item in task.query.scope.get("uids", ())))
        self.all_confirmed.set(task.query.scope.get("mode") == "all" and task.query.scope.get("all_confirmed") is True)
        self.formula.set(task.query.formula)
        self._schedule_entries = [(item.schedule_time, item.period) for item in task.schedules if item.enabled]
        self._render_schedule_list()
        self.notebook.select(self.tasks_tab)

    def _selected_task_group(self) -> tuple[BotConfig, GroupConfig]:
        config = self.store.load()
        bot = next((bot for bot in config.bots if bot.name == self.task_bot_choice.get()), None)
        if bot is None:
            raise ValueError(text_for("bot_missing", self._language))
        for group in config.groups:
            if self._group_choice_label(group, config.groups) == self.task_group_choice.get():
                return bot, group
        raise ValueError(text_for("group_missing", self._language))

    def _save_task(self) -> bool:
        try:
            bot, group = self._selected_task_group()
            if not self.task_name.get().strip() or not self.profile.get().strip():
                raise ValueError(text_for("group_missing", self._language))
            task_id = self._editing_task_id or uuid.uuid4().hex
            task = PushTaskConfig(
                task_id=task_id,
                name=self.task_name.get().strip(),
                bot_name=bot.name,
                chat_id=group.chat_id,
                profile=self.profile.get(),
                query=QueryConfig(
                    coin=self.coin.get(),
                    product_types=tuple(item.strip().upper() for item in self.product_types.get().split(",") if item.strip()),
                    scope=self._scope(),
                    formula=self.formula.get(),
                ),
                schedules=tuple(ScheduleConfig(schedule_time, period) for schedule_time, period in self._schedule_entries),
            )
            current = self.store.load()
            tasks = [item for item in current.tasks if item.task_id != task_id]
            tasks.append(task)
            self.store.update(current.with_tasks(tuple(tasks)), allow_plaintext=True)
            self._editing_task_id = task_id
            self.task_choice.set(task.name)
        except Exception as exc:
            messagebox.showerror(text_for("configuration_error", self._language), str(exc))
            return False
        self._refresh_all()
        messagebox.showinfo(text_for("success", self._language), text_for("saved", self._language))
        return True

    def _test_task(self) -> None:
        try:
            if not self._save_task():
                return
            bot, group = self._selected_task_group()
            TelegramSender().send(bot.token, group.chat_id, text_for("test_message", self._language))
        except Exception as exc:
            messagebox.showerror(text_for("telegram_test_failed", self._language), str(exc))
        else:
            messagebox.showinfo(text_for("success", self._language), text_for("telegram_sent", self._language))

    def _send_task(self) -> None:
        try:
            if not self._save_task():
                return
            task = next(task for task in self.store.load().tasks if task.task_id == self._editing_task_id)
            config = self.store.load()
            service = RebateService(
                config,
                PartnerClient(config.skill_root),
                TelegramSender(),
                DeliveryLedger(self.store.root / "deliveries.sqlite3"),
            )
            result = service.send_task_for_date(
                task.task_id,
                datetime.now(timezone.utc).date() - timedelta(days=1),
                force=True,
            )
            if not result.ok:
                raise RuntimeError("; ".join(result.error_messages))
        except Exception as exc:
            messagebox.showerror(text_for("send_failed", self._language), str(exc))
        else:
            messagebox.showinfo(text_for("success", self._language), text_for("telegram_sent", self._language))


class _ModalDialog(tk.Toplevel):
    def __init__(self, parent: ConfigWindow, *, title: str, language: str) -> None:
        super().__init__(parent)
        self.parent_window = parent
        self.language = language
        self.title(title)
        self.transient(parent)
        self.grab_set()
        self.resizable(True, True)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.result = False
        self._apply_direction()

    def _apply_direction(self) -> None:
        if not is_rtl(self.language):
            return
        stack = [self]
        while stack:
            widget = stack.pop()
            stack.extend(widget.winfo_children())
            try:
                widget.configure(justify="right")
            except tk.TclError:
                pass
            try:
                if isinstance(widget, (ttk.Label, ttk.LabelFrame)):
                    widget.configure(anchor="e")
            except tk.TclError:
                pass

    def _row(self, frame: Any, row: int, label: str, variable: tk.StringVar, *, secret: bool = False) -> None:
        ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", padx=(0, 10), pady=6)
        ttk.Entry(frame, textvariable=variable, show="•" if secret else "").grid(row=row, column=1, sticky="ew", pady=6)


class DatePicker(ttk.Frame):
    def __init__(self, parent: Any, variable: tk.StringVar, *, language: str) -> None:
        super().__init__(parent)
        self.variable = variable
        self.language = language
        self._month = date.today().replace(day=1)
        ttk.Entry(self, textvariable=self.variable, width=12, state="readonly").pack(side="left")
        ttk.Button(self, text=text_for("select_date", language), command=self._open).pack(side="left", padx=(6, 0))

    def _open(self) -> None:
        popup = tk.Toplevel(self)
        popup.title(text_for("date_picker", self.language))
        popup.transient(self.winfo_toplevel())
        popup.grab_set()
        header = ttk.Frame(popup, padding=10)
        header.pack(fill="x")
        month_label = ttk.Label(header)
        month_label.pack(side="left", expand=True)
        body = ttk.Frame(popup, padding=(10, 0, 10, 10))
        body.pack()

        def render() -> None:
            for child in body.winfo_children():
                child.destroy()
            month_label.configure(text=self._month.strftime("%Y-%m"))
            ttk.Button(header, text="‹", width=3, command=lambda: move(-1)).place(x=10, y=8)
            ttk.Button(header, text="›", width=3, command=lambda: move(1)).place(relx=1.0, x=-40, y=8, anchor="ne")
            names = tuple(text_for("weekday_names", self.language).split(","))
            for column, name in enumerate(names):
                ttk.Label(body, text=name, width=4, anchor="center").grid(row=0, column=column, padx=1, pady=2)
            first_weekday, days_in_month = calendar.monthrange(self._month.year, self._month.month)
            for day in range(1, days_in_month + 1):
                index = first_weekday + day - 1
                row, column = divmod(index, 7)
                ttk.Button(body, text=str(day), width=4, command=lambda d=day: choose(d)).grid(row=row + 1, column=column, padx=1, pady=1)

        def move(delta: int) -> None:
            month_index = self._month.year * 12 + self._month.month - 1 + delta
            year, month = divmod(month_index, 12)
            self._month = date(year, month + 1, 1)
            render()

        def choose(day: int) -> None:
            self.variable.set(date(self._month.year, self._month.month, day).isoformat())
            popup.destroy()

        render()
        popup.wait_window()


class TimezonePicker(ttk.Frame):
    """Single editable timezone field with a non-focus-stealing popdown."""

    def __init__(
        self,
        parent: Any,
        variable: tk.StringVar,
        values: tuple[str, ...],
        *,
        width: int = 24,
    ) -> None:
        super().__init__(parent)
        self.variable = variable
        self.values = tuple(values)
        topbar = ttk.Frame(self)
        topbar.pack(fill="x", expand=True)
        self.entry = ttk.Entry(topbar, textvariable=self.variable, width=width)
        self.entry.pack(side="left", fill="x", expand=True)
        self.button = ttk.Button(topbar, text="▾", width=2, command=self._toggle)
        self.button.pack(side="right")
        self.listbox = tk.Listbox(self, height=0, exportselection=False, activestyle="dotbox")
        self.listbox.bind("<ButtonRelease-1>", self._choose)
        self.listbox.bind("<Return>", self._choose)
        self.listbox.bind("<Escape>", lambda _event: self._hide())
        self.entry.bind("<KeyRelease>", self._on_query)
        self.entry.bind("<Down>", self._focus_list)
        self.entry.bind("<Escape>", lambda _event: self._hide())

    def _on_query(self, _event: Any = None) -> None:
        self._show(filter_timezones(self.values, self.variable.get()))

    def _toggle(self) -> None:
        if not self.listbox.winfo_ismapped():
            self._show(filter_timezones(self.values, self.variable.get()))
        else:
            self._hide()
        self.entry.focus_set()

    def _show(self, matches: tuple[str, ...]) -> None:
        self.listbox.delete(0, "end")
        for value in matches:
            self.listbox.insert("end", value)
        if matches:
            self.listbox.selection_clear(0, "end")
            self.listbox.selection_set(0)
            self.listbox.activate(0)
            self.listbox.configure(height=min(len(matches), 10))
            self.listbox.pack(fill="x", pady=(2, 0))
        else:
            self.listbox.pack_forget()

    def _focus_list(self, _event: Any = None) -> str:
        if self.listbox.winfo_ismapped():
            self.listbox.focus_set()
            return "break"
        return ""

    def _choose(self, event: Any = None) -> str:
        if event is not None and hasattr(event, "y"):
            index = self.listbox.nearest(event.y)
        else:
            selected = self.listbox.curselection()
            index = selected[0] if selected else -1
        if index >= 0:
            self.variable.set(self.listbox.get(index))
        self._hide()
        self.entry.focus_set()
        return "break"

    def _hide(self) -> None:
        self.listbox.pack_forget()


class BotDialog(_ModalDialog):
    def __init__(self, parent: ConfigWindow, store: ConfigStore, *, language: str, bot: BotConfig | None = None, candidates: tuple[str, ...] = ()) -> None:
        super().__init__(parent, title=text_for("bot_details", language), language=language)
        self.store = store
        self.bot = bot
        self.candidates = candidates
        self.name = tk.StringVar(value=bot.name if bot else "")
        self.token = tk.StringVar(value=bot.token if bot else "")
        self.skill_root = tk.StringVar(value=store.load().skill_root or (candidates[0] if candidates else ""))
        frame = ttk.Frame(self, padding=18)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(1, weight=1)
        self._row(frame, 0, text_for("bot_name", language), self.name)
        self._row(frame, 1, text_for("token", language), self.token, secret=True)
        self._row(frame, 2, text_for("skill_path", language), self.skill_root)
        ttk.Button(frame, text=text_for("save_bot", language), command=self._save).grid(row=4, column=0, sticky="e", pady=(14, 0))
        ttk.Button(frame, text=text_for("cancel", language), command=self.destroy).grid(row=4, column=1, sticky="e", pady=(14, 0))
        self._apply_direction()
        self.geometry("+%d+%d" % (parent.winfo_rootx() + 120, parent.winfo_rooty() + 100))
        self.wait_window()

    def _save(self) -> None:
        try:
            name = self.name.get().strip()
            if not name:
                raise ValueError(text_for("bot_missing", self.language))
            current = self.store.load()
            old_name = self.bot.name if self.bot else None
            if name != old_name and any(item.name == name for item in current.bots):
                raise ValueError(f"duplicate bot name: {name}")
            bots = [BotConfig(name, self.token.get(), item.groups) if item.name == old_name else item for item in current.bots]
            if old_name is None:
                bots.append(BotConfig(name, self.token.get(), ()))
            tasks = tuple(
                PushTaskConfig(task_id=task.task_id, name=task.name, bot_name=name if old_name and task.bot_name == old_name else task.bot_name, chat_id=task.chat_id, profile=task.profile, query=task.query, schedules=task.schedules, language=task.language)
                for task in current.tasks
            )
            self.store.update(AppConfig(skill_root=self.skill_root.get(), bots=tuple(bots), groups=current.groups, tasks=tasks), allow_plaintext=True)
        except Exception as exc:
            messagebox.showerror(text_for("configuration_error", self.language), str(exc), parent=self)
            return
        self.result = True
        self.destroy()


class GroupDialog(_ModalDialog):
    def __init__(self, parent: ConfigWindow, store: ConfigStore, *, language: str, group: GroupConfig | None = None) -> None:
        super().__init__(parent, title=text_for("group_details", language), language=language)
        self.store = store
        self.group = group
        self.name = tk.StringVar(value=group.label if group else "")
        self.chat_id = tk.StringVar(value=group.chat_id if group else "")
        frame = ttk.Frame(self, padding=18)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(1, weight=1)
        self._row(frame, 0, text_for("group_name", language), self.name)
        self._row(frame, 1, text_for("chat_id", language), self.chat_id)
        ttk.Button(frame, text=text_for("save_group", language), command=self._save).grid(row=2, column=0, sticky="e", pady=(14, 0))
        ttk.Button(frame, text=text_for("cancel", language), command=self.destroy).grid(row=2, column=1, sticky="e", pady=(14, 0))
        self._apply_direction()
        self.geometry("+%d+%d" % (parent.winfo_rootx() + 150, parent.winfo_rooty() + 120))
        self.wait_window()

    def _save(self) -> None:
        try:
            chat_id = self.chat_id.get().strip()
            if not chat_id:
                raise ValueError(text_for("group_missing", self.language))
            new_group = GroupConfig(chat_id=chat_id, label=self.name.get())
            current = self.store.load()
            old_chat = self.group.chat_id if self.group else None
            groups = [item for item in current.groups if item.chat_id not in {old_chat, chat_id}]
            groups.append(new_group)
            self.store.update(
                current.with_groups(tuple(groups)).with_tasks(
                    remap_task_chat_id(current.tasks, old_chat, chat_id)
                ),
                allow_plaintext=True,
            )
        except Exception as exc:
            messagebox.showerror(text_for("configuration_error", self.language), str(exc), parent=self)
            return
        self.result = True
        self.destroy()


class TaskDialog(_ModalDialog):
    def __init__(self, parent: ConfigWindow, store: ConfigStore, *, language: str, task: PushTaskConfig | None = None) -> None:
        super().__init__(parent, title=text_for("task_details", language), language=language)
        self.store = store
        self.task = task
        config = store.load()
        self.name = tk.StringVar(value=task.name if task else "")
        self.bot_name = tk.StringVar(value=task.bot_name if task else (config.bots[0].name if config.bots else ""))
        self.group_name = tk.StringVar(value="")
        self.profile = tk.StringVar(value=task.profile if task else "")
        self.task_language = tk.StringVar(value=task.language if task else language)
        self._locale_options = locale_options(TRANSLATIONS)
        self._locale_code_to_name = dict(self._locale_options)
        self._locale_name_to_code = {name: code for code, name in self._locale_options}
        self.task_language_display = tk.StringVar(
            value=self._locale_code_to_name.get(
                self.task_language.get(), locale_display_name(TRANSLATIONS, self.task_language.get())
            )
        )
        self.profile_values = tuple(discover_saved_profiles())
        if self.profile.get() and self.profile.get() not in self.profile_values:
            self.profile_values = tuple(dict.fromkeys(self.profile_values + (self.profile.get(),)))
        query = task.query if task else QueryConfig()
        self.coin = tk.StringVar(value=query.coin)
        self.product_values = tuple(discover_commission_filters(config.skill_root or None).get("products", ()))
        self.coin_values = tuple(discover_commission_filters(config.skill_root or None).get("coins", ()))
        self.product_values = tuple(dict.fromkeys(self.product_values + tuple(query.product_types)))
        self.coin_values = tuple(dict.fromkeys(self.coin_values + (query.coin,)))
        self.products = tk.StringVar(value=", ".join(query.product_types))
        self.product_vars = {product: tk.BooleanVar(value=product in query.product_types) for product in self.product_values}
        self.uid_search = tk.StringVar()
        self.available_uids: list[int] = [int(item) for item in query.scope.get("uids", ())]
        self.selected_uids: set[int] = set(self.available_uids)
        self.all_confirmed = tk.BooleanVar(value=query.scope.get("mode") == "all" and query.scope.get("all_confirmed") is True)
        self.formula = tk.StringVar(value=query.formula)
        self.query_windows = list(dict.fromkeys(item.period for item in (task.schedules if task else ()))) or ["1d"]
        self.push_times = list(dict.fromkeys(item.schedule_time for item in (task.schedules if task else ()))) or ["09:00"]
        self._initial_push_time = self.push_times[0]
        self.task_timezone = tk.StringVar(
            value=next((item.timezone for item in (task.schedules if task else ())), "UTC")
        )
        self.window_days = tk.StringVar(value="")
        self.window_vars = {period: tk.BooleanVar(value=period in self.query_windows) for period in ("1d", "1w", "1m", "1y")}
        custom_days = [period[:-1] for period in self.query_windows if period not in self.window_vars]
        self.custom_days_enabled = tk.BooleanVar(value=bool(custom_days))
        self.window_days.set(custom_days[0] if custom_days else "")
        custom_starts = [item.start_date for item in (task.schedules if task else ()) if item.start_date]
        self.window_start_date = tk.StringVar(value=custom_starts[0] if custom_starts else "")
        initial_hour, initial_minute = self._initial_push_time.split(":", 1)
        self.push_hour = tk.StringVar(value=initial_hour)
        self.push_minute = tk.StringVar(value=initial_minute)
        viewport = ttk.Frame(self)
        viewport.pack(fill="both", expand=True)
        canvas = tk.Canvas(viewport, highlightthickness=0, borderwidth=0)
        vertical_scroll = ttk.Scrollbar(viewport, orient="vertical", command=canvas.yview)
        horizontal_scroll = ttk.Scrollbar(viewport, orient="horizontal", command=canvas.xview)
        canvas.configure(yscrollcommand=vertical_scroll.set, xscrollcommand=horizontal_scroll.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        vertical_scroll.grid(row=0, column=1, sticky="ns")
        horizontal_scroll.grid(row=1, column=0, sticky="ew")
        viewport.rowconfigure(0, weight=1)
        viewport.columnconfigure(0, weight=1)
        frame = ttk.Frame(canvas, padding=18)
        frame_window = canvas.create_window((0, 0), window=frame, anchor="nw")

        def update_scroll_region(_event: Any = None) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        def fit_form_width(event: Any) -> None:
            requested = frame.winfo_reqwidth()
            canvas.itemconfigure(frame_window, width=max(event.width, requested))

        frame.bind("<Configure>", update_scroll_region)
        canvas.bind("<Configure>", fit_form_width)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(3, weight=1)
        self._row(frame, 0, text_for("task_name", language), self.name)
        ttk.Label(frame, text=text_for("bot_selector", language)).grid(row=1, column=0, sticky="w", padx=(0, 10), pady=6)
        self.bot_combo = ttk.Combobox(frame, textvariable=self.bot_name, values=[bot.name for bot in config.bots], state="readonly")
        self.bot_combo.grid(row=1, column=1, sticky="ew", padx=(0, 14), pady=6)
        self._row(frame, 2, text_for("group_selector", language), self.group_name)
        self.group_combo = ttk.Combobox(frame, textvariable=self.group_name, state="readonly")
        self.group_combo.grid(row=2, column=1, sticky="ew", pady=6)
        self.bot_combo.bind("<<ComboboxSelected>>", lambda _event: self._refresh_groups())
        self._refresh_groups()
        ttk.Label(frame, text=text_for("profile", language)).grid(row=3, column=0, sticky="w", padx=(0, 10), pady=6)
        self.profile_combo = ttk.Combobox(frame, textvariable=self.profile, values=self.profile_values, state="readonly")
        self.profile_combo.grid(row=3, column=1, sticky="ew", pady=6)
        ttk.Label(frame, text=text_for("language", language)).grid(row=3, column=2, sticky="w", padx=(10, 4), pady=6)
        self.task_language_combo = ttk.Combobox(
            frame,
            textvariable=self.task_language_display,
            values=tuple(name for _code, name in self._locale_options),
            state="readonly",
            width=24,
        )
        self.task_language_combo.grid(row=3, column=3, sticky="e", pady=6)
        self.task_language_combo.bind("<<ComboboxSelected>>", self._on_task_language_change)
        ttk.Label(frame, text=text_for("coin", language)).grid(row=4, column=0, sticky="w", padx=(0, 10), pady=6)
        self.coin_combo = ttk.Combobox(frame, textvariable=self.coin, values=self.coin_values, state="normal")
        self.coin_combo.grid(row=4, column=1, sticky="ew", pady=6)
        self.coin_combo.bind("<KeyRelease>", self._filter_coins)
        ttk.Label(frame, text=text_for("products", language)).grid(row=5, column=0, sticky="w", padx=(0, 10), pady=6)
        product_frame = ttk.Frame(frame)
        product_frame.grid(row=5, column=1, columnspan=3, sticky="ew", pady=6)
        for product in self.product_values:
            label = text_for(PRODUCT_KEYS.get(product, "products"), language) if product in PRODUCT_KEYS else product
            ttk.Checkbutton(product_frame, text=label, variable=self.product_vars[product]).pack(anchor="w")
        ttk.Checkbutton(frame, text=text_for("all_scope", language), variable=self.all_confirmed, command=self._toggle_uid_controls).grid(row=6, column=0, columnspan=4, sticky="w", pady=6)
        ttk.Label(frame, text=text_for("uids", language)).grid(row=7, column=0, sticky="w", padx=(0, 10), pady=6)
        uid_bar = ttk.Frame(frame)
        uid_bar.grid(row=7, column=1, columnspan=3, sticky="ew", pady=6)
        uid_bar.columnconfigure(0, weight=1)
        self.uid_entry = ttk.Entry(uid_bar, textvariable=self.uid_search)
        self.uid_entry.grid(row=0, column=0, sticky="ew")
        self.uid_entry.bind("<KeyRelease>", lambda _event: self._render_uids())
        self.uid_load_button = ttk.Button(uid_bar, text=text_for("load_uids", language), command=self._load_uids)
        self.uid_load_button.grid(row=0, column=1, padx=(8, 0))
        self.uid_list = tk.Listbox(frame, selectmode="multiple", height=5, exportselection=False)
        self.uid_list.grid(row=8, column=1, columnspan=3, sticky="ew", pady=(0, 6))
        self.uid_list.bind("<<ListboxSelect>>", self._capture_uid_selection)
        self._render_uids()
        self._toggle_uid_controls()
        ttk.Label(frame, text=text_for("formula", language)).grid(row=9, column=0, sticky="w", padx=(0, 10), pady=6)
        self.formula_labels = {
            "commission_minus_subaffiliate_commission": text_for("formula_option_subaffiliate", language),
            "commission": text_for("formula_option_commission", language),
        }
        self.formula_display = tk.StringVar(value=self.formula_labels.get(self.formula.get(), self.formula.get()))
        formula_combo = ttk.Combobox(
            frame,
            textvariable=self.formula_display,
            values=tuple(self.formula_labels.values()),
            state="readonly",
        )
        formula_combo.grid(row=9, column=1, columnspan=3, sticky="ew", pady=6)
        formula_combo.bind(
            "<<ComboboxSelected>>",
            lambda _event: self.formula.set(
                next((key for key, label in self.formula_labels.items() if label == self.formula_display.get()), self.formula.get())
            ),
        )
        ttk.Label(frame, text=text_for("query_window", language)).grid(row=10, column=0, sticky="w", padx=(0, 10), pady=6)
        window_frame = ttk.Frame(frame)
        window_frame.grid(row=10, column=1, columnspan=3, sticky="ew", pady=6)
        for period in ("1d", "1w", "1m", "1y"):
            ttk.Checkbutton(window_frame, text=text_for(WINDOW_KEYS[period], language), variable=self.window_vars[period]).pack(anchor="w")
        custom_window = ttk.Frame(window_frame)
        custom_window.pack(anchor="w", pady=(4, 0))
        ttk.Checkbutton(custom_window, text=text_for("custom_window", language), variable=self.custom_days_enabled).pack(side="left")
        ttk.Entry(custom_window, textvariable=self.window_days, width=8).pack(side="left", padx=6)
        ttk.Label(custom_window, text=text_for("start_date_utc", language)).pack(side="left", padx=(10, 4))
        DatePicker(custom_window, self.window_start_date, language=language).pack(side="left")
        ttk.Label(frame, text=text_for("push_time", language)).grid(row=12, column=0, sticky="w", padx=(0, 10), pady=6)
        time_bar = ttk.Frame(frame)
        time_bar.grid(row=12, column=1, columnspan=3, sticky="ew", pady=6)
        ttk.Spinbox(time_bar, from_=0, to=23, format="%02.0f", textvariable=self.push_hour, width=4).pack(side="left")
        ttk.Label(time_bar, text=":").pack(side="left")
        ttk.Spinbox(time_bar, from_=0, to=59, format="%02.0f", textvariable=self.push_minute, width=4).pack(side="left", padx=6)
        ttk.Button(time_bar, text=text_for("add_push_time", language), command=self._add_push_time).pack(side="left", padx=8)
        self.time_hint = ttk.Label(time_bar, text=", ".join(self.push_times))
        self.time_hint.pack(side="left", padx=6)
        ttk.Label(time_bar, text=text_for("timezone", language)).pack(side="left", padx=(12, 4))
        timezone_values = sorted(available_timezones())
        if self.task_timezone.get() not in timezone_values:
            timezone_values.append(self.task_timezone.get())
        self.timezone_values = tuple(timezone_values)
        self.timezone_picker = TimezonePicker(time_bar, self.task_timezone, self.timezone_values)
        self.timezone_picker.pack(side="left", fill="x", expand=True)
        ttk.Button(frame, text=text_for("save_task", language), command=self._save).grid(row=13, column=0, sticky="e", pady=(14, 0))
        ttk.Button(frame, text=text_for("cancel", language), command=self.destroy).grid(row=13, column=1, sticky="e", pady=(14, 0))
        self._apply_direction()
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        dialog_width = min(1180, max(760, screen_width - 60))
        dialog_height = min(820, max(560, screen_height - 100))
        self.minsize(min(760, dialog_width), min(560, dialog_height))
        self.geometry(f"{dialog_width}x{dialog_height}+{max(0, parent.winfo_rootx() + 40)}+{max(0, parent.winfo_rooty() + 40)}")
        self.wait_window()

    def _on_task_language_change(self, _event: Any = None) -> None:
        selected = self.task_language_display.get()
        self.task_language.set(self._locale_name_to_code.get(selected, self.task_language.get()))

    def _add_window(self) -> None:
        try:
            days = int(self.window_days.get())
            if days <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror(text_for("configuration_error", self.language), text_for("positive_integer_error", self.language), parent=self)
            return
        value = f"{days}d"
        if value not in self.query_windows:
            self.query_windows.append(value)
            self.window_list.insert("end", value)
            self.window_list.selection_set("end")
        self.window_hint.configure(text=", ".join(self.query_windows))

    def _add_push_time(self) -> None:
        try:
            value = self._current_push_time()
        except (ValueError, TypeError):
            messagebox.showerror(text_for("configuration_error", self.language), text_for("invalid_time", self.language), parent=self)
            return
        if value not in self.push_times:
            self.push_times.append(value)
            self.push_times.sort()
        self.time_hint.configure(text=", ".join(self.push_times))

    def _current_push_time(self) -> str:
        value = f"{int(self.push_hour.get()):02d}:{int(self.push_minute.get()):02d}"
        ScheduleConfig(value, "1d")
        return value

    def _filter_coins(self, _event: Any = None) -> None:
        query = self.coin.get().strip().upper()
        self.coin_combo.configure(values=tuple(item for item in self.coin_values if query in item))

    def _render_uids(self) -> None:
        query = self.uid_search.get().strip()
        self.uid_list.delete(0, "end")
        visible = [uid for uid in self.available_uids if not query or query in str(uid)]
        for uid in visible:
            self.uid_list.insert("end", str(uid))
            if uid in self.selected_uids:
                self.uid_list.selection_set("end")

    def _capture_uid_selection(self, _event: Any = None) -> None:
        query = self.uid_search.get().strip()
        visible = [uid for uid in self.available_uids if not query or query in str(uid)]
        self.selected_uids = {uid for uid in self.selected_uids if uid not in visible}
        self.selected_uids.update(visible[index] for index in self.uid_list.curselection())

    def _toggle_uid_controls(self) -> None:
        state = "disabled" if self.all_confirmed.get() else "normal"
        self.uid_entry.configure(state=state)
        self.uid_load_button.configure(state=state)
        self.uid_list.configure(state=state)

    def _load_uids(self) -> None:
        try:
            if not self.profile.get().strip():
                raise ValueError(text_for("select_profile_first", self.language))
            config = self.store.load()
            skill_root = config.skill_root or (discover_skill_roots()[0] if discover_skill_roots() else "")
            if not skill_root:
                raise ValueError(text_for("confirm_skill_path", self.language))
            self.available_uids = PartnerClient(skill_root).fetch_referral_uids(self.profile.get().strip())
            self.selected_uids = set(self.available_uids)
            self._render_uids()
        except Exception as exc:
            messagebox.showerror(text_for("configuration_error", self.language), str(exc), parent=self)

    def _refresh_groups(self) -> None:
        values = [group.label or group.chat_id for group in self.store.load().groups]
        self.group_combo.configure(values=values)
        if self.group_name.get() not in values:
            self.group_name.set(values[0] if values else "")

    def _save(self) -> None:
        try:
            config = self.store.load()
            group = next((group for group in config.groups if (group.label or group.chat_id) == self.group_name.get()), None)
            if group is None or not self.name.get().strip() or not self.profile.get().strip():
                raise ValueError(text_for("group_missing", self.language))
            if self.all_confirmed.get():
                scope = {"mode": "all", "all_confirmed": True}
            else:
                self._capture_uid_selection()
                values = sorted(self.selected_uids)
                if not values:
                    raise ValueError(text_for("scope_error", self.language))
                scope = {"mode": "uids", "uids": values}
            products = tuple(product for product, variable in self.product_vars.items() if variable.get())
            if not products:
                raise ValueError(text_for("select_product", self.language))
            selected_windows = [period for period, variable in self.window_vars.items() if variable.get()]
            if self.custom_days_enabled.get():
                try:
                    custom_days = int(self.window_days.get())
                    if custom_days <= 0:
                        raise ValueError
                except ValueError as exc:
                    raise ValueError(text_for("positive_integer_error", self.language)) from exc
                selected_windows.append(f"{custom_days}d")
            if not selected_windows:
                raise ValueError(text_for("select_query_window", self.language))
            try:
                selected_timezone = resolve_timezone_query(
                    self.timezone_values,
                    self.task_timezone.get().strip(),
                    self.task_timezone.get().strip(),
                )
                self.task_timezone.set(selected_timezone)
                push_times = resolve_push_times(
                    self.push_times,
                    self._initial_push_time,
                    self._current_push_time(),
                )
            except (ValueError, TypeError) as exc:
                raise ValueError(text_for("invalid_time", self.language)) from exc
            schedules = [
                ScheduleConfig(
                    push_time,
                    window,
                    start_date=(self.window_start_date.get().strip() if window not in self.window_vars else ""),
                    timezone=selected_timezone,
                )
                for push_time in push_times
                for window in selected_windows
            ]
            task = PushTaskConfig(task_id=self.task.task_id if self.task else uuid.uuid4().hex, name=self.name.get().strip(), bot_name=self.bot_name.get(), chat_id=group.chat_id, profile=self.profile.get(), query=QueryConfig(coin=self.coin.get().strip().upper(), product_types=products, scope=scope, formula=self.formula.get()), schedules=tuple(schedules), language=self.task_language.get())
            tasks = [item for item in config.tasks if item.task_id != task.task_id]
            tasks.append(task)
            self.store.update(config.with_tasks(tuple(tasks)), allow_plaintext=True)
        except Exception as exc:
            messagebox.showerror(text_for("configuration_error", self.language), str(exc), parent=self)
            return
        self.result = True
        self.destroy()


def launch(store: ConfigStore, language: str = "auto") -> None:
    scheduler = GuiScheduler(store)
    scheduler.start()
    try:
        ConfigWindow(store, language=language).mainloop()
    finally:
        scheduler.stop()
        scheduler.join(timeout=2)
