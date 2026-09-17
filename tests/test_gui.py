import unittest

from weex_tg_bot.gui import detect_language, filter_timezones, merge_schedule_entries, period_label, remap_task_chat_id, resolve_push_times, resolve_timezone_query, text_for
from weex_tg_bot.models import PushTaskConfig
from weex_tg_bot.i18n import is_rtl, normalize_locale, translate


class GuiLanguageTests(unittest.TestCase):
    def test_explicit_language_is_normalized(self):
        self.assertEqual(detect_language("zh"), "zh")
        self.assertEqual(detect_language("en"), "en")
        self.assertEqual(detect_language("unknown"), "en")

    def test_translation_has_both_supported_languages(self):
        self.assertEqual(text_for("overview", "zh"), "概览")
        self.assertEqual(text_for("overview", "en"), "Overview")

    def test_internal_period_codes_are_rendered_as_localized_labels(self):
        self.assertIn("自然日", period_label("1d", "zh_cn"))
        self.assertIn("day", period_label("3d", "en_us").lower())

    def test_timezone_filter_is_case_insensitive_and_substring_based(self):
        values = ("Asia/Shanghai", "Asia/Tokyo", "Europe/London")
        self.assertEqual(filter_timezones(values, "asia/sha"), ("Asia/Shanghai",))
        self.assertEqual(filter_timezones(values, "LONDON"), ("Europe/London",))
        self.assertEqual(filter_timezones(values, ""), values)
        self.assertEqual(resolve_timezone_query(values, "UTC", "Shanghai"), "Asia/Shanghai")

    def test_editing_single_push_time_replaces_the_default_time(self):
        self.assertEqual(resolve_push_times(("09:00",), "09:00", "10:30"), ("10:30",))
        self.assertEqual(resolve_push_times(("09:00", "18:00"), "09:00", "10:30"), ("09:00", "10:30", "18:00"))

    def test_editing_group_chat_id_remaps_saved_push_tasks(self):
        task = PushTaskConfig("task", "Task", "bot", "-1001", "profile")
        moved = remap_task_chat_id((task,), "-1001", "-1002")
        self.assertEqual(moved[0].chat_id, "-1002")

    def test_schedule_periods_are_multi_selectable_without_duplicates(self):
        self.assertEqual(
            merge_schedule_entries((("09:00", "1d"),), "09:00", ("1d", "1w")),
            (("09:00", "1d"), ("09:00", "1w")),
        )

    def test_locale_normalization_and_rtl(self):
        self.assertEqual(normalize_locale("zh-TW"), "zh_tw")
        self.assertTrue(is_rtl("fa_ir"))
        self.assertEqual(translate({"en_us": {"hello": "Hello"}}, "de", "hello"), "Hello")


if __name__ == "__main__":
    unittest.main()
