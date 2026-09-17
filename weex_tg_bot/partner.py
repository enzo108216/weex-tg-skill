from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, time, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time as sleep_time
from typing import Any, Callable, Mapping

from .models import QueryConfig


WEEX_SKILL_REPOSITORY_URL = "https://github.com/weex-labs/weex-agent-skills"


class PartnerQueryError(RuntimeError):
    """Raised when a Partner query cannot produce a complete safe result."""


def records_from_partner_envelopes(payload: Any) -> list[Mapping[str, Any]]:
    """Extract records from one or more already executed Partner-skill results.

    This is the hand-off boundary used when `$weex-partner-skill` performs the
    query and this skill performs only aggregation and Telegram delivery.
    """
    if isinstance(payload, Mapping) and isinstance(payload.get("results"), list):
        envelopes = payload["results"]
    elif isinstance(payload, list):
        envelopes = payload
    else:
        envelopes = [payload]
    records: list[Mapping[str, Any]] = []
    for index, envelope in enumerate(envelopes):
        if not isinstance(envelope, Mapping):
            raise PartnerQueryError(f"Partner result {index} is not an object")
        if envelope.get("ok") is not True or envelope.get("complete") is not True or envelope.get("partial") is True:
            error = envelope.get("error") if isinstance(envelope.get("error"), Mapping) else {}
            raise PartnerQueryError(str(error.get("message") or f"Partner result {index} is incomplete"))
        batch = envelope.get("records")
        if not isinstance(batch, list) or any(not isinstance(item, Mapping) for item in batch):
            raise PartnerQueryError(f"Partner result {index} records are not objects")
        records.extend(batch)
    return records


def _utc_stamp(value: datetime) -> str:
    normalized = value.astimezone(timezone.utc)
    timespec = "milliseconds" if normalized.microsecond else "seconds"
    return normalized.isoformat(timespec=timespec).replace("+00:00", "Z")


def build_commission_requests(profile: str, utc_date: date, query: QueryConfig) -> list[dict[str, Any]]:
    return build_commission_range_requests(profile, utc_date, utc_date, query)


def _add_months(value: date, months: int) -> date:
    index = value.year * 12 + (value.month - 1) + months
    year, month_index = divmod(index, 12)
    month = month_index + 1
    return date(year, month, 1)


def _range_segments(start: date, end: date) -> list[tuple[date, date]]:
    if start > end:
        raise PartnerQueryError("query start must not be after query end")
    segments: list[tuple[date, date]] = []
    current = start
    while current <= end:
        segment_month_end = _add_months(current.replace(day=1), 2)
        segment_end = date(
            segment_month_end.year,
            segment_month_end.month,
            monthrange(segment_month_end.year, segment_month_end.month)[1],
        )
        bounded_end = min(segment_end, end)
        segments.append((current, bounded_end))
        current = bounded_end + timedelta(days=1)
    return segments


def build_commission_range_requests(
    profile: str,
    start_date: date,
    end_date: date,
    query: QueryConfig,
) -> list[dict[str, Any]]:
    if not str(profile or "").strip():
        raise PartnerQueryError("saved WEEX profile is required")
    requests: list[dict[str, Any]] = []
    for segment_start, segment_end in _range_segments(start_date, end_date):
        start = datetime.combine(segment_start, time.min, timezone.utc)
        end = datetime.combine(segment_end, time.max, timezone.utc).replace(microsecond=999000)
        for product_type in query.product_types:
            requests.append(
                {
                    "operation": "get-commission",
                    "profile": profile,
                    "language": "en",
                    "scope": dict(query.scope),
                    "time_range": {"start": _utc_stamp(start), "end": _utc_stamp(end)},
                    "filters": {"coin": query.coin, "product_type": product_type},
                    "result_mode": "complete_list",
                }
            )
    return requests


class PartnerClient:
    def __init__(
        self,
        skill_root: str | Path | None = None,
        *,
        runner: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None,
        python_executable: str | None = None,
        timeout: int = 120,
        retry_attempts: int = 2,
    ) -> None:
        self.skill_root = Path(skill_root).expanduser() if skill_root else None
        self.runner = runner
        self.python_executable = python_executable or sys.executable
        self.timeout = timeout
        self.retry_attempts = max(0, int(retry_attempts))

    def _script(self) -> Path:
        if self.skill_root and self.skill_root.suffix == ".py":
            candidate = self.skill_root
        elif self.skill_root:
            candidate = self.skill_root / "skills" / "weex-partner-skill" / "scripts" / "weex_partner_cli.py"
            if not candidate.exists():
                candidate = self.skill_root / "scripts" / "weex_partner_cli.py"
        else:
            candidates = []
            explicit = os.environ.get("WEEX_PARTNER_CLI")
            if explicit:
                candidates.append(Path(explicit).expanduser())
            installed_root = os.environ.get("WEEX_AGENT_SKILLS_ROOT")
            if installed_root:
                root = Path(installed_root).expanduser()
                candidates.extend(
                    [
                        root / "skills" / "weex-partner-skill" / "scripts" / "weex_partner_cli.py",
                        root / "scripts" / "weex_partner_cli.py",
                    ]
                )
            home = Path.home()
            candidates.extend(
                [
                    home / ".codex" / "skills" / "weex-partner-skill" / "scripts" / "weex_partner_cli.py",
                    home / ".codex" / "skills" / "weex-agent-skills" / "skills" / "weex-partner-skill" / "scripts" / "weex_partner_cli.py",
                ]
            )
            candidate = next((item for item in candidates if item.is_file()), Path("weex_partner_cli.py"))
        if not candidate.is_file():
            raise PartnerQueryError(
                "Installed weex-partner-skill CLI was not found; set WEEX_PARTNER_CLI "
                "or configure --skill-root"
            )
        return candidate

    def _run(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        if self.runner is not None:
            result = self.runner(payload)
            if not isinstance(result, Mapping):
                raise PartnerQueryError("Partner runner returned a non-object")
            return result
        request_data = json.dumps(payload, ensure_ascii=False)
        operation = str(payload.get("operation") or "get-commission")
        last_error: Exception | None = None
        for attempt in range(self.retry_attempts + 1):
            try:
                completed = subprocess.run(
                    [self.python_executable, str(self._script()), operation, "--request-file", "-"],
                    input=request_data,
                    text=True,
                    capture_output=True,
                    timeout=self.timeout,
                    check=False,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                last_error = exc
                if attempt < self.retry_attempts:
                    sleep_time.sleep(0.5 * (attempt + 1))
                    continue
                raise PartnerQueryError("Partner skill process failed or timed out") from exc
            try:
                response = json.loads(completed.stdout)
            except json.JSONDecodeError as exc:
                last_error = exc
                if attempt < self.retry_attempts:
                    sleep_time.sleep(0.5 * (attempt + 1))
                    continue
                raise PartnerQueryError("Partner skill returned invalid JSON") from exc
            if not isinstance(response, Mapping):
                raise PartnerQueryError("Partner skill returned a non-object JSON value")
            error = response.get("error") if isinstance(response.get("error"), Mapping) else {}
            if response.get("ok") is False and error.get("category") == "transport" and attempt < self.retry_attempts:
                sleep_time.sleep(0.5 * (attempt + 1))
                continue
            if completed.returncode != 0 and response.get("ok") is not False:
                raise PartnerQueryError("Partner skill exited unsuccessfully")
            return response
        raise PartnerQueryError("Partner skill transport failed") from last_error

    def fetch_records(self, profile: str, utc_date: date, query: QueryConfig) -> list[Mapping[str, Any]]:
        return self.fetch_records_for_range(profile, utc_date, utc_date, query)

    def fetch_records_for_range(
        self,
        profile: str,
        start_date: date,
        end_date: date,
        query: QueryConfig,
    ) -> list[Mapping[str, Any]]:
        if query.scope.get("mode") == "all" and query.scope.get("all_confirmed") is not True:
            raise PartnerQueryError("all-referrals scope requires explicit all_confirmed=true")
        records: list[Mapping[str, Any]] = []
        for payload in build_commission_range_requests(profile, start_date, end_date, query):
            response = self._run(payload)
            if response.get("ok") is not True or response.get("complete") is not True or response.get("partial") is True:
                error = response.get("error") if isinstance(response.get("error"), Mapping) else {}
                message = str(error.get("message") or "Partner result was incomplete")
                raise PartnerQueryError(message)
            batch = response.get("records")
            if not isinstance(batch, list) or any(not isinstance(item, Mapping) for item in batch):
                raise PartnerQueryError("Partner result records are not a list of objects")
            records.extend(batch)
        return records

    def fetch_referral_uids(self, profile: str) -> list[int]:
        """Load complete referral UID options through the official Partner skill."""
        payload = {
            "operation": "list-referral-uids",
            "profile": profile,
            "language": "en",
            "scope": {"mode": "all", "all_confirmed": True},
            "result_mode": "complete_list",
        }
        response = self._run(payload)
        if response.get("ok") is not True or response.get("complete") is not True or response.get("partial") is True:
            error = response.get("error") if isinstance(response.get("error"), Mapping) else {}
            raise PartnerQueryError(str(error.get("message") or "Partner referral UID result was incomplete"))
        records = response.get("records")
        if not isinstance(records, list) or any(not isinstance(item, Mapping) for item in records):
            raise PartnerQueryError("Partner referral UID records are invalid")
        values: list[int] = []
        for record in records:
            try:
                uid = int(str(record["uid"]))
            except (KeyError, TypeError, ValueError) as exc:
                raise PartnerQueryError("Partner referral UID record is invalid") from exc
            if uid > 0 and uid not in values:
                values.append(uid)
        return sorted(values)
