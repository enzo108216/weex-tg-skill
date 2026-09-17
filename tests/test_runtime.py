import tempfile
import unittest
from pathlib import Path

from weex_tg_bot.runtime import (
    build_runtime_preflight,
    managed_python_path,
    managed_runtime_setup_command,
)


class RuntimeTests(unittest.TestCase):
    def test_preflight_reports_missing_managed_runtime_without_installing(self):
        with tempfile.TemporaryDirectory() as directory:
            report = build_runtime_preflight(Path(directory))
            self.assertFalse(report["ready"])
            self.assertTrue(report["requires_install"])
            self.assertEqual(report["reason"], "managed_runtime_missing")

    def test_setup_command_requires_explicit_acceptance(self):
        self.assertIn("--accept-managed-runtime", managed_runtime_setup_command("Darwin"))
        self.assertIn("--accept-managed-runtime", managed_runtime_setup_command("Windows"))

    def test_managed_python_path_is_platform_specific(self):
        with tempfile.TemporaryDirectory() as directory:
            path = managed_python_path(Path(directory), system_name="Darwin")
            self.assertEqual(path, Path(directory) / "venv" / "bin" / "python")


if __name__ == "__main__":
    unittest.main()
