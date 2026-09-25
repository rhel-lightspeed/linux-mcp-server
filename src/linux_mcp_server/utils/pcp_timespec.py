"""Time window resolution for PCP historical queries.

Fills in omitted start/end/interval to return roughly TARGET_SAMPLES rows.
When all three are supplied, the request is honored verbatim.
All functions are pure; pass "now" in the target system's timezone.
"""

import re

from datetime import datetime
from datetime import timedelta
from datetime import timezone

from pydantic import BaseModel
from pydantic import ConfigDict


#: Number of rows pmrep should return when the query is under-specified.
TARGET_SAMPLES = 20

#: Default window when neither start nor end is provided.
DEFAULT_TIMESPAN = timedelta(hours=1)

_UNIT_SECONDS: dict[str, int] = {
    "s": 1,
    "sec": 1,
    "secs": 1,
    "second": 1,
    "seconds": 1,
    "m": 60,
    "min": 60,
    "mins": 60,
    "minute": 60,
    "minutes": 60,
    "h": 3600,
    "hr": 3600,
    "hrs": 3600,
    "hour": 3600,
    "hours": 3600,
    "d": 86400,
    "day": 86400,
    "days": 86400,
}

_DURATION_RE = re.compile(r"^(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>[a-z]*)$", re.IGNORECASE)

# PCP tools need "@" prefix and UTC zone to resolve ambiguity. The grammar
_PCP_TIME_FORMAT = "@%Y-%m-%d %H:%M:%S UTC"


#: Convenient intervals to round a calculated interval up to.
_INTERVAL_LADDER: tuple[tuple[int, str], ...] = (
    (1, "sec"),
    (2, "sec"),
    (5, "sec"),
    (10, "sec"),
    (15, "sec"),
    (30, "sec"),
    (60, "min"),
    (120, "min"),
    (300, "min"),
    (600, "min"),
    (900, "min"),
    (1800, "min"),
    (3600, "hour"),
    (7200, "hour"),
    (10800, "hour"),
    (21600, "hour"),
    (43200, "hour"),
    (86400, "day"),
)

_UNIT_DIVISORS = {"sec": 1, "min": 60, "hour": 3600, "day": 86400}


class _PCPTimeWindow(BaseModel):
    """Resolved pmrep arguments for a query window"""

    model_config = ConfigDict(frozen=True)

    start: str
    end: str | None
    interval: str
    samples: int | None


def parse_duration(spec: str) -> timedelta:
    """Parse a PCP-style duration such as "30", "10seconds", or "5m".

    A bare number is interpreted as seconds, matching PCP's convention.

    Raises:
        ValueError: If the string is not a recognised duration.
    """
    match = _DURATION_RE.match(spec.strip())
    if match is None:
        raise ValueError(f"Invalid duration: {spec!r}")

    unit = match["unit"].lower() or "s"
    if unit not in _UNIT_SECONDS:
        raise ValueError(f"Unknown duration unit in {spec!r}. Use seconds, minutes, hours, or days.")

    seconds = float(match["value"]) * _UNIT_SECONDS[unit]
    if seconds <= 0:
        raise ValueError(f"Duration must be positive: {spec!r}")

    return timedelta(seconds=seconds)


def parse_time_spec(spec: str, now: datetime) -> datetime:
    """Parse a full calendar date and time, or "now", into a datetime.

    Timestamps without an offset use the timezone of ``now``, which the
    caller supplies in the target system's timezone.

    Raises:
        ValueError: If the string is not a recognised time specification.
    """
    text = spec.strip()
    if not text:
        raise ValueError("Time specification cannot be empty")

    if text.lower() == "now":
        return now

    text = text.removeprefix("@").strip()

    # fromisoformat also accepts bare dates, so require an explicit time first.
    if not re.match(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}", text):
        raise ValueError(
            f"Invalid time specification: {spec!r}. Use 'now' or a full date and time such as 'YYYY-MM-DD HH:MM:SS'."
        )

    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=now.tzinfo)


def resolve_pcp_window(
    start_time: str | None,
    end_time: str | None,
    interval: str | None,
    now: datetime | None = None,
) -> _PCPTimeWindow:
    """Fill in omitted start/end/interval to return roughly TARGET_SAMPLES rows.

    All three supplied = exact range, however many rows.

    Args:
        start_time: Start time or None.
        end_time: End time or None.
        interval: Sampling interval or None.
        now: Reference in target timezone. Defaults to local time.

    Raises:
        ValueError: Malformed time/duration or end <= start.
    """
    if now is None:
        now = datetime.now().astimezone()

    now_utc = now.astimezone(timezone.utc)

    if start_time is not None and end_time is not None and interval:
        parse_duration(interval)
        start = _parse_utc(start_time, now)
        end = _parse_utc(end_time, now)
        _check_order(start, end)
        return _PCPTimeWindow(start=to_pcp_time(start), end=to_pcp_time(end), interval=interval, samples=None)

    start = _parse_utc(start_time, now) if start_time is not None else None
    end = _parse_utc(end_time, now) if end_time is not None else None

    if interval:
        interval_delta = parse_duration(interval)
        if start is None:
            start = (end or now_utc) - interval_delta * (TARGET_SAMPLES - 1)
        return _PCPTimeWindow(start=to_pcp_time(start), end=None, interval=interval, samples=TARGET_SAMPLES)

    if start is None:
        if end is None:
            end = now_utc
        start = end - DEFAULT_TIMESPAN
    elif end is None:
        end = start + DEFAULT_TIMESPAN

    _check_order(start, end)

    return _PCPTimeWindow(
        start=to_pcp_time(start),
        end=to_pcp_time(end),
        interval=_round_interval((end - start) / TARGET_SAMPLES),
        samples=None,
    )


def to_pcp_time(moment: datetime) -> str:
    """Render an instant as an absolute PCP timestamp in UTC."""
    return moment.astimezone(timezone.utc).strftime(_PCP_TIME_FORMAT)


def _parse_utc(spec: str, now: datetime) -> datetime:
    """Parse ``spec`` against the target's clock and return it as a UTC instant."""
    return parse_time_spec(spec, now).astimezone(timezone.utc)


def _check_order(start: datetime, end: datetime) -> None:
    """Reject a window whose end does not come after its start."""
    if end <= start:
        raise ValueError(f"End time ({end.isoformat()}) must be after start time ({start.isoformat()})")


def _round_interval(delta: timedelta) -> str:
    """Round a calculated interval up to the next convenient value."""
    seconds = delta.total_seconds()

    for threshold, unit in _INTERVAL_LADDER:
        if seconds <= threshold:
            return f"{threshold // _UNIT_DIVISORS[unit]}{unit}"

    return f"{int(seconds // 86400) + 1}day"
