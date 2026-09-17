import tempfile
import unittest
from pathlib import Path

from weex_tg_bot.discovery import discover_commission_filters, discover_saved_profiles, discover_skill_roots


class SkillDiscoveryTests(unittest.TestCase):
    def test_discovers_partner_skill_root_without_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "skills"
            cli = root / "weex-partner-skill" / "scripts" / "weex_partner_cli.py"
            cli.parent.mkdir(parents=True)
            cli.write_text("# fixture", encoding="utf-8")
            self.assertEqual(discover_skill_roots(search_roots=(root,)), (str((root / "weex-partner-skill").resolve()),))

    def test_ignores_missing_candidates(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(discover_skill_roots(search_roots=(Path(directory),)), ())

    def test_reads_commission_filter_options_from_official_catalog(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = root / "references" / "partner-field-catalog.json"
            catalog.parent.mkdir(parents=True)
            catalog.write_text(
                '{"operations":{"get-commission":{"request_fields":['
                '{"wire_name":"coin","official_description_zh":"币种(USDT或BTC)"},'
                '{"wire_name":"product_type","official_description_zh":"SPOT或FUTURES"}]}}}',
                encoding="utf-8",
            )
            result = discover_commission_filters(root)
            self.assertEqual(result["coins"], ("USDT", "BTC"))
            self.assertEqual(result["products"], ("SPOT", "FUTURES"))

    def test_reads_saved_profile_names_from_trader_skill(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = root / "scripts" / "weex_profiles.py"
            script.parent.mkdir(parents=True)
            script.write_text(
                "import json; print(json.dumps({'profiles': [{'name': '合伙人'}, {'name': 'account 1'}]}))",
                encoding="utf-8",
            )
            self.assertEqual(discover_saved_profiles(trader_root=root), ("合伙人", "account 1"))


if __name__ == "__main__":
    unittest.main()
