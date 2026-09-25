"""Time window resolution for PCP historical queries.

Fills in omitted start/end/interval to return roughly TARGET_SAMPLES rows.
When all three are supplied, the request is honored verbatim.
All functions are pure; pass "now" in the target system's timezone.
"""

import re
import typing as t

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

_OFFSET_RE = re.compile(r"^(?P<sign>[-+])\s*(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>[a-z]*)$", re.IGNORECASE)

# Bare clock times, the one absolute form fromisoformat rejects.
_TIME_ONLY_FORMATS = ("%H:%M:%S", "%H:%M")

# PCP tools need "@" prefix and UTC zone to resolve ambiguity. The grammar
# has no sub-second field; pmrep rejects a fraction at any precision.
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


class PCPTimeWindow(BaseModel):
    """Resolved pmrep arguments for a query window.

    ``end`` is None when the window is pinned by ``samples`` instead, because
    pmrep recalculates a supplied interval if given both --finish and
    --samples.
    """

    model_config = ConfigDict(frozen=True)

    start: str
    end: str | None
    interval: str
    samples: int | None


def parse_duration(spec: str) -> timedelta:
    """Parse a PCP-style duration such as "30", "10seconds", or "5m".

    A bare number is interpreted as seconds, matching PCP's own convention.

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
    """Parse "now", an offset like "-2hours", or a timestamp into a datetime.

    Anything the spec leaves out - the offset, the date - is taken from
    ``now``, which the caller sets to the target system's clock.

    Raises:
        ValueError: If the string is not a recognised time specification.
    """
    text = spec.strip()
    if not text:
        raise ValueError("Time specification cannot be empty")

    if text.lower() == "now":
        return now

    offset = _OFFSET_RE.match(text)
    if offset is not None:
        delta = parse_duration(f"{offset['value']}{offset['unit']}")
        base = now.astimezone(timezone.utc)
        shifted = base - delta if offset["sign"] == "-" else base + delta
        return shifted.astimezone(now.tzinfo)

    text = text.removeprefix("@").strip()

    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        pass
    else:
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=now.tzinfo)

    for time_format in _TIME_ONLY_FORMATS:
        try:
            parsed = datetime.strptime(text, time_format)
        except ValueError:
            continue
        return parsed.replace(year=now.year, month=now.month, day=now.day, tzinfo=now.tzinfo)

    raise ValueError(
        f"Invalid time specification: {spec!r}. Use 'now', an offset like '-2hours', or 'YYYY-MM-DD HH:MM:SS'."
    )


def resolve_pcp_window(
    start_time: str | None,
    end_time: str | None,
    interval: str | None,
    now: datetime | None = None,
) -> PCPTimeWindow:
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

    if start_time and end_time and interval:
        parse_duration(interval)
        start = _parse_utc(start_time, now)
        end = _parse_utc(end_time, now)
        _check_order(start, end)
        return PCPTimeWindow(start=to_pcp_time(start), end=to_pcp_time(end), interval=interval, samples=None)

    start = _parse_utc(start_time, now) if start_time else None
    end = _parse_utc(end_time, now) if end_time else None

    if interval:
        interval_delta = parse_duration(interval)
        if start is None:
            start = (end or now_utc) - interval_delta * (TARGET_SAMPLES - 1)
        return PCPTimeWindow(start=to_pcp_time(start), end=None, interval=interval, samples=TARGET_SAMPLES)

    if start is None and end is None:
        end = now_utc
    if start is None:
        start = t.cast(datetime, end) - DEFAULT_TIMESPAN
    elif end is None:
        end = start + DEFAULT_TIMESPAN

    end = t.cast(datetime, end)
    _check_order(start, end)

    return PCPTimeWindow(
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
        if seconds < threshold:
            return f"{threshold // _UNIT_DIVISORS[unit]}{unit}"

    return f"{int(seconds // 86400) + 1}day"
