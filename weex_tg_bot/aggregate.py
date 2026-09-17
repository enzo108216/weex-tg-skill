from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Sequence

from .models import RebateSummary


class AggregateError(ValueError):
    """Raised when a critical metric cannot be computed completely."""


_REQUIRED = {
    "coin", "fee", "commission", "sourceType", "takerAmount", "makerAmount",
}


def _decimal(record: Mapping[str, Any], field: str) -> Decimal:
    try:
        value = Decimal(str(record[field]))
    except (KeyError, InvalidOperation, TypeError, ValueError) as exc:
        raise AggregateError(f"record field {field} is missing or not a decimal") from exc
    if not value.is_finite() or value < 0:
        raise AggregateError(f"record field {field} must be a finite non-negative decimal")
    return value


def aggregate_records(
    records: Sequence[Mapping[str, Any]],
    *,
    utc_date: str,
    coin: str = "USDT",
    formula: str = "commission_minus_subaffiliate_commission",
    complete: bool = True,
    partial: bool = False,
    utc_start: str = "",
    utc_end: str = "",
) -> RebateSummary:
    if not complete or partial:
        raise AggregateError("Partner result is not complete; delivery is blocked")
    expected_coin = str(coin).upper()
    if not records:
        zeros = Decimal("0")
        return RebateSummary(utc_date, expected_coin, zeros, zeros, zeros, zeros, zeros, formula, utc_start, utc_end)
    volume = fee = commission = sub_commission = Decimal("0")
    for index, record in enumerate(records):
        if not isinstance(record, Mapping):
            raise AggregateError(f"record {index} is not an object")
        missing = sorted(_REQUIRED - set(record))
        if missing:
            raise AggregateError(f"record {index} is missing fields: {', '.join(missing)}")
        record_coin = str(record["coin"]).upper()
        if record_coin != expected_coin:
            raise AggregateError(f"mixed or unexpected coin in record {index}: {record_coin}")
        try:
            source_type = int(record["sourceType"])
        except (TypeError, ValueError) as exc:
            raise AggregateError(f"record {index} has invalid sourceType") from exc
        if source_type not in {1, 2}:
            raise AggregateError(f"record {index} has unknown sourceType {source_type}")
        taker = _decimal(record, "takerAmount")
        maker = _decimal(record, "makerAmount")
        row_fee = _decimal(record, "fee")
        row_commission = _decimal(record, "commission")
        volume += taker + maker
        fee += row_fee
        commission += row_commission
        if source_type == 2:
            sub_commission += row_commission
    if formula == "commission_minus_subaffiliate_commission":
        final_income = commission - sub_commission
    elif formula == "commission":
        final_income = commission
    else:
        raise AggregateError(f"unsupported final income formula: {formula}")
    return RebateSummary(
        utc_date=utc_date,
        coin=expected_coin,
        trading_volume=volume,
        fee=fee,
        commission=commission,
        sub_affiliate_commission=sub_commission,
        final_income=final_income,
        formula=formula,
        utc_start=utc_start,
        utc_end=utc_end,
    )
