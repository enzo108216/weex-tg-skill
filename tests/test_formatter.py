import unittest
from decimal import Decimal

from weex_tg_bot.formatter import format_summary, localized_trigger
from weex_tg_bot.models import RebateSummary


class FormatterTests(unittest.TestCase):
    def test_custom_bot_and_group_names_are_rendered(self):
        summary = RebateSummary(
            utc_date="2026-09-15",
            coin="USDT",
            trading_volume=Decimal("0"),
            fee=Decimal("0"),
            commission=Decimal("0"),
            sub_affiliate_commission=Decimal("0"),
            final_income=Decimal("0"),
            formula="commission",
        )
        text = format_summary(
            summary,
            bot_name="返佣机器人",
            target_label="运营群",
        )
        self.assertIn("推送目标：返佣机器人 / 运营群", text)

    def test_english_message_uses_locale_file(self):
        summary = RebateSummary(
            utc_date="2026-09-15",
            coin="USDT",
            trading_volume=Decimal("1"),
            fee=Decimal("0"),
            commission=Decimal("2"),
            sub_affiliate_commission=Decimal("0"),
            final_income=Decimal("2"),
            formula="commission",
        )
        text = format_summary(summary, language="en", profile="account")
        self.assertIn("WEEX Rebate Summary", text)
        self.assertIn("Trading Volume: 1 USDT", text)

    def test_message_includes_query_context_and_metrics(self):
        summary = RebateSummary(
            utc_date="2026-09-15",
            utc_start="2026-09-15T00:00:00Z",
            utc_end="2026-09-15T23:59:59.999Z",
            coin="USDT",
            trading_volume=Decimal("123.45"),
            fee=Decimal("1.2"),
            commission=Decimal("8.5"),
            sub_affiliate_commission=Decimal("2.5"),
            final_income=Decimal("6"),
            formula="commission_minus_subaffiliate_commission",
        )

        text = format_summary(
            summary,
            trigger="手动查询",
            profile="合伙人",
            scope={"mode": "all", "all_confirmed": True},
            product_types=("SPOT", "FUTURES"),
            bot_name="main",
            target_label="my tg",
        )

        self.assertIn("WEEX 返佣统计", text)
        self.assertIn("触发方式：手动查询", text)
        self.assertIn("WEEX 账号：合伙人", text)
        self.assertIn("查询范围：全量下级（已确认）", text)
        self.assertIn("查询时间（UTC）：2026-09-15 00:00:00 至 2026-09-15 23:59:59.999", text)
        self.assertIn("产品类型：SPOT、FUTURES", text)
        self.assertIn("结算币种：USDT", text)
        self.assertIn("推送目标：main / my tg", text)
        self.assertIn("交易量（Trading Volume）：123.45 USDT", text)
        self.assertIn("最终收入（Final Income）：6 USDT", text)
        self.assertIn("Final Income = Commission - Sub-affiliate Commission", text)

    def test_uid_scope_is_rendered_without_exposing_internal_dict(self):
        summary = RebateSummary(
            utc_date="2026-09-15",
            coin="USDT",
            trading_volume=Decimal("0"),
            fee=Decimal("0"),
            commission=Decimal("0"),
            sub_affiliate_commission=Decimal("0"),
            final_income=Decimal("0"),
            formula="commission",
        )

        text = format_summary(
            summary,
            profile="account-a",
            scope={"mode": "uids", "uids": [10002, 10001]},
            product_types=("SPOT",),
            bot_name="ops",
            target_label="-1001",
        )

        self.assertIn("查询范围：指定下级 UID：10001、10002", text)
        self.assertNotIn("'mode'", text)
        self.assertNotIn("'uids'", text)

    def test_non_chinese_locale_uses_localized_trigger_and_uid_separator(self):
        summary = RebateSummary(
            utc_date="2026-09-15",
            coin="USDT",
            trading_volume=Decimal("0"),
            fee=Decimal("0"),
            commission=Decimal("0"),
            sub_affiliate_commission=Decimal("0"),
            final_income=Decimal("0"),
            formula="commission",
        )
        text = format_summary(
            summary,
            language="de",
            trigger=localized_trigger("de", "manual"),
            scope={"mode": "uids", "uids": [10002, 10001]},
        )
        self.assertIn("Manuelle", text)
        self.assertIn("10001, 10002", text)

    def test_scheduled_trigger_hides_internal_schedule_syntax(self):
        text = localized_trigger("zh_cn", "scheduled", "Asia/Shanghai:21:14=1d@-")
        self.assertIn("Asia/Shanghai 21:14", text)
        self.assertIn("上一完整自然日", text)
        self.assertNotIn("=1d@-", text)

    def test_time_range_separator_uses_locale_catalog(self):
        summary = RebateSummary(
            utc_date="2026-09-15",
            utc_start="2026-09-15T00:00:00Z",
            utc_end="2026-09-15T23:59:59.999Z",
            coin="USDT",
            trading_volume=Decimal("0"),
            fee=Decimal("0"),
            commission=Decimal("0"),
            sub_affiliate_commission=Decimal("0"),
            final_income=Decimal("0"),
            formula="commission",
        )
        text = format_summary(summary, language="th")
        self.assertIn(" ถึง ", text)
        self.assertNotIn(" 至 ", text)


if __name__ == "__main__":
    unittest.main()
