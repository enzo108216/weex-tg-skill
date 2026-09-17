from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import re


PERIODS = {"1d", "1w", "1m", "1y"}


@dataclass(frozen=True)
class PeriodWindow:
    period: str
    start: date
    end: date

    @property
    def key(self) -> str:
        return f"{self.period}:{self.start.isoformat()}:{self.end.isoformat()}"


def previous_natural_period(period: str, reference_date: date, start_date: str | date | None = None) -> PeriodWindow:
    """Return the previous complete UTC natural period before reference_date."""
    period = str(period or "").strip().lower()
    custom_days = re.fullmatch(r"([1-9]\d*)d", period) if period not in PERIODS else None
    if custom_days:
        days = int(custom_days.group(1))
        if start_date is None:
            raise ValueError("custom Nd periods require start_date")
        anchor = date.fromisoformat(start_date) if isinstance(start_date, str) else start_date
        if reference_date <= anchor:
            raise ValueError("custom Nd period has no completed window yet")
        elapsed_days = (reference_date - anchor).days
        cycle_index = elapsed_days // days
        if cycle_index <= 0:
            raise ValueError("custom Nd period has no completed window yet")
        end = anchor + timedelta(days=cycle_index * days - 1)
        return PeriodWindow(period, end - timedelta(days=days - 1), end)
    if period not in PERIODS:
        raise ValueError("period must be 1d, 1w, 1m, 1y, or Nd")
    if period == "1d":
        end = reference_date - timedelta(days=1)
        return PeriodWindow(period, end, end)
    if period == "1w":
        current_week_start = reference_date - timedelta(days=reference_date.weekday())
        end = current_week_start - timedelta(days=1)
        return PeriodWindow(period, end - timedelta(days=6), end)
    if period == "1m":
        current_month_start = reference_date.replace(day=1)
        end = current_month_start - timedelta(days=1)
        return PeriodWindow(period, end.replace(day=1), end)
    current_year_start = reference_date.replace(month=1, day=1)
    end = current_year_start - timedelta(days=1)
    return PeriodWindow(period, end.replace(month=1, day=1), end)
