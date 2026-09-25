"""Tests for parsing and merging PCP archive time ranges."""

from datetime import datetime
from datetime import timezone

import pytest

from linux_mcp_server.parsers import parse_pcp_archive_ranges


def archive_label(start: int, end: int) -> str:
    """Build the boundary lines emitted by pmdumplog -l -x -x -x."""
    start_date = datetime.fromtimestamp(start, tz=timezone.utc).strftime("%a %b %d %H:%M:%S.%f %Y")
    end_date = datetime.fromtimestamp(end, tz=timezone.utc).strftime("%a %b %d %H:%M:%S.%f %Y")
    return f"Log Label (Log Format Version 3)\n    commencing {start_date} {start}\n    ending {end_date} {end}\n"


def test_parse_pcp_archive_ranges_uses_epoch_and_merges(pcp_archive_output):
    ranges = parse_pcp_archive_ranges(pcp_archive_output, "UTC")

    assert len(ranges) == 1
    assert ranges[0].start == datetime(2024, 1, 1, tzinfo=timezone.utc)
    assert ranges[0].end == datetime(2024, 1, 1, 2, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    ("boundaries", "expected"),
    [
        # The grace period is inclusive: a 3600s gap merges, a 3601s one does not.
        pytest.param([(0, 300), (100, 200)], [(0, 300)], id="nested"),
        pytest.param([(0, 100), (100, 200)], [(0, 200)], id="touching"),
        pytest.param([(0, 100), (3700, 3800)], [(0, 3800)], id="exactly-one-hour"),
        pytest.param([(0, 100), (3701, 3800)], [(0, 100), (3701, 3800)], id="gap-over-one-hour"),
        pytest.param([(7400, 7500), (0, 100), (3700, 3800)], [(0, 7500)], id="chain"),
        pytest.param([(100, 100)], [(100, 100)], id="single-sample"),
        pytest.param([(100, 0)], [], id="reversed"),
    ],
)
def test_parse_pcp_archive_ranges_boundaries(boundaries, expected):
    stdout = "".join(archive_label(start, end) for start, end in boundaries)

    ranges = parse_pcp_archive_ranges(stdout, "UTC")

    assert [(item.start.timestamp(), item.end.timestamp()) for item in ranges] == expected


@pytest.mark.parametrize(
    ("grace_period_hours", "expected"),
    [(0, [(0, 200), (210, 300)]), (1, [(0, 300)])],
)
def test_parse_pcp_archive_ranges_configurable_grace(grace_period_hours, expected):
    stdout = archive_label(0, 100) + archive_label(100, 200) + archive_label(210, 300)

    ranges = parse_pcp_archive_ranges(stdout, "UTC", grace_period_hours=grace_period_hours)

    assert [(item.start.timestamp(), item.end.timestamp()) for item in ranges] == expected


def test_parse_pcp_archive_ranges_rejects_negative_grace():
    with pytest.raises(ValueError, match="grace_period_hours must be nonnegative"):
        parse_pcp_archive_ranges("", "UTC", grace_period_hours=-1)


@pytest.mark.parametrize(
    "stdout",
    [
        "",
        "not an archive label",
        "commencing Mon Jan 01 00:00:00.000000 2024\nending Mon Jan 01 01:00:00.000000 2024",
        "commencing Mon Jan 01 00:00:00.000000 2024 1704067200\nending UNKNOWN",
        "ending Mon Jan 01 01:00:00.000000 2024 1704070800",
        "commencing Mon Jan 01 00:00:00.000000 2024 1704067200",
        "commencing Mon Jan 01 00:00:00.000000 2024 999999999999999999999999999\nending UNKNOWN",
        "commencing Mon Jan 01 00:00:00.000000 2024 1704067200\n"
        "--- archive next ---\nending Mon Jan 01 01:00:00.000000 2024 1704070800",
    ],
)
def test_parse_pcp_archive_ranges_ignores_invalid_or_incomplete_labels(stdout):
    assert parse_pcp_archive_ranges(stdout, "UTC") == []


@pytest.mark.parametrize("fraction", ["", ".123456", ".123456789"])
def test_parse_pcp_archive_ranges_reports_whole_seconds(fraction):
    """A fraction in the label is read but dropped, whatever its precision.

    pmrep rejects sub-second precision in a time spec, so a range boundary
    carrying one could never be handed back to pcp_query_metrics as-is.
    """
    stdout = (
        f"commencing Mon Jan 01 00:00:00{fraction} 2024 1704067200\n"
        f"ending Mon Jan 01 01:00:00{fraction} 2024 1704070800\n"
    )

    ranges = parse_pcp_archive_ranges(stdout, "UTC")

    assert len(ranges) == 1
    assert ranges[0].start == datetime(2024, 1, 1, tzinfo=timezone.utc)
    assert ranges[0].end == datetime(2024, 1, 1, 1, tzinfo=timezone.utc)


def test_parse_pcp_archive_ranges_rejects_an_unknown_timezone():
    with pytest.raises(ValueError, match="Invalid timezone: Mars/Olympus_Mons"):
        parse_pcp_archive_ranges("", "Mars/Olympus_Mons")
