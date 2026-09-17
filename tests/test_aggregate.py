import unittest
from decimal import Decimal

from weex_tg_bot.aggregate import AggregateError, aggregate_records


def record(**overrides):
    value = {
        "uid": 1,
        "date": 1710000000000,
        "coin": "USDT",
        "fee": "3.50",
        "commission": "2.00",
        "sourceType": 1,
        "takerAmount": "100",
        "makerAmount": "50",
        "productType": "SPOT",
    }
    value.update(overrides)
    return value


class AggregateTests(unittest.TestCase):
    def test_calculates_all_daily_metrics_with_decimal_formula(self):
        summary = aggregate_records(
            [
                record(),
                record(
                    uid=2,
                    sourceType=2,
                    fee="1.25",
                    commission="0.75",
                    takerAmount="10.2",
                    makerAmount="0.3",
                ),
            ],
            utc_date="2026-09-15",
        )
        self.assertEqual(summary.trading_volume, Decimal("160.5"))
        self.assertEqual(summary.fee, Decimal("4.75"))
        self.assertEqual(summary.commission, Decimal("2.75"))
        self.assertEqual(summary.sub_affiliate_commission, Decimal("0.75"))
        self.assertEqual(summary.final_income, Decimal("2.00"))

    def test_missing_required_field_fails_closed(self):
        item = record()
        del item["fee"]
        with self.assertRaises(AggregateError):
            aggregate_records([item], utc_date="2026-09-15")

    def test_partial_and_mixed_coin_data_are_rejected(self):
        with self.assertRaises(AggregateError):
            aggregate_records([record()], utc_date="2026-09-15", complete=False)
        with self.assertRaises(AggregateError):
            aggregate_records([record(coin="BTC")], utc_date="2026-09-15")

    def test_unknown_source_type_and_invalid_amount_are_rejected(self):
        with self.assertRaises(AggregateError):
            aggregate_records([record(sourceType=9)], utc_date="2026-09-15")
        with self.assertRaises(AggregateError):
            aggregate_records([record(fee="not-a-number")], utc_date="2026-09-15")


if __name__ == "__main__":
    unittest.main()
