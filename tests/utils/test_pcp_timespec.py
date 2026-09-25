"""Tests for PCP time window resolution."""

import zoneinfo

from datetime import datetime
from datetime import timedelta
from datetime import timezone

import pytest

from linux_mcp_server.utils.pcp_timespec import DEFAULT_TIMESPAN
from linux_mcp_server.utils.pcp_timespec import parse_duration
from linux_mcp_server.utils.pcp_timespec import parse_time_spec
from linux_mcp_server.utils.pcp_timespec import resolve_pcp_window
from linux_mcp_server.utils.pcp_timespec import TARGET_SAMPLES
from linux_mcp_server.utils.pcp_timespec import to_pcp_time


NOW = datetime(2026, 9, 9, 18, 0, 0, tzinfo=timezone.utc)
NEW_YORK = zoneinfo.ZoneInfo("America/New_York")


class TestParseDuration:
    @pytest.mark.parametrize(
        ("spec", "expected"),
        [
            ("30", timedelta(seconds=30)),
            ("10seconds", timedelta(seconds=10)),
            ("5s", timedelta(seconds=5)),
            ("1minute", timedelta(minutes=1)),
            ("5 min", timedelta(minutes=5)),
            ("2hours", timedelta(hours=2)),
            ("1d", timedelta(days=1)),
            ("0.5h", timedelta(minutes=30)),
        ],
    )
    def test_valid(self, spec, expected):
        assert parse_duration(spec) == expected

    @pytest.mark.parametrize(
        ("spec", "message"),
        [
            ("", "Invalid duration"),
            ("soon", "Invalid duration"),
            ("invalid", "Invalid duration"),
            ("-5m", "Invalid duration"),
            ("1e3s", "Invalid duration"),
            ("0s", "Duration must be positive"),
            ("0m", "Duration must be positive"),
            ("5 fortnights", "Unknown duration unit"),
        ],
    )
    def test_invalid(self, spec, message):
        with pytest.raises(ValueError, match=message):
            parse_duration(spec)


class TestParseTimeSpec:
    """Only "now" and a full calendar date and time are accepted.

    Relative offsets, bare dates and bare clock times were all dropped: each
    resolves against a clock the caller cannot see, so a query silently
    covering the wrong window is easier to produce than to notice.
    """

    @pytest.mark.parametrize(
        ("spec", "expected"),
        [
            ("now", NOW),
            ("NOW", NOW),
            ("2026-08-14 14:00:00", datetime(2026, 8, 14, 14, 0, tzinfo=timezone.utc)),
            ("2026-08-14T14:00", datetime(2026, 8, 14, 14, 0, tzinfo=timezone.utc)),
            ("@2026-08-14 14:00:00", datetime(2026, 8, 14, 14, 0, tzinfo=timezone.utc)),
        ],
    )
    def test_valid(self, spec, expected):
        assert parse_time_spec(spec, NOW) == expected

    def test_empty_is_rejected(self):
        with pytest.raises(ValueError, match="Time specification cannot be empty"):
            parse_time_spec("", NOW)

    @pytest.mark.parametrize(
        "spec",
        [
            pytest.param("yesterday", id="prose"),
            pytest.param("2026", id="year-only"),
            pytest.param("10", id="bare-number"),
            # An argument smuggled in behind a newline must not reach pmrep.
            pytest.param("14:00:00\n--output-file=x", id="injected-option"),
            # Dropped forms: each would be resolved against an unseen clock.
            pytest.param("2026-08-14", id="bare-date"),
            pytest.param("20260814", id="compact-date"),
            pytest.param("2026-08-14T14", id="hour-without-minutes"),
            pytest.param("14:00:00", id="bare-time"),
            pytest.param("@14:00", id="prefixed-bare-time"),
            pytest.param("-2hours", id="relative-past"),
            pytest.param("-3days", id="relative-days"),
            pytest.param("+30m", id="relative-future"),
        ],
    )
    def test_rejected(self, spec):
        with pytest.raises(ValueError, match="Use 'now' or a full date and time"):
            parse_time_spec(spec, NOW)

    @pytest.mark.parametrize(
        "spec",
        [
            pytest.param("2026-13-01 14:00:00", id="month-13"),
            pytest.param("2026-02-30 14:00:00", id="february-30th"),
            pytest.param("2026-09-09 25:00:00", id="hour-25"),
        ],
    )
    def test_well_shaped_but_impossible_dates_are_rejected(self, spec):
        """These clear the shape check, so the calendar error has to surface.

        CPython words that error differently across the versions this project
        supports, so assert only that the failure is not our own shape check.
        """
        with pytest.raises(ValueError) as excinfo:
            parse_time_spec(spec, NOW)

        assert "Use 'now' or a full date and time" not in str(excinfo.value)


class TestResolvePcpWindow:
    """The eight cases from the time-window policy.

    Cases 2, 3 and 7 anchor on a caller-supplied interval, so they cap the
    result with --samples and leave --finish off. Every other case pins both
    ends of the window instead, so pmrep needs no cap. The two must never
    appear together: pmrep recalculates a supplied interval when given both.
    """

    def test_case_1_keeps_the_requested_range_and_spacing(self):
        window = resolve_pcp_window("2026-09-08 18:00:00", "2026-09-09 18:00:00", "1second", now=NOW)

        assert window.start == "@2026-09-08 18:00:00 UTC"
        assert window.end == "@2026-09-09 18:00:00 UTC"
        assert window.interval == "1second"
        assert window.samples is None

    def test_case_1_reads_bare_timestamps_in_the_target_timezone(self):
        now = datetime(2026, 9, 9, 14, 0, tzinfo=NEW_YORK)

        window = resolve_pcp_window("2026-09-09 09:00:00", "2026-09-09 11:00:00", "1min", now=now)

        assert window.start == "@2026-09-09 13:00:00 UTC"
        assert window.end == "@2026-09-09 15:00:00 UTC"
        assert window.interval == "1min"

    def test_case_2_start_and_interval_drops_the_end(self):
        window = resolve_pcp_window("2026-09-09 09:00:00", None, "5min", now=NOW)

        assert window.start == "@2026-09-09 09:00:00 UTC"
        assert window.end is None
        assert window.interval == "5min"
        assert window.samples == TARGET_SAMPLES

    def test_case_3_end_and_interval_walks_back_nineteen_gaps(self):
        window = resolve_pcp_window(None, "2026-09-09 10:00:00", "5min", now=NOW)

        # 19 gaps * 5min = 95min before the requested end.
        assert window.start == "@2026-09-09 08:25:00 UTC"
        assert window.end is None
        assert window.interval == "5min"
        assert window.samples == TARGET_SAMPLES

    def test_case_4_start_and_end_derive_the_interval(self):
        window = resolve_pcp_window("2026-09-09 16:00:00", "2026-09-09 18:00:00", None, now=NOW)

        # 2h / 20 = 6min, rounded up the ladder to 10min.
        assert window.start == "@2026-09-09 16:00:00 UTC"
        assert window.end == "@2026-09-09 18:00:00 UTC"
        assert window.interval == "10min"
        assert window.samples is None

    def test_case_5_start_only_ends_an_hour_later_not_now(self):
        window = resolve_pcp_window("2026-09-09 09:00:00", None, None, now=NOW)

        assert window.start == "@2026-09-09 09:00:00 UTC"
        assert window.end == "@2026-09-09 10:00:00 UTC"
        assert window.interval == "5min"
        assert window.samples is None

    def test_case_6_end_only_starts_an_hour_earlier(self):
        window = resolve_pcp_window(None, "2026-09-09 09:00:00", None, now=NOW)

        assert window.start == "@2026-09-09 08:00:00 UTC"
        assert window.end == "@2026-09-09 09:00:00 UTC"
        assert window.interval == "5min"
        assert window.samples is None

    def test_case_7_interval_only_ends_at_now(self):
        window = resolve_pcp_window(None, None, "30s", now=NOW)

        # 19 gaps * 30s = 9min30s before now.
        assert window.start == "@2026-09-09 17:50:30 UTC"
        assert window.end is None
        assert window.interval == "30s"
        assert window.samples == TARGET_SAMPLES

    def test_case_8_nothing_given_is_the_last_hour(self):
        window = resolve_pcp_window(None, None, None, now=NOW)

        assert window.start == "@2026-09-09 17:00:00 UTC"
        assert window.end == "@2026-09-09 18:00:00 UTC"
        assert window.interval == "5min"
        assert window.samples is None


class TestIntervalRounding:
    """Derived intervals climb a ladder; supplied intervals never move."""

    @pytest.mark.parametrize(
        ("start", "end", "expected"),
        [
            # 1min / 20 = 3s, which is on no rung, so take the next one up.
            ("2026-09-09 17:59:00", "2026-09-09 18:00:00", "5sec"),
            # 1h / 20 = 3min -> 5min.
            ("2026-09-09 17:00:00", "2026-09-09 18:00:00", "5min"),
            # 6h / 20 = 18min -> 30min.
            ("2026-09-09 12:00:00", "2026-09-09 18:00:00", "30min"),
            # 24h / 20 = 72min -> 2hour.
            ("2026-09-08 18:00:00", "2026-09-09 18:00:00", "2hour"),
            # 20 days / 20 = 1day exactly, which is itself a rung, so it stays.
            ("2026-08-20 18:00:00", "2026-09-09 18:00:00", "1day"),
        ],
    )
    def test_derived_interval_climbs_the_ladder(self, start, end, expected):
        assert resolve_pcp_window(start, end, None, now=NOW).interval == expected

    def test_window_longer_than_the_ladder_rounds_to_whole_days(self):
        window = resolve_pcp_window("2020-01-01 00:00:00", "2026-01-01 00:00:00", None, now=NOW)

        # ~6 years / 20 is far past the 1day rung, so it extends in days.
        assert window.interval.endswith("day")
        assert int(window.interval.removesuffix("day")) > 1

    @pytest.mark.parametrize("interval", ["7sec", "0.5s", "3min", "1second"])
    def test_supplied_interval_is_never_rounded(self, interval):
        window = resolve_pcp_window("2026-09-09 09:00:00", None, interval, now=NOW)

        assert window.interval == interval


class TestResolvePcpWindowValidation:
    @pytest.mark.parametrize("interval", [None, "1second"])
    def test_end_before_start_is_rejected(self, interval):
        with pytest.raises(ValueError, match="must be after start time"):
            resolve_pcp_window("2026-09-09 18:00:00", "2026-09-09 16:00:00", interval, now=NOW)

    @pytest.mark.parametrize("interval", [None, "1second"])
    def test_a_zero_length_window_is_rejected(self, interval):
        with pytest.raises(ValueError, match="must be after start time"):
            resolve_pcp_window("2026-09-09 16:00:00", "2026-09-09 16:00:00", interval, now=NOW)

    @pytest.mark.parametrize(
        ("start", "end"),
        [("2026-09-09 09:00:00", "2026-09-09 10:00:00"), (None, None)],
    )
    def test_malformed_interval_is_rejected(self, start, end):
        with pytest.raises(ValueError, match="Invalid duration"):
            resolve_pcp_window(start, end, "a while", now=NOW)

    @pytest.mark.parametrize("interval", [None, "1second"])
    @pytest.mark.parametrize(("start", "end"), [("whenever", "now"), ("now", "whenever")])
    def test_malformed_time_spec_is_rejected(self, start, end, interval):
        with pytest.raises(ValueError, match="Invalid time specification"):
            resolve_pcp_window(start, end, interval, now=NOW)


class TestTimezones:
    """Offset-free times mean the target system's clock, never this server's."""

    def test_offset_free_time_is_read_in_the_reference_timezone(self):
        now = datetime(2026, 9, 9, 14, 0, tzinfo=NEW_YORK)

        parsed = parse_time_spec("2026-09-09 09:00:00", now)

        assert parsed.utcoffset() == timedelta(hours=-4)
        assert parsed.astimezone(timezone.utc).hour == 13

    @pytest.mark.parametrize(
        ("spec", "expected"),
        [
            ("2026-09-09T13:00:00Z", datetime(2026, 9, 9, 13, 0, tzinfo=timezone.utc)),
            ("2026-09-09T09:00:00-04:00", datetime(2026, 9, 9, 13, 0, tzinfo=timezone.utc)),
            ("@2026-09-09T18:30:00+05:30", datetime(2026, 9, 9, 13, 0, tzinfo=timezone.utc)),
        ],
    )
    def test_supplied_offsets_are_honoured(self, spec, expected):
        assert parse_time_spec(spec, datetime(2026, 9, 9, 14, 0, tzinfo=NEW_YORK)) == expected

    def test_elapsed_time_is_measured_across_a_dst_jump(self):
        """01:30 is still EST and 03:30 is already EDT, so this spans one real hour."""
        now = datetime(2026, 3, 8, 12, 0, tzinfo=NEW_YORK)

        window = resolve_pcp_window("2026-03-08 01:30:00", "2026-03-08 03:30:00", None, now=now)

        assert window.start == "@2026-03-08 06:30:00 UTC"
        assert window.end == "@2026-03-08 07:30:00 UTC"
        # One real hour over 20 samples is 3min, rounded up to 5min — not the
        # 10min that two wall-clock hours would have given.
        assert window.interval == "5min"

    def test_default_timespan_is_a_real_hour_across_a_dst_jump(self):
        now = datetime(2026, 3, 8, 12, 0, tzinfo=NEW_YORK)

        window = resolve_pcp_window(None, "2026-03-08 03:30:00", None, now=now)

        assert window.start == "@2026-03-08 06:30:00 UTC"
        assert window.end == "@2026-03-08 07:30:00 UTC"

    def test_interval_anchored_window_steps_real_time_across_a_dst_jump(self):
        now = datetime(2026, 3, 8, 12, 0, tzinfo=NEW_YORK)

        window = resolve_pcp_window(None, "2026-03-08 03:30:00", "10min", now=now)

        # 19 gaps * 10min back from 07:30 UTC, counted in elapsed time.
        assert window.start == "@2026-03-08 04:20:00 UTC"
        assert window.samples == TARGET_SAMPLES


def test_reference_time_defaults_to_this_machine():
    before = datetime.now().astimezone().replace(microsecond=0)

    window = resolve_pcp_window(None, None, None)

    assert window.start >= to_pcp_time(before - DEFAULT_TIMESPAN)
