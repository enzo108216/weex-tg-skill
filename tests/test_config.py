import tempfile
import unittest
from pathlib import Path
import sqlite3

from weex_tg_bot.config import ConfigStore, mask_token
from weex_tg_bot.models import AppConfig, BotConfig, GroupConfig, PushTaskConfig, QueryConfig


class MemoryKeyring:
    def __init__(self):
        self.values = {}

    def get_password(self, service, username):
        return self.values.get((service, username))

    def set_password(self, service, username, password):
        self.values[(service, username)] = password

    def delete_password(self, service, username):
        self.values.pop((service, username), None)


def binding(chat_id, profile="profile"):
    return GroupConfig(
        chat_id,
        profile=profile,
        query=QueryConfig(product_types=("SPOT",), scope={"mode": "all", "all_confirmed": True}),
    )


class ConfigTests(unittest.TestCase):
    def test_tokens_are_saved_in_sqlite_by_default_and_show_masks(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ConfigStore(Path(directory), keyring_backend=None)
            store.set_token("123:secret")
            self.assertEqual(mask_token("123:secret"), "123:••••••")
            self.assertNotIn("secret", str(store.display()))
            self.assertEqual(store.load().bots[0].token, "123:secret")
            store.clear_token()
            self.assertEqual(store.load().bots[0].token, "")

    def test_groups_are_deduplicated_by_bot_and_chat(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ConfigStore(Path(directory), keyring_backend=None)
            store.upsert_group(binding("-1001"), bot_name="main")
            store.upsert_group(binding("-1001", profile="profile-b"), bot_name="main")
            groups = store.load().bots[0].groups
            self.assertEqual(len(groups), 1)
            self.assertEqual(groups[0].profile, "profile-b")

    def test_display_exposes_custom_group_name(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ConfigStore(Path(directory), keyring_backend=None)
            store.set_token("123:secret", bot_name="rebates", allow_plaintext=True)
            store.upsert_group(
                GroupConfig(
                    "-1001",
                    label="运营群",
                    profile="profile",
                    query=QueryConfig(scope={"mode": "all", "all_confirmed": True}),
                ),
                bot_name="rebates",
            )
            shown_group = store.display()["bots"][0]["groups"][0]
            self.assertEqual(store.display()["bots"][0]["bot_name"], "rebates")
            self.assertEqual(shown_group["group_name"], "运营群")
            self.assertEqual(shown_group["label"], "运营群")

    def test_custom_bot_name_supports_unicode_display_names(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ConfigStore(Path(directory), keyring_backend=None)
            store.set_token("123:secret", bot_name="返佣机器人", allow_plaintext=True)
            self.assertEqual(store.load().bots[0].name, "返佣机器人")

    def test_groups_and_push_tasks_are_persisted_separately(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ConfigStore(Path(directory), keyring_backend=None)
            group = GroupConfig("-1001", label="运营群")
            task = PushTaskConfig(
                task_id="daily-ops",
                name="每日运营返佣",
                bot_name="main",
                chat_id="-1001",
                profile="profile",
                query=QueryConfig(scope={"mode": "all", "all_confirmed": True}),
            )
            store.save(
                store.load().with_bots((BotConfig("main", "123:token", (group,)),)).with_tasks((task,)),
                allow_plaintext=True,
            )
            loaded = store.load()
            self.assertEqual(loaded.bots[0].groups[0].label, "运营群")
            # The in-memory group keeps a read-only legacy projection for
            # callers; persisted task ownership is asserted independently.
            self.assertEqual(loaded.bots[0].groups[0].profile, "profile")
            self.assertEqual(loaded.tasks[0].name, "每日运营返佣")

    def test_query_filters_are_not_locally_limited_to_known_enum_values(self):
        query = QueryConfig(coin="NEWCOIN", product_types=("NEWPRODUCT",), scope={"mode": "all", "all_confirmed": True})
        self.assertEqual(query.coin, "NEWCOIN")
        self.assertEqual(query.product_types, ("NEWPRODUCT",))

    def test_custom_schedule_requires_and_persists_start_date(self):
        from weex_tg_bot.models import ScheduleConfig
        schedule = ScheduleConfig("09:00", "3d", start_date="2026-09-01")
        self.assertEqual(schedule.to_dict()["start_date"], "2026-09-01")

    def test_schedule_timezone_is_validated_and_persisted(self):
        from weex_tg_bot.models import ScheduleConfig
        schedule = ScheduleConfig("09:00", "1d", timezone="Asia/Shanghai")
        self.assertEqual(schedule.to_dict()["timezone"], "Asia/Shanghai")

    def test_gui_language_setting_survives_configuration_saves(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ConfigStore(Path(directory), keyring_backend=None)
            store.set_gui_language("pt-BR")
            self.assertEqual(store.get_gui_language(), "pt_br")
            store.save(AppConfig(), allow_plaintext=True)
            self.assertEqual(store.get_gui_language(), "pt_br")

    def test_default_store_persists_token_in_sqlite_without_keyring(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ConfigStore(Path(directory))
            store.set_token("123:default-db")
            self.assertIsNone(store.keyring)
            with sqlite3.connect(store.path) as connection:
                value = connection.execute("SELECT plaintext_token FROM bots WHERE name = 'main'").fetchone()[0]
            self.assertEqual(value, "123:default-db")

    def test_supports_multiple_bots_with_independent_group_bindings(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ConfigStore(Path(directory), keyring_backend=None)
            store.set_token("111:alpha", bot_name="alpha", allow_plaintext=True)
            store.upsert_group(binding("-1001", "profile-a"), bot_name="alpha")
            store.set_token("222:beta", bot_name="beta", allow_plaintext=True)
            store.upsert_group(binding("-1002", "profile-b"), bot_name="beta")
            config = store.load()
            self.assertEqual(config.bots[0].groups[0].profile, "profile-a")
            self.assertEqual(config.bots[1].groups[0].profile, "profile-b")
            shown = str(store.display())
            self.assertNotIn("111:alpha", shown)
            self.assertNotIn("222:beta", shown)

    def test_remove_bot_deletes_its_tasks_but_keeps_standalone_groups(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ConfigStore(Path(directory), keyring_backend=None)
            group = binding("-1001", "profile-a")
            store.set_token("111:alpha", bot_name="alpha", allow_plaintext=True)
            store.upsert_group(group, bot_name="alpha")
            store.set_token("222:beta", bot_name="beta", allow_plaintext=True)
            store.upsert_group(group, bot_name="beta")

            store.remove_bot("alpha")

            config = store.load()
            self.assertEqual([bot.name for bot in config.bots], ["beta"])
            self.assertEqual([task.bot_name for task in config.tasks], ["beta"])
            self.assertEqual([item.chat_id for item in config.groups], ["-1001"])

    def test_remove_group_deletes_all_tasks_for_the_standalone_group(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ConfigStore(Path(directory), keyring_backend=None)
            group = binding("-1001", "profile-a")
            store.set_token("111:alpha", bot_name="alpha", allow_plaintext=True)
            store.upsert_group(group, bot_name="alpha")
            store.set_token("222:beta", bot_name="beta", allow_plaintext=True)
            store.upsert_group(group, bot_name="beta")

            store.remove_group("-1001")

            config = store.load()
            self.assertEqual(config.groups, ())
            self.assertEqual(config.tasks, ())
            self.assertEqual([bot.name for bot in config.bots], ["alpha", "beta"])

    def test_keyring_keeps_tokens_out_of_sqlite(self):
        with tempfile.TemporaryDirectory() as directory:
            keyring = MemoryKeyring()
            store = ConfigStore(Path(directory), keyring_backend=keyring)
            store.set_token("111:alpha", bot_name="alpha")
            store.set_token("222:beta", bot_name="beta")
            with sqlite3.connect(store.path) as connection:
                rows = connection.execute("SELECT name, plaintext_token FROM bots ORDER BY name").fetchall()
            self.assertEqual(rows, [("alpha", ""), ("beta", "")])
            self.assertEqual(keyring.values[("weex-tg-skill", "telegram-bot-token:alpha")], "111:alpha")
            self.assertEqual(keyring.values[("weex-tg-skill", "telegram-bot-token:beta")], "222:beta")


if __name__ == "__main__":
    unittest.main()
