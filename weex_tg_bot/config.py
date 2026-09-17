from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import sqlite3
from typing import Any, Iterator

from .i18n import normalize_locale
from .models import (
    AppConfig,
    BotConfig,
    ConfigValidationError,
    GroupConfig,
    PushTaskConfig,
    QueryConfig,
    ScheduleConfig,
    validate_bot_name,
    validate_token,
)


_TOKEN_USERNAME_PREFIX = "telegram-bot-token:"


def default_config_dir() -> Path:
    override = os.environ.get("WEEX_TG_CONFIG_DIR")
    if override:
        return Path(override).expanduser()
    if os.name == "nt":
        return Path(os.environ.get("APPDATA", Path.home())) / "weex-tg-skill"
    if os.sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "weex-tg-skill"
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "weex-tg-skill"


def mask_token(token: str) -> str:
    if not token:
        return "<not configured>"
    if len(token) <= 6:
        return "•" * len(token)
    return f"{token[:3]}:{'•' * max(4, len(token) - 4)}"


class ConfigStore:
    """SQLite-backed runtime configuration store.

    SQLite is the source of truth for independent Bot, Group, PushTask, and
    TaskSchedule objects. Legacy binding tables are not created or read.
    """

    def __init__(self, root: Path | None = None, keyring_backend: Any = None) -> None:
        self.root = Path(root or default_config_dir()).expanduser()
        self.path = self.root / "config.sqlite3"
        # Tokens are stored in the local SQLite database by default. An
        # explicit backend is retained only for isolated callers/tests; the
        # application never auto-selects macOS/Windows keyring storage.
        if keyring_backend == "auto":
            keyring_backend = None
        self.keyring = keyring_backend
        self._initialize()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        self.root.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA foreign_keys=ON")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS bots (
                    name TEXT PRIMARY KEY,
                    plaintext_token TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS groups (
                    chat_id TEXT PRIMARY KEY,
                    label TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS push_tasks (
                    task_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    bot_name TEXT NOT NULL REFERENCES bots(name) ON DELETE CASCADE,
                    chat_id TEXT NOT NULL REFERENCES groups(chat_id) ON DELETE CASCADE,
                    profile TEXT NOT NULL,
                    query_json TEXT NOT NULL,
                    language TEXT NOT NULL DEFAULT 'zh'
                );
                CREATE TABLE IF NOT EXISTS push_task_schedules (
                    task_id TEXT NOT NULL REFERENCES push_tasks(task_id) ON DELETE CASCADE,
                    schedule_time TEXT NOT NULL,
                    period TEXT NOT NULL,
                    start_date TEXT NOT NULL DEFAULT '',
                    timezone TEXT NOT NULL DEFAULT 'UTC',
                    enabled INTEGER NOT NULL DEFAULT 1,
                    PRIMARY KEY (task_id, schedule_time, period, start_date, timezone)
                );
                """
            )
            task_columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(push_tasks)").fetchall()}
            if "language" not in task_columns:
                connection.execute("DROP TABLE IF EXISTS push_task_schedules")
                connection.execute("DROP TABLE IF EXISTS push_tasks")
                connection.execute("CREATE TABLE push_tasks (task_id TEXT PRIMARY KEY, name TEXT NOT NULL, bot_name TEXT NOT NULL REFERENCES bots(name) ON DELETE CASCADE, chat_id TEXT NOT NULL REFERENCES groups(chat_id) ON DELETE CASCADE, profile TEXT NOT NULL, query_json TEXT NOT NULL, language TEXT NOT NULL DEFAULT 'zh')")
                connection.execute("CREATE TABLE push_task_schedules (task_id TEXT NOT NULL REFERENCES push_tasks(task_id) ON DELETE CASCADE, schedule_time TEXT NOT NULL, period TEXT NOT NULL, start_date TEXT NOT NULL DEFAULT '', timezone TEXT NOT NULL DEFAULT 'UTC', enabled INTEGER NOT NULL DEFAULT 1, PRIMARY KEY (task_id, schedule_time, period, start_date, timezone))")
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass

    def get_setting(self, key: str, default: str = "") -> str:
        with self._connect() as connection:
            row = connection.execute("SELECT value FROM settings WHERE key = ?", (str(key),)).fetchone()
        return str(row["value"]) if row is not None else default

    def set_setting(self, key: str, value: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO settings(key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (str(key), str(value)),
            )

    def get_gui_language(self) -> str:
        return self.get_setting("gui_language", "")

    def set_gui_language(self, language: str) -> None:
        self.set_setting("gui_language", normalize_locale(language))

    def set_skill_root(self, skill_root: str) -> None:
        self.set_setting("skill_root", str(skill_root or "").strip())

    @staticmethod
    def _token_username(bot_name: str) -> str:
        return f"{_TOKEN_USERNAME_PREFIX}{bot_name}"

    def _keyring_token(self, bot_name: str) -> str:
        if self.keyring is None:
            return ""
        try:
            token = self.keyring.get_password("weex-tg-skill", self._token_username(bot_name)) or ""
        except Exception:
            token = ""
        return str(token)

    def _stored_plaintext_tokens(self) -> dict[str, str]:
        with self._connect() as connection:
            rows = connection.execute("SELECT name, plaintext_token FROM bots").fetchall()
        return {str(row["name"]): str(row["plaintext_token"] or "") for row in rows}

    def _stored_bot_names(self) -> set[str]:
        with self._connect() as connection:
            rows = connection.execute("SELECT name FROM bots").fetchall()
        return {str(row["name"]) for row in rows}

    @staticmethod
    def _query_from_json(raw: str):
        try:
            value = json.loads(raw)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ConfigValidationError("stored group query is invalid") from exc
        if not isinstance(value, dict):
            raise ConfigValidationError("stored group query must be an object")
        from .models import QueryConfig

        return QueryConfig(**value)

    def load(self) -> AppConfig:
        with self._connect() as connection:
            settings = {
                str(row["key"]): str(row["value"])
                for row in connection.execute("SELECT key, value FROM settings")
            }
            bot_rows = connection.execute(
                "SELECT name, plaintext_token FROM bots ORDER BY name"
            ).fetchall()
            catalog_rows = connection.execute(
                "SELECT chat_id, label FROM groups ORDER BY chat_id"
            ).fetchall()
            task_rows = connection.execute(
                "SELECT task_id, name, bot_name, chat_id, profile, query_json, language "
                "FROM push_tasks ORDER BY task_id"
            ).fetchall()
            task_schedule_rows = connection.execute(
                "SELECT task_id, schedule_time, period, start_date, timezone, enabled "
                "FROM push_task_schedules ORDER BY task_id, schedule_time, period"
            ).fetchall()

        schedules_by_task: dict[str, list[ScheduleConfig]] = {}
        for row in task_schedule_rows:
            schedules_by_task.setdefault(str(row["task_id"]), []).append(
                ScheduleConfig(
                    schedule_time=str(row["schedule_time"]),
                    period=str(row["period"]),
                    start_date=str(row["start_date"] or ""),
                    timezone=str(row["timezone"] or "UTC"),
                    enabled=bool(row["enabled"]),
                )
            )
        tasks: list[PushTaskConfig] = [
            PushTaskConfig(
                task_id=str(row["task_id"]),
                name=str(row["name"]),
                bot_name=str(row["bot_name"]),
                chat_id=str(row["chat_id"]),
                profile=str(row["profile"] or ""),
                query=self._query_from_json(str(row["query_json"])),
                schedules=tuple(schedules_by_task.get(str(row["task_id"]), ())),
                language=str(row["language"] or "zh") if "language" in row.keys() else "zh",
            )
            for row in task_rows
        ]
        catalog_groups: list[GroupConfig] = [
            GroupConfig(chat_id=str(row["chat_id"]), label=str(row["label"] or ""))
            for row in catalog_rows
        ]
        labels = {group.chat_id: group.label for group in catalog_groups}
        groups_by_bot: dict[str, list[GroupConfig]] = {}
        for task in tasks:
            groups_by_bot.setdefault(task.bot_name, []).append(
                GroupConfig(
                    chat_id=task.chat_id,
                    label=labels.get(task.chat_id, ""),
                    profile=task.profile,
                    query=task.query,
                    schedules=task.schedules,
                    language=task.language,
                )
            )

        bots: list[BotConfig] = []
        for row in bot_rows:
            name = str(row["name"])
            token = self._keyring_token(name) or str(row["plaintext_token"] or "")
            bots.append(BotConfig(name, token, tuple(groups_by_bot.get(name, ()))))

        return AppConfig(
            skill_root=settings.get("skill_root", ""),
            bots=tuple(bots),
            groups=tuple(catalog_groups),
            tasks=tuple(tasks),
        )

    def save(self, config: AppConfig, *, allow_plaintext: bool = True) -> None:
        for bot in config.bots:
            if bot.token:
                validate_token(bot.token)

        existing_names = self._stored_bot_names()
        tasks = list(config.tasks)
        if not tasks:
            tasks = [
                PushTaskConfig(
                    task_id=f"{bot.name}:{group.chat_id}",
                    name=group.label or group.chat_id,
                    bot_name=bot.name,
                    chat_id=group.chat_id,
                    profile=group.profile,
                    query=group.query,
                    schedules=group.schedules,
                    language=group.language,
                )
                for bot in config.bots
                for group in bot.groups
                if group.profile
            ]
        task_by_binding: dict[tuple[str, str], PushTaskConfig] = {}
        for task in tasks:
            task_by_binding.setdefault((task.bot_name, task.chat_id), task)
        catalog_groups = list(config.groups)
        if not catalog_groups:
            seen_catalog: set[str] = set()
            for bot in config.bots:
                for group in bot.groups:
                    if group.chat_id not in seen_catalog:
                        catalog_groups.append(group)
                        seen_catalog.add(group.chat_id)

        with self._connect() as connection:
            preserved_settings = {
                str(row["key"]): str(row["value"])
                for row in connection.execute("SELECT key, value FROM settings")
            }
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("DELETE FROM push_task_schedules")
            connection.execute("DELETE FROM push_tasks")
            connection.execute("DELETE FROM groups")
            connection.execute("DELETE FROM bots")
            connection.execute("DELETE FROM settings")
            connection.execute(
                "INSERT INTO settings(key, value) VALUES (?, ?)",
                ("skill_root", config.skill_root),
            )
            for key, value in preserved_settings.items():
                if key == "skill_root":
                    continue
                connection.execute(
                    "INSERT INTO settings(key, value) VALUES (?, ?)",
                    (key, value),
                )
            for group in catalog_groups:
                connection.execute(
                    "INSERT INTO groups(chat_id, label) VALUES (?, ?)",
                    (group.chat_id, group.label),
                )
            for bot in config.bots:
                stored_token = "" if self.keyring is not None else bot.token
                connection.execute(
                    "INSERT INTO bots(name, plaintext_token) VALUES (?, ?)",
                    (bot.name, stored_token),
                )
            for task in tasks:
                connection.execute(
                    "INSERT INTO push_tasks(task_id, name, bot_name, chat_id, profile, query_json, language) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        task.task_id,
                        task.name,
                        task.bot_name,
                        task.chat_id,
                        task.profile,
                        json.dumps(task.query.to_dict(), ensure_ascii=False, sort_keys=True),
                        task.language,
                    ),
                )
                for schedule in task.schedules:
                    connection.execute(
                        "INSERT INTO push_task_schedules(task_id, schedule_time, period, start_date, timezone, enabled) VALUES (?, ?, ?, ?, ?, ?)",
                        (task.task_id, schedule.schedule_time, schedule.period, schedule.start_date, schedule.timezone, 1 if schedule.enabled else 0),
                    )

        if self.keyring is not None:
            current_names = {bot.name for bot in config.bots}
            for name in existing_names - current_names:
                try:
                    self.keyring.delete_password("weex-tg-skill", self._token_username(name))
                except Exception:
                    pass
            for bot in config.bots:
                username = self._token_username(bot.name)
                if bot.token:
                    self.keyring.set_password("weex-tg-skill", username, validate_token(bot.token))
                else:
                    try:
                        self.keyring.delete_password("weex-tg-skill", username)
                    except Exception:
                        pass

    def set_token(self, token: str, *, bot_name: str = "main", allow_plaintext: bool = True) -> None:
        token = validate_token(token)
        bot_name = validate_bot_name(bot_name)
        config = self.load()
        bots = list(config.bots)
        current = next((bot for bot in bots if bot.name == bot_name), BotConfig(bot_name))
        replacement = BotConfig(bot_name, token, current.groups)
        bots = [replacement if bot.name == bot_name else bot for bot in bots]
        if not any(bot.name == bot_name for bot in bots):
            bots.append(replacement)
        self.save(config.with_bots(tuple(bots)), allow_plaintext=allow_plaintext)

    def clear_token(self) -> None:
        self.clear_bot_token("main")

    def clear_bot_token(self, bot_name: str) -> None:
        bot_name = validate_bot_name(bot_name)
        config = self.load()
        bots = [
            BotConfig(bot.name, "" if bot.name == bot_name else bot.token, bot.groups)
            for bot in config.bots
        ]
        self.save(config.with_bots(tuple(bots)), allow_plaintext=True)

    def update(self, config: AppConfig, *, allow_plaintext: bool = True) -> None:
        self.save(config, allow_plaintext=allow_plaintext)

    def upsert_group(
        self,
        group: GroupConfig,
        *,
        bot_name: str = "main",
        allow_plaintext: bool = True,
    ) -> None:
        bot_name = validate_bot_name(bot_name)
        config = self.load()
        bots = list(config.bots)
        current = next((bot for bot in bots if bot.name == bot_name), BotConfig(bot_name))
        replacement = current.with_group(group)
        bots = [replacement if bot.name == bot_name else bot for bot in bots]
        if not any(bot.name == bot_name for bot in bots):
            bots.append(replacement)
        tasks = list(config.tasks)
        task_found = False
        for index, task in enumerate(tasks):
            if task.bot_name == bot_name and task.chat_id == group.chat_id and group.profile:
                task_found = True
                tasks[index] = PushTaskConfig(
                    task_id=task.task_id,
                    name=task.name,
                    bot_name=bot_name,
                    chat_id=group.chat_id,
                    profile=group.profile,
                    query=group.query,
                    schedules=group.schedules,
                    language=task.language,
                )
        if group.profile and not task_found:
            tasks.append(
                PushTaskConfig(
                    task_id=f"{bot_name}:{group.chat_id}",
                    name=group.label or group.chat_id,
                    bot_name=bot_name,
                    chat_id=group.chat_id,
                    profile=group.profile,
                    query=group.query,
                    schedules=group.schedules,
                    language=group.language,
                )
            )
        groups = [item for item in config.groups if item.chat_id != group.chat_id]
        groups.append(GroupConfig(chat_id=group.chat_id, label=group.label))
        self.save(
            config.with_bots(tuple(bots)).with_groups(tuple(groups)).with_tasks(tuple(tasks)),
            allow_plaintext=allow_plaintext,
        )

    def remove_bot(self, bot_name: str) -> None:
        bot_name = validate_bot_name(bot_name)
        config = self.load()
        bots = tuple(bot for bot in config.bots if bot.name != bot_name)
        tasks = tuple(task for task in config.tasks if task.bot_name != bot_name)
        self.save(config.with_bots(bots).with_tasks(tasks), allow_plaintext=True)

    def remove_group(self, chat_id: str, *, bot_name: str = "main") -> None:
        # Groups are a standalone catalog. Removing one therefore removes all
        # task targets for that Chat ID, regardless of which Bot owns them.
        _ = bot_name  # retained for compatibility with older callers
        chat_id = str(chat_id)
        config = self.load()
        bots = tuple(
            BotConfig(
                bot.name,
                bot.token,
                tuple(group for group in bot.groups if group.chat_id != chat_id),
            )
            for bot in config.bots
        )
        tasks = tuple(task for task in config.tasks if task.chat_id != chat_id)
        groups = tuple(item for item in config.groups if item.chat_id != str(chat_id))
        self.save(config.with_bots(tuple(bots)).with_groups(groups).with_tasks(tasks), allow_plaintext=True)

    def display(self) -> dict[str, Any]:
        config = self.load()
        value = config.to_dict()
        value["bots"] = [
            {
                "name": bot.name,
                "bot_name": bot.name,
                "telegram_token": mask_token(bot.token),
                "groups": [group.to_dict() for group in bot.groups],
            }
            for bot in config.bots
        ]
        value["tasks"] = [task.to_dict() for task in config.tasks]
        value["config_path"] = str(self.path)
        value["ledger_path"] = str(self.root / "deliveries.sqlite3")
        return value
