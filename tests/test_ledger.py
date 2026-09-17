import tempfile
import unittest
from pathlib import Path

from weex_tg_bot.ledger import DeliveryLedger


class LedgerTests(unittest.TestCase):
    def test_reservation_is_idempotent_and_force_reopens(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = DeliveryLedger(Path(directory) / "state.sqlite3")
            self.assertTrue(ledger.reserve("profile", "2026-09-15", "-1001"))
            ledger.mark_sent("profile", "2026-09-15", "-1001")
            self.assertFalse(ledger.reserve("profile", "2026-09-15", "-1001"))
            self.assertTrue(ledger.reserve("profile", "2026-09-15", "-1001", force=True))
            ledger.mark_failed("profile", "2026-09-15", "-1001", "network")
            self.assertEqual(ledger.status("profile", "2026-09-15", "-1001"), "failed")

    def test_same_chat_can_be_delivered_by_different_bots(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = DeliveryLedger(Path(directory) / "state.sqlite3")
            self.assertTrue(ledger.reserve("profile", "2026-09-15", "-1001", bot_name="alpha"))
            ledger.mark_sent("profile", "2026-09-15", "-1001", bot_name="alpha")
            self.assertTrue(ledger.reserve("profile", "2026-09-15", "-1001", bot_name="beta"))
            self.assertEqual(ledger.status("profile", "2026-09-15", "-1001", bot_name="alpha"), "sent")
            self.assertEqual(ledger.status("profile", "2026-09-15", "-1001", bot_name="beta"), "sending")


if __name__ == "__main__":
    unittest.main()
