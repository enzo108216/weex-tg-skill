from __future__ import annotations

from datetime import datetime, timezone
import logging
from pathlib import Path
import threading
from typing import Any

from .scheduler_guard import SchedulerInstanceLock


LOGGER = logging.getLogger(__name__)


class GuiScheduler(threading.Thread):
    """Poll configured push tasks while the GUI process is alive."""

    def __init__(
        self,
        store: Any,
        *,
        interval_seconds: int = 20,
        lock_path: Path | None = None,
    ) -> None:
        super().__init__(name="weex-tg-gui-scheduler", daemon=True)
        self.store = store
        self.interval_seconds = max(5, int(interval_seconds))
        self.lock_path = lock_path
        self._stop_event = threading.Event()
        self._sent_minute_keys: set[tuple[str, str, str, str, str, str]] = set()
        self._scheduler_lock: SchedulerInstanceLock | None = None
        self._blocked_by_existing_instance = threading.Event()

    @property
    def blocked_by_existing_instance(self) -> bool:
        return self._blocked_by_existing_instance.is_set()

    def stop(self) -> None:
        self._stop_event.set()

    def _run_due_tasks(self) -> None:
        # Import lazily to avoid a CLI/GUI import cycle during module startup.
        from .cli import _scheduled_tasks, _send_scheduled_task

        config = self.store.load()
        now = datetime.now(timezone.utc)
        minute = now.strftime("%Y-%m-%d %H:%M")
        for bot, group, schedule in _scheduled_tasks(config, now):
            key = (
                minute,
                bot.name,
                group.chat_id,
                schedule.schedule_time,
                schedule.period,
                schedule.timezone,
            )
            if key in self._sent_minute_keys:
                continue
            try:
                result_code = _send_scheduled_task(self.store, (bot, group, schedule), now)
            except Exception:
                LOGGER.exception("scheduled push failed for %s:%s", bot.name, group.chat_id)
                continue
            if result_code == 0:
                self._sent_minute_keys.add(key)
        if len(self._sent_minute_keys) > 2048:
            current_date = now.strftime("%Y-%m-%d")
            self._sent_minute_keys = {key for key in self._sent_minute_keys if key[0].startswith(current_date)}

    def run(self) -> None:
        scheduler_lock = SchedulerInstanceLock(self.lock_path)
        if not scheduler_lock.acquire():
            self._blocked_by_existing_instance.set()
            LOGGER.info("scheduler already active; GUI will not start another scheduler")
            return
        self._scheduler_lock = scheduler_lock
        try:
            while not self._stop_event.is_set():
                try:
                    self._run_due_tasks()
                except Exception:
                    LOGGER.exception("GUI scheduler loop failed")
                self._stop_event.wait(self.interval_seconds)
        finally:
            self._scheduler_lock = None
            scheduler_lock.release()
