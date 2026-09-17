import tempfile
import unittest
from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock

from weex_tg_bot.scheduler import GuiScheduler
from weex_tg_bot.scheduler_guard import SchedulerInstanceLock


class SchedulerInstanceLockTests(unittest.TestCase):
    def test_lock_is_exclusive_and_reusable_after_release(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "scheduler.lock"
            first = SchedulerInstanceLock(path)
            second = SchedulerInstanceLock(path)
            self.assertTrue(first.acquire())
            self.assertFalse(second.acquire())
            first.release()
            self.assertTrue(second.acquire())
            second.release()

    def test_lock_is_exclusive_across_processes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "scheduler.lock"
            script = (
                "from pathlib import Path; import sys, time; "
                "from weex_tg_bot.scheduler_guard import SchedulerInstanceLock; "
                "lock = SchedulerInstanceLock(Path(sys.argv[1])); "
                "print(lock.acquire(), flush=True); time.sleep(10)"
            )
            process = subprocess.Popen(
                [sys.executable, "-c", script, str(path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            try:
                self.assertEqual(process.stdout.readline().strip(), "True")
                contender = SchedulerInstanceLock(path)
                self.assertFalse(contender.acquire())
            finally:
                process.terminate()
                process.wait(timeout=3)
                if process.stdout is not None:
                    process.stdout.close()
                if process.stderr is not None:
                    process.stderr.close()
            self.assertTrue(contender.acquire())
            contender.release()

    def test_gui_scheduler_skips_when_another_instance_holds_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "scheduler.lock"
            owner = SchedulerInstanceLock(path)
            self.assertTrue(owner.acquire())
            try:
                scheduler = GuiScheduler(object(), interval_seconds=5, lock_path=path)
                scheduler._run_due_tasks = Mock()
                scheduler.start()
                scheduler.join(timeout=1)
                self.assertFalse(scheduler.is_alive())
                self.assertTrue(scheduler.blocked_by_existing_instance)
                scheduler._run_due_tasks.assert_not_called()
            finally:
                owner.release()


if __name__ == "__main__":
    unittest.main()
