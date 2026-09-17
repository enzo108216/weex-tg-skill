import unittest
from datetime import datetime, timezone
from io import StringIO
import json
from unittest.mock import patch

from weex_tg_bot.cli import _binding_from_args, _config_find, _scheduled_bots, build_parser
from weex_tg_bot.models import AppConfig, BotConfig, GroupConfig, PushTaskConfig, QueryConfig, ScheduleConfig


class CliTests(unittest.TestCase):
    def test_gui_accepts_explicit_language(self):
        args = build_parser().parse_args(["gui", "--language", "en"])
        self.assertEqual(args.language, "en")

    def test_gui_accepts_every_locale_file(self):
        for language in ("zh_tw", "ar", "pt_br", "fa_ir"):
            args = build_parser().parse_args(["gui", "--language", language])
            self.assertEqual(args.language, language)

    def test_add_task_accepts_existing_target_and_independent_name(self):
        args = build_parser().parse_args(
            [
                "config", "add-task", "-1001",
                "--bot-name", "rebates",
                "--task-name", "每日返佣",
                "--profile", "account-a",
                "--all-confirmed",
                "--schedule", "09:00=1d",
            ]
        )
        self.assertEqual(args.task_name, "每日返佣")
        self.assertEqual(args.bot, "rebates")

    def test_schedule_accepts_anchored_custom_days(self):
        args = build_parser().parse_args(
            [
                "config", "add-task", "-1001",
                "--bot-name", "rebates",
                "--task-name", "三日任务",
                "--profile", "account-a",
                "--all-confirmed",
                "--schedule", "09:00=3d@2026-09-01",
            ]
        )
        from weex_tg_bot.cli import _parse_schedule_values
        self.assertEqual(_parse_schedule_values(args.schedule)[0].start_date, "2026-09-01")

    def test_custom_bot_and_group_name_aliases_are_accepted(self):
        args = build_parser().parse_args(
            [
                "config", "add-group", "-1001",
                "--group-name", "运营群",
            ]
        )
        group = _binding_from_args(args)
        self.assertEqual(group.label, "运营群")

    def test_add_group_is_standalone(self):
        args = build_parser().parse_args(
            [
                "config", "add-group", "-1001",
            ]
        )
        group = _binding_from_args(args)
        self.assertEqual(group.chat_id, "-1001")

    def test_config_parser_supports_bot_and_group_management(self):
        remove_bot = build_parser().parse_args(["config", "remove-bot", "ops"])
        self.assertEqual(remove_bot.config_command, "remove-bot")
        self.assertEqual(remove_bot.bot_name, "ops")

        find_group = build_parser().parse_args(["config", "find", "group", "运营"])
        self.assertEqual(find_group.config_command, "find")
        self.assertEqual(find_group.kind, "group")
        self.assertEqual(find_group.query, "运营")

    def test_config_find_filters_groups_by_name_or_chat_id(self):
        args = build_parser().parse_args(["config", "find", "group", "1002"])
        fake_store = unittest.mock.Mock()
        fake_store.display.return_value = {
            "groups": [
                {"group_name": "运营群", "chat_id": "-1001"},
                {"group_name": "Ops", "chat_id": "-1002"},
            ],
            "bots": [],
        }
        with patch("weex_tg_bot.cli._store", return_value=fake_store), patch("sys.stdout", new_callable=StringIO) as output:
            self.assertEqual(_config_find(args), 0)
        self.assertEqual(json.loads(output.getvalue())["groups"], [{"group_name": "Ops", "chat_id": "-1002"}])

    def test_send_result_requires_explicit_binding(self):
        with self.assertRaises(SystemExit):
            build_parser().parse_args(["send-result", "--date", "2026-09-15"])

    def test_scheduler_selects_enabled_bindings_by_their_own_utc_time(self):
        query = QueryConfig(scope={"mode": "all", "all_confirmed": True})
        config = AppConfig(
            bots=(
                BotConfig(
                    "main",
                    "token",
                    (
                        GroupConfig("-1001", profile="a", query=query, schedules=(ScheduleConfig("09:00", "1d"),)),
                        GroupConfig("-1002", profile="b", query=query, schedules=(ScheduleConfig("18:30", "1w"),)),
                        GroupConfig("-1003", profile="c", query=query, schedules=()),
                    ),
                ),
            )
        )
        due = _scheduled_bots(config, datetime(2026, 9, 16, 9, 0, tzinfo=timezone.utc))
        self.assertEqual([group.chat_id for group in due[0].groups], ["-1001"])

    def test_scheduler_matches_task_time_in_configured_timezone(self):
        from weex_tg_bot.models import PushTaskConfig
        query = QueryConfig(scope={"mode": "all", "all_confirmed": True})
        task = PushTaskConfig(
            task_id="tz-task",
            name="上海任务",
            bot_name="main",
            chat_id="-1001",
            profile="profile",
            query=query,
            schedules=(ScheduleConfig("09:00", "1d", timezone="Asia/Shanghai"),),
        )
        config = AppConfig(bots=(BotConfig("main", "token", (GroupConfig("-1001", label="群"),)),), tasks=(task,))
        due = _scheduled_bots(config, datetime(2026, 9, 16, 1, 0, tzinfo=timezone.utc))
        self.assertEqual([group.chat_id for group in due[0].groups], ["-1001"])

    def test_scheduler_preserves_task_language_for_scheduled_formatter(self):
        from weex_tg_bot.cli import _scheduled_tasks
        query = QueryConfig(scope={"mode": "all", "all_confirmed": True})
        task = PushTaskConfig(
            task_id="lang-task",
            name="German task",
            bot_name="main",
            chat_id="-1001",
            profile="profile",
            query=query,
            schedules=(ScheduleConfig("09:00", "1d"),),
            language="de",
        )
        config = AppConfig(bots=(BotConfig("main", "token"),), tasks=(task,))
        due = _scheduled_tasks(config, datetime(2026, 9, 16, 9, 0, tzinfo=timezone.utc))
        self.assertEqual(due[0][1].language, "de")


if __name__ == "__main__":
    unittest.main()
