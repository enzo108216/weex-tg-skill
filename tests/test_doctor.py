import unittest

from weex_tg_bot.doctor import build_report


class DoctorTests(unittest.TestCase):
    def test_recommends_gui_when_desktop_tk_and_keyring_are_ready(self):
        report = build_report(
            system_name="Darwin",
            tkinter_importable=True,
            desktop_available=True,
            keyring_available=True,
            managed_runtime_ready=True,
        )
        self.assertEqual(report["recommendation"], "gui")
        self.assertTrue(report["gui_ready"])

    def test_recommends_command_when_gui_prerequisites_are_missing(self):
        report = build_report(
            system_name="Windows",
            tkinter_importable=False,
            desktop_available=True,
            keyring_available=False,
            managed_runtime_ready=False,
        )
        self.assertEqual(report["recommendation"], "command")
        self.assertFalse(report["gui_ready"])
        self.assertTrue(report["reasons"])

    def test_linux_headless_session_recommends_command(self):
        report = build_report(
            system_name="Linux",
            tkinter_importable=True,
            desktop_available=False,
            keyring_available=True,
            managed_runtime_ready=False,
        )
        self.assertEqual(report["recommendation"], "command")

    def test_recommends_gui_install_when_desktop_is_ready_but_venv_is_missing(self):
        report = build_report(
            system_name="Darwin",
            tkinter_importable=True,
            desktop_available=True,
            keyring_available=True,
            managed_runtime_ready=False,
        )
        self.assertEqual(report["recommendation"], "gui-install")

    def test_keyring_is_not_required_for_gui_when_sqlite_storage_is_used(self):
        report = build_report(
            system_name="Darwin",
            tkinter_importable=True,
            desktop_available=True,
            keyring_available=False,
            managed_runtime_ready=True,
        )
        self.assertTrue(report["gui_capable"])
        self.assertTrue(report["gui_ready"])
        self.assertEqual(report["recommendation"], "gui")
        self.assertEqual(report["token_storage"], "sqlite")


if __name__ == "__main__":
    unittest.main()
