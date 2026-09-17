import tempfile
import unittest
from pathlib import Path
import sqlite3

from weex_tg_bot.config import ConfigStore
from weex_tg_bot.models import BotConfig, GroupConfig, QueryConfig, ScheduleConfig


class DatabaseConfigTests(unittest.TestCase):
    def binding(self, chat_id="-1001", profile="profile-a", schedules=()):
        return GroupConfig(
            chat_id,
            label="ops",
            profile=profile,
            query=QueryConfig(product_types=("SPOT",), scope={"mode": "all", "all_confirmed": True}),
            schedules=schedules,
        )

    def test_bindings_are_persisted_per_bot_and_chat_in_sqlite(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ConfigStore(Path(directory), keyring_backend=None)
            config = store.load()
            self.assertEqual(config.bots, ())
            store.save(
                config.with_bots(
                    (
                        BotConfig("main", "111:token", (self.binding(),)),
                        BotConfig("ops", "222:token", (self.binding("-1002", "profile-b"),)),
                    )
                ),
                allow_plaintext=True,
            )

            loaded = store.load()
            self.assertEqual(loaded.skill_root, "")
            self.assertEqual(loaded.bots[0].groups[0].profile, "profile-a")
            self.assertEqual(loaded.bots[1].groups[0].profile, "profile-b")
            self.assertEqual(store.path.name, "config.sqlite3")

    def test_duplicate_bot_chat_binding_is_replaced_atomically(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ConfigStore(Path(directory), keyring_backend=None)
            store.set_token("111:token", allow_plaintext=True)
            store.upsert_group(self.binding(), bot_name="main")
            store.upsert_group(self.binding(profile="profile-b"), bot_name="main")
            groups = store.load().bots[0].groups
            self.assertEqual(len(groups), 1)
            self.assertEqual(groups[0].profile, "profile-b")

    def test_schedule_is_persisted_per_binding(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ConfigStore(Path(directory), keyring_backend=None)
            store.save(
                store.load().with_bots(
                    (
                        BotConfig(
                            "main",
                            "111:token",
                            (
                                self.binding("-1001", schedules=(ScheduleConfig("09:00", "1d"),)),
                                self.binding("-1002", schedules=(ScheduleConfig("18:30", "1w", enabled=False),)),
                            ),
                        ),
                    )
                ),
                allow_plaintext=True,
            )
            groups = {item.chat_id: item for item in store.load().bots[0].groups}
            self.assertEqual(groups["-1001"].schedules, (ScheduleConfig("09:00", "1d"),))
            self.assertEqual(groups["-1002"].schedules, (ScheduleConfig("18:30", "1w", enabled=False),))

    def test_existing_sqlite_binding_schema_gets_disabled_schedule_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.sqlite3"
            with sqlite3.connect(path) as connection:
                connection.executescript(
                    """
                    CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                    CREATE TABLE bots (name TEXT PRIMARY KEY, plaintext_token TEXT NOT NULL DEFAULT '');
                    CREATE TABLE group_bindings (
                        bot_name TEXT NOT NULL,
                        chat_id TEXT NOT NULL,
                        label TEXT NOT NULL DEFAULT '',
                        profile TEXT NOT NULL,
                        query_json TEXT NOT NULL,
                        PRIMARY KEY (bot_name, chat_id)
                    );
                    INSERT INTO bots(name, plaintext_token) VALUES ('main', '111:token');
                    INSERT INTO group_bindings(bot_name, chat_id, profile, query_json)
                    VALUES ('main', '-1001', 'profile-a', '{"coin":"USDT","product_types":["SPOT"],"scope":{"mode":"all","all_confirmed":true},"formula":"commission_minus_subaffiliate_commission"}');
                    """
                )
            config = ConfigStore(Path(directory), keyring_backend=None).load()
            self.assertEqual(config.bots[0].groups, ())
            self.assertEqual(config.groups, ())
            self.assertEqual(config.tasks, ())

    def test_old_json_is_not_read_or_migrated(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config.json").write_text(
                '{"profile":"legacy","query":{"coin":"BTC"}}', encoding="utf-8"
            )
            store = ConfigStore(root, keyring_backend=None)
            self.assertEqual(store.load().bots, ())
            self.assertEqual(store.load().skill_root, "")


if __name__ == "__main__":
    unittest.main()
