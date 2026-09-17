import unittest
from datetime import date

from weex_tg_bot.periods import previous_natural_period


class PeriodTests(unittest.TestCase):
    def test_previous_day_excludes_reference_day(self):
        window = previous_natural_period("1d", date(2026, 9, 16))
        self.assertEqual((window.start, window.end), (date(2026, 9, 15), date(2026, 9, 15)))

    def test_previous_week_is_complete_monday_to_sunday(self):
        window = previous_natural_period("1w", date(2026, 9, 16))
        self.assertEqual((window.start, window.end), (date(2026, 9, 7), date(2026, 9, 13)))

    def test_previous_month_and_year_are_complete_periods(self):
        month = previous_natural_period("1m", date(2026, 9, 16))
        year = previous_natural_period("1y", date(2026, 9, 16))
        self.assertEqual((month.start, month.end), (date(2026, 8, 1), date(2026, 8, 31)))
        self.assertEqual((year.start, year.end), (date(2025, 1, 1), date(2025, 12, 31)))

    def test_previous_custom_days_excludes_reference_day(self):
        window = previous_natural_period("3d", date(2026, 9, 16), "2026-09-01")
        self.assertEqual((window.start, window.end), (date(2026, 9, 13), date(2026, 9, 15)))

    def test_custom_days_has_no_window_before_first_cycle_ends(self):
        with self.assertRaises(ValueError):
            previous_natural_period("3d", date(2026, 9, 3), "2026-09-01")


if __name__ == "__main__":
    unittest.main()
