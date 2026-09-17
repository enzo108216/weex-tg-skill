from __future__ import annotations

import json
from typing import Any, Callable
from urllib import error, parse, request


class TelegramError(RuntimeError):
    """A safe Telegram error that never includes the bot token."""


class TelegramSendResult:
    def __init__(self, message_id: int | None = None) -> None:
        self.message_id = message_id


class TelegramSender:
    def __init__(self, *, transport: Callable[[request.Request], tuple[int, bytes]] | None = None, timeout: int = 30) -> None:
        self.transport = transport or self._default_transport
        self.timeout = timeout

    def _default_transport(self, req: request.Request) -> tuple[int, bytes]:
        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                return int(response.status), response.read()
        except error.HTTPError as exc:
            return int(exc.code), exc.read()
        except (error.URLError, TimeoutError, OSError) as exc:
            raise TelegramError("Telegram network request failed") from exc

    def send(self, token: str, chat_id: str, text: str) -> TelegramSendResult:
        if not token or any(char.isspace() for char in token):
            raise TelegramError("Telegram token is not configured")
        if not chat_id:
            raise TelegramError("Telegram chat ID is not configured")
        if not text or len(text) > 4096:
            raise TelegramError("Telegram message must contain 1-4096 characters")
        # Token is used only to build the request URL and is never included in an error.
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        body = parse.urlencode({"chat_id": chat_id, "text": text}).encode("utf-8")
        req = request.Request(url, data=body, method="POST", headers={"Content-Type": "application/x-www-form-urlencoded"})
        status, raw = self.transport(req)
        try:
            payload: Any = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise TelegramError(f"Telegram returned invalid JSON (status={status})") from exc
        if status < 200 or status >= 300:
            raise TelegramError(f"Telegram HTTP request failed (status={status})")
        if not isinstance(payload, dict) or payload.get("ok") is not True:
            raise TelegramError("Telegram rejected the message")
        result = payload.get("result")
        message_id = result.get("message_id") if isinstance(result, dict) else None
        return TelegramSendResult(message_id if isinstance(message_id, int) else None)
