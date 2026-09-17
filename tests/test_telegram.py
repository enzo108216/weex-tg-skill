import json
import unittest

from weex_tg_bot.telegram import TelegramError, TelegramSender


class TelegramTests(unittest.TestCase):
    def test_successful_send(self):
        sender = TelegramSender(
            transport=lambda request: (200, json.dumps({"ok": True, "result": {"message_id": 3}}).encode())
        )
        result = sender.send("123:secret-token", "-1001", "hello")
        self.assertEqual(result.message_id, 3)

    def test_api_failure_does_not_echo_token(self):
        token = "123:secret-token"
        sender = TelegramSender(
            transport=lambda request: (200, json.dumps({"ok": False, "description": "Forbidden"}).encode())
        )
        with self.assertRaises(TelegramError) as raised:
            sender.send(token, "-1001", "hello")
        self.assertNotIn(token, str(raised.exception))

    def test_http_failure_is_normalized(self):
        sender = TelegramSender(transport=lambda request: (500, b"gateway down"))
        with self.assertRaises(TelegramError):
            sender.send("123:secret-token", "-1001", "hello")


if __name__ == "__main__":
    unittest.main()
