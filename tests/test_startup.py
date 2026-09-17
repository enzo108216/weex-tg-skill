import os
from pathlib import Path
import tempfile
import unittest

from weex_tg_bot.startup import (
    build_launcher,
    install_launcher,
    launcher_path,
    remove_launcher,
)


class StartupLauncherTests(unittest.TestCase):
    def test_macos_autostart_is_a_launch_agent_for_headless_scheduler(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            path = install_launcher(
                target="autostart",
                system_name="Darwin",
                home=home,
                executable="/usr/bin/python3",
                working_directory=Path("/workspace/weex-tg-skill"),
                command_mode="scheduler",
            )
            self.assertEqual(path, home / "Library/LaunchAgents/com.weex.tg.skill.scheduler.plist")
            payload = path.read_text(encoding="utf-8")
            self.assertIn("com.weex.tg.skill.scheduler", payload)
            self.assertIn("weex_tg_bot", payload)
            self.assertIn("run", payload)
            self.assertIn("<key>SuccessfulExit</key>", payload)

    def test_desktop_launcher_requires_gui_and_starts_gui_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            path = install_launcher(
                target="desktop",
                system_name="Darwin",
                home=home,
                desktop=home / "Desktop",
                executable="/usr/bin/python3",
                working_directory=Path("/workspace/weex-tg-skill"),
                command_mode="gui",
            )
            self.assertEqual(path, home / "Desktop/WEEX Telegram Push.command")
            self.assertTrue(os.access(path, os.X_OK))
            self.assertIn("weex_tg_bot gui --language auto", path.read_text(encoding="utf-8"))

    def test_remove_launcher_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            path = install_launcher(
                target="desktop",
                system_name="Linux",
                home=home,
                desktop=home / "Desktop",
                executable="/usr/bin/python3",
                working_directory=Path("/workspace/weex-tg-skill"),
                command_mode="gui",
            )
            self.assertTrue(remove_launcher(path))
            self.assertFalse(remove_launcher(path))

    def test_launcher_path_matches_platform(self):
        home = Path("/tmp/weex-home")
        self.assertTrue(str(launcher_path("Linux", "autostart", home)).endswith(".config/autostart/weex-tg-skill.desktop"))
        self.assertTrue(str(launcher_path("Windows", "desktop", home)).endswith("Desktop/WEEX Telegram Push.cmd"))


if __name__ == "__main__":
    unittest.main()
