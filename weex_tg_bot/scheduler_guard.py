from __future__ import annotations

from datetime import datetime, timezone
import errno
import json
import logging
import os
from pathlib import Path
from typing import TextIO

from .config import default_config_dir


LOGGER = logging.getLogger(__name__)


def default_scheduler_lock_path() -> Path:
    return default_config_dir() / "scheduler.lock"


def _lock_file(handle: TextIO) -> None:
    if os.name == "nt":
        import msvcrt

        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            if exc.errno in {errno.EACCES, errno.EAGAIN, errno.EDEADLK}:
                raise BlockingIOError from exc
            raise
        return

    import fcntl

    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        if exc.errno in {errno.EACCES, errno.EAGAIN}:
            raise BlockingIOError from exc
        raise


def _unlock_file(handle: TextIO) -> None:
    if os.name == "nt":
        import msvcrt

        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            LOGGER.debug("scheduler lock was already released", exc_info=True)
        return

    import fcntl

    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


class SchedulerInstanceLock:
    """Own the process-wide scheduler slot for the lifetime of a process.

    The lock is advisory and automatically released by the operating system if
    the owning process exits or crashes. The lock file is deliberately kept on
    disk so all launch paths can use the same stable path without stale-PID
    cleanup.
    """

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path or default_scheduler_lock_path()).expanduser()
        self._handle: TextIO | None = None

    @property
    def acquired(self) -> bool:
        return self._handle is not None

    def acquire(self) -> bool:
        if self.acquired:
            return True
        handle: TextIO | None = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            handle = self.path.open("a+", encoding="utf-8")
            # Windows requires a byte-sized region for msvcrt.locking().
            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(" ")
                handle.flush()
            handle.seek(0)
            _lock_file(handle)
        except BlockingIOError:
            if handle is not None:
                handle.close()
            return False
        except OSError:
            LOGGER.warning("unable to acquire scheduler lock at %s", self.path, exc_info=True)
            if handle is not None:
                handle.close()
            return False

        assert handle is not None
        self._handle = handle
        try:
            handle.seek(0)
            handle.truncate()
            json.dump(
                {
                    "pid": os.getpid(),
                    "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                },
                handle,
            )
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
            try:
                self.path.chmod(0o600)
            except OSError:
                LOGGER.debug("unable to set scheduler lock permissions", exc_info=True)
        except OSError:
            self.release()
            LOGGER.warning("unable to initialize scheduler lock at %s", self.path, exc_info=True)
            return False
        return True

    def release(self) -> None:
        handle = self._handle
        self._handle = None
        if handle is None:
            return
        try:
            _unlock_file(handle)
        finally:
            handle.close()

    def __enter__(self) -> "SchedulerInstanceLock":
        if not self.acquire():
            raise RuntimeError("another scheduler instance is already active")
        return self

    def __exit__(self, _exc_type, _exc_value, _traceback) -> None:
        self.release()
