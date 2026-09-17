import tempfile
import unittest
from datetime import date
from pathlib import Path

from weex_tg_bot.ledger import DeliveryLedger
from weex_tg_bot.models import AppConfig, BotConfig, GroupConfig, PushTaskConfig, QueryConfig
from weex_tg_bot.periods import previous_natural_period
from weex_tg_bot.service import RebateService


def record(source_type=1, commission="2"):
    return {
        "coin": "USDT", "fee": "1", "commission": commission, "sourceType": source_type,
        "takerAmount": "10", "makerAmount": "0", "uid": 1, "date": 1,
    }


def binding(chat_id, profile, products=("SPOT",)):
    return GroupConfig(
        chat_id=chat_id,
        profile=profile,
        query=QueryConfig(product_types=products, scope={"mode": "uids", "uids": [1]}),
    )


class FakeClient:
    def __init__(self, failing=None):
        self.calls = []
        self.failing = failing

    def fetch_records(self, profile, utc_date, query):
        self.calls.append((profile, utc_date, query))
        if profile == self.failing:
            raise RuntimeError("partner failed")
        return [record(), record(2, "1")]

    def fetch_records_for_range(self, profile, start_date, end_date, query):
        self.calls.append((profile, start_date, end_date, query))
        if profile == self.failing:
            raise RuntimeError("partner failed")
        return [record(), record(2, "1")]


class FakeSender:
    def __init__(self, failing=None):
        self.calls = []
        self.failing = failing

    def send(self, token, chat_id, text):
        self.calls.append((token, chat_id, text))
        if chat_id == self.failing:
            raise RuntimeError("send failed")


class ServiceTests(unittest.TestCase):
    def config(self, *groups):
        return AppConfig(
            bots=(BotConfig("main", "token", tuple(groups)),),
        )

    def test_fetches_and_sends_using_each_group_binding(self):
        with tempfile.TemporaryDirectory() as directory:
            client = FakeClient()
            sender = FakeSender()
            service = RebateService(self.config(binding("-1001", "profile-a"), binding("-1002", "profile-b", ("FUTURES",))), client, sender, DeliveryLedger(Path(directory) / "state.db"))
            result = service.send_for_date(date(2026, 9, 15))
            self.assertTrue(result.ok)
            self.assertEqual([call[0] for call in client.calls], ["profile-a", "profile-b"])
            self.assertEqual([call[1] for call in sender.calls], ["-1001", "-1002"])
            self.assertIn("触发方式：手动查询", sender.calls[0][2])
            self.assertIn("WEEX 账号：profile-a", sender.calls[0][2])
            self.assertIn("查询范围：指定下级 UID：1", sender.calls[0][2])
            self.assertIn("查询时间（UTC）：2026-09-15 00:00:00 至 2026-09-15 23:59:59.999", sender.calls[0][2])
            self.assertIn("推送目标：main / -1002", sender.calls[1][2])
            self.assertIn("推送目标：main / -1001", sender.calls[0][2])

    def test_identical_bindings_share_one_partner_query(self):
        with tempfile.TemporaryDirectory() as directory:
            client = FakeClient()
            sender = FakeSender()
            query_binding_a = binding("-1001", "profile-a")
            query_binding_b = binding("-1002", "profile-a")
            service = RebateService(self.config(query_binding_a, query_binding_b), client, sender, DeliveryLedger(Path(directory) / "state.db"))
            result = service.send_for_date(date(2026, 9, 15))
            self.assertTrue(result.ok)
            self.assertEqual(len(client.calls), 1)
            self.assertEqual(len(sender.calls), 2)

    def test_partner_failure_is_fail_closed_before_any_send(self):
        with tempfile.TemporaryDirectory() as directory:
            client = FakeClient(failing="profile-b")
            sender = FakeSender()
            service = RebateService(self.config(binding("-1001", "profile-a"), binding("-1002", "profile-b")), client, sender, DeliveryLedger(Path(directory) / "state.db"))
            with self.assertRaises(RuntimeError):
                service.send_for_date(date(2026, 9, 15))
            self.assertEqual(sender.calls, [])

    def test_send_can_target_only_due_bindings(self):
        with tempfile.TemporaryDirectory() as directory:
            client = FakeClient()
            sender = FakeSender()
            first = binding("-1001", "profile-a")
            second = binding("-1002", "profile-b")
            service = RebateService(self.config(first, second), client, sender, DeliveryLedger(Path(directory) / "state.db"))
            result = service.send_for_date(
                date(2026, 9, 15),
                bots=(BotConfig("main", "token", (first,)),),
            )
            self.assertTrue(result.ok)
            self.assertEqual([call[1] for call in sender.calls], ["-1001"])

    def test_sends_previous_natural_period_and_uses_window_in_ledger_key(self):
        with tempfile.TemporaryDirectory() as directory:
            client = FakeClient()
            sender = FakeSender()
            group = binding("-1001", "profile-a")
            service = RebateService(self.config(group), client, sender, DeliveryLedger(Path(directory) / "state.db"))
            window = previous_natural_period("1w", date(2026, 9, 16))
            result = service.send_for_window(window)
            self.assertTrue(result.ok)
            self.assertEqual(client.calls[0][1:3], (date(2026, 9, 7), date(2026, 9, 13)))
            self.assertIn("查询时间（UTC）：2026-09-07 00:00:00 至 2026-09-13 23:59:59.999", sender.calls[0][2])
            self.assertIn("触发方式：定时任务", sender.calls[0][2])
            self.assertIn("WEEX 账号：profile-a", sender.calls[0][2])

    def test_one_failed_group_makes_result_failed(self):
        with tempfile.TemporaryDirectory() as directory:
            client = FakeClient()
            sender = FakeSender(failing="-1002")
            service = RebateService(self.config(binding("-1001", "profile-a"), binding("-1002", "profile-a")), client, sender, DeliveryLedger(Path(directory) / "state.db"))
            result = service.send_for_date(date(2026, 9, 15))
            self.assertFalse(result.ok)
            self.assertEqual(result.failed, ("-1002",))

    def test_push_tasks_are_sent_independently_from_group_catalog(self):
        with tempfile.TemporaryDirectory() as directory:
            group = GroupConfig("-1001", label="运营群")
            task = PushTaskConfig(
                task_id="daily-ops",
                name="每日运营返佣",
                bot_name="main",
                chat_id="-1001",
                profile="profile-a",
                query=QueryConfig(scope={"mode": "uids", "uids": [1]}),
            )
            client = FakeClient()
            sender = FakeSender()
            service = RebateService(
                AppConfig(bots=(BotConfig("main", "token", (group,)),), tasks=(task,)),
                client,
                sender,
                DeliveryLedger(Path(directory) / "state.db"),
            )
            result = service.send_task_for_date("daily-ops", date(2026, 9, 15))
            self.assertTrue(result.ok)
            self.assertEqual(client.calls[0][0], "profile-a")
            self.assertIn("运营群", sender.calls[0][2])


if __name__ == "__main__":
    unittest.main()
