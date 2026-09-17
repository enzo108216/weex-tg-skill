from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import sqlite3
from pathlib import Path
from typing import Iterator


class DeliveryLedger:
    def __init__(self, path: Path) -> None:
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=10)
        try:
            connection.execute("PRAGMA journal_mode=WAL")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS deliveries (
                    profile TEXT NOT NULL,
                    utc_date TEXT NOT NULL,
                    chat_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    error TEXT,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (profile, utc_date, chat_id)
                )"""
            )

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    @staticmethod
    def _ledger_chat_id(chat_id: str, bot_name: str) -> str:
        # Preserve the original key for the default bot so existing ledgers
        # remain idempotent after upgrading. Named bots use a separator that
        # cannot occur in a validated Telegram chat ID.
        return str(chat_id) if bot_name in {"", "main"} else f"{bot_name}\x1f{chat_id}"

    def reserve(
        self,
        profile: str,
        utc_date: str,
        chat_id: str,
        *,
        bot_name: str = "main",
        force: bool = False,
    ) -> bool:
        ledger_chat_id = self._ledger_chat_id(chat_id, bot_name)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute(
                "SELECT status FROM deliveries WHERE profile=? AND utc_date=? AND chat_id=?",
                (profile, utc_date, ledger_chat_id),
            ).fetchone()
            if current and current[0] == "sent" and not force:
                return False
            connection.execute(
                "INSERT INTO deliveries(profile, utc_date, chat_id, status, error, updated_at) VALUES (?, ?, ?, 'sending', NULL, ?) "
                "ON CONFLICT(profile, utc_date, chat_id) DO UPDATE SET status='sending', error=NULL, updated_at=excluded.updated_at",
                (profile, utc_date, ledger_chat_id, self._now()),
            )
            return True

    def mark_sent(self, profile: str, utc_date: str, chat_id: str, *, bot_name: str = "main") -> None:
        ledger_chat_id = self._ledger_chat_id(chat_id, bot_name)
        with self._connect() as connection:
            connection.execute(
                "UPDATE deliveries SET status='sent', error=NULL, updated_at=? WHERE profile=? AND utc_date=? AND chat_id=?",
                (self._now(), profile, utc_date, ledger_chat_id),
            )

    def mark_failed(
        self,
        profile: str,
        utc_date: str,
        chat_id: str,
        error_message: str,
        *,
        bot_name: str = "main",
    ) -> None:
        ledger_chat_id = self._ledger_chat_id(chat_id, bot_name)
        with self._connect() as connection:
            connection.execute(
                "UPDATE deliveries SET status='failed', error=?, updated_at=? WHERE profile=? AND utc_date=? AND chat_id=?",
                (str(error_message)[:500], self._now(), profile, utc_date, ledger_chat_id),
            )

    def status(self, profile: str, utc_date: str, chat_id: str, *, bot_name: str = "main") -> str | None:
        ledger_chat_id = self._ledger_chat_id(chat_id, bot_name)
        with self._connect() as connection:
            row = connection.execute(
                "SELECT status FROM deliveries WHERE profile=? AND utc_date=? AND chat_id=?",
                (profile, utc_date, ledger_chat_id),
            ).fetchone()
        return str(row[0]) if row else None
