import json
import re
import unittest
from pathlib import Path

from weex_tg_bot.formatter import format_summary
from weex_tg_bot.i18n import is_rtl, load_locale_catalog, locale_options
from weex_tg_bot.models import PushTaskConfig, RebateSummary
from decimal import Decimal


LOCALE_DIR = Path(__file__).parents[1] / "weex_tg_bot" / "locales"
REQUIRED_LOCALES = {
    "en_us", "zh_cn", "zh_tw", "ko", "ja", "vi", "id", "th", "fa_ir", "ar",
    "tr", "de", "fr", "it", "es_es", "pt_pt", "pl", "ru", "uk", "az", "es_419",
    "es_ar", "pt_br",
}


class LocaleCatalogTests(unittest.TestCase):
    def test_every_requested_locale_is_discoverable_and_has_same_keys(self):
        catalog = load_locale_catalog()
        self.assertTrue(REQUIRED_LOCALES.issubset(catalog))
        keys = set(catalog["en_us"])
        self.assertGreaterEqual(len(keys), 140)
        for locale in REQUIRED_LOCALES:
            self.assertEqual(set(catalog[locale]), keys, locale)

    def test_format_placeholders_are_preserved(self):
        catalog = load_locale_catalog()
        source = catalog["en_us"]
        for locale in REQUIRED_LOCALES:
            for key, value in source.items():
                expected = set(re.findall(r"\{[^}]+\}", value))
                actual = set(re.findall(r"\{[^}]+\}", catalog[locale][key]))
                self.assertEqual(actual, expected, f"{locale}:{key}")

    def test_formatter_and_task_language_cover_every_locale(self):
        catalog = load_locale_catalog()
        summary = RebateSummary(
            utc_date="2026-09-15",
            coin="USDT",
            trading_volume=Decimal("1"),
            fee=Decimal("2"),
            commission=Decimal("3"),
            sub_affiliate_commission=Decimal("1"),
            final_income=Decimal("2"),
            formula="commission_minus_subaffiliate_commission",
        )
        for locale in REQUIRED_LOCALES:
            text = format_summary(
                summary,
                language=locale,
                profile="account",
                scope={"mode": "uids", "uids": [10001]},
                product_types=("SPOT",),
            )
            self.assertIn("10001", text, locale)
            self.assertNotIn("{uids}", text, locale)
            task = PushTaskConfig("task-" + locale, "Task", "bot", "-1001", "account", language=locale)
            self.assertEqual(task.language, locale)

    def test_rtl_catalogs_are_marked_rtl(self):
        self.assertTrue(is_rtl("ar"))
        self.assertTrue(is_rtl("fa_ir"))
        self.assertFalse(is_rtl("de"))

    def test_locale_options_use_native_names_and_hide_base_aliases(self):
        options = dict(locale_options(load_locale_catalog()))
        self.assertEqual(options["zh_cn"], "简体中文")
        self.assertEqual(options["de"], "Deutsch")
        self.assertEqual(options["ar"], "العربية")
        self.assertNotIn("en", options)
        self.assertNotIn("zh", options)
        self.assertNotIn("zh_cn", options.values())

    def test_help_body_documents_current_task_runtime_contract_for_every_locale(self):
        catalog = load_locale_catalog()
        for locale in REQUIRED_LOCALES:
            help_body = catalog[locale]["help_body"]
            self.assertIn("UTC", help_body, locale)
            self.assertIn("IANA", help_body, locale)
            self.assertIn("N", help_body, locale)
            self.assertIn("language", help_body.lower(), locale)


if __name__ == "__main__":
    unittest.main()
