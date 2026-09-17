import json
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path

from weex_tg_bot.models import QueryConfig
from weex_tg_bot.partner import (
    PartnerClient,
    PartnerQueryError,
    build_commission_requests,
    build_commission_range_requests,
    records_from_partner_envelopes,
)


class PartnerTests(unittest.TestCase):
    def test_fetches_referral_uids_as_complete_options(self):
        client = PartnerClient(runner=lambda payload: {
            "ok": True,
            "complete": True,
            "partial": False,
            "records": [{"uid": 1002}, {"uid": 1001}, {"uid": 1002}],
        })
        self.assertEqual(client.fetch_referral_uids("profile"), [1001, 1002])

    def test_subprocess_uses_the_partner_operation_as_cli_subcommand(self):
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / "partner_cli.py"
            script.write_text(
                "import json, sys; "
                "print(json.dumps({'ok': True, 'complete': True, 'partial': False, "
                "'records': [{'uid': 7}] if sys.argv[1] == 'list-referral-uids' else []}))",
                encoding="utf-8",
            )
            client = PartnerClient(skill_root=script)
            self.assertEqual(client.fetch_referral_uids("profile"), [7])
    def test_discovers_partner_cli_from_explicit_environment_path(self):
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / "weex_partner_cli.py"
            script.write_text("# test marker\n", encoding="utf-8")
            previous = os.environ.get("WEEX_PARTNER_CLI")
            os.environ["WEEX_PARTNER_CLI"] = str(script)
            try:
                self.assertEqual(PartnerClient()._script(), script)
            finally:
                if previous is None:
                    os.environ.pop("WEEX_PARTNER_CLI", None)
                else:
                    os.environ["WEEX_PARTNER_CLI"] = previous

    def test_accepts_only_complete_partner_envelopes_for_push(self):
        payload = {
            "results": [
                {"ok": True, "complete": True, "partial": False, "records": [{"coin": "USDT"}]},
                {"ok": True, "complete": True, "partial": False, "records": [{"coin": "USDT"}]},
            ]
        }
        self.assertEqual(len(records_from_partner_envelopes(payload)), 2)
        with self.assertRaises(PartnerQueryError):
            records_from_partner_envelopes({"ok": True, "complete": False, "partial": True, "records": []})

    def test_builds_one_request_per_product_with_utc_day_window(self):
        query = QueryConfig(
            coin="USDT",
            product_types=("SPOT", "FUTURES"),
            scope={"mode": "all", "all_confirmed": True},
        )
        requests = build_commission_requests("profile-a", date(2026, 9, 15), query)
        self.assertEqual([item["filters"]["product_type"] for item in requests], ["SPOT", "FUTURES"])
        self.assertEqual(requests[0]["time_range"]["start"], "2026-09-15T00:00:00Z")
        self.assertEqual(requests[0]["time_range"]["end"], "2026-09-15T23:59:59.999Z")
        self.assertEqual(requests[0]["result_mode"], "complete_list")

    def test_splits_long_natural_periods_into_complete_calendar_segments(self):
        query = QueryConfig(product_types=("SPOT",), scope={"mode": "all", "all_confirmed": True})
        requests = build_commission_range_requests("profile-a", date(2025, 1, 1), date(2025, 12, 31), query)
        self.assertEqual(len(requests), 4)
        self.assertEqual(requests[0]["time_range"]["start"], "2025-01-01T00:00:00Z")
        self.assertEqual(requests[-1]["time_range"]["end"], "2025-12-31T23:59:59.999Z")

    def test_rejects_unconfirmed_all_scope_before_runner(self):
        query = QueryConfig(
            coin="USDT",
            product_types=("SPOT",),
            scope={"mode": "all", "all_confirmed": False},
        )
        called = []
        client = PartnerClient(runner=lambda payload: called.append(payload))
        with self.assertRaises(PartnerQueryError):
            client.fetch_records("profile-a", date(2026, 9, 15), query)
        self.assertEqual(called, [])

    def test_rejects_partial_skill_envelope(self):
        query = QueryConfig(
            coin="USDT",
            product_types=("SPOT",),
            scope={"mode": "uids", "uids": [1]},
        )
        client = PartnerClient(
            runner=lambda payload: {
                "ok": True,
                "complete": False,
                "partial": True,
                "records": [{"fee": "1"}],
            }
        )
        with self.assertRaises(PartnerQueryError):
            client.fetch_records("profile-a", date(2026, 9, 15), query)

    def test_runner_payload_is_json_safe_and_records_are_combined(self):
        query = QueryConfig(
            coin="USDT",
            product_types=("SPOT", "FUTURES"),
            scope={"mode": "uids", "uids": [1]},
        )
        seen = []

        def runner(payload):
            seen.append(payload)
            return {"ok": True, "complete": True, "partial": False, "records": [{"coin": "USDT"}]}

        records = PartnerClient(runner=runner).fetch_records("profile-a", date(2026, 9, 15), query)
        self.assertEqual(len(seen), 2)
        self.assertEqual(len(records), 2)
        json.dumps(seen[0])


if __name__ == "__main__":
    unittest.main()
