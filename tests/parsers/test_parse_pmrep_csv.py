"""Tests for parsing pmrep -o csv output."""

import zoneinfo

from datetime import timezone

import pytest

from linux_mcp_server.parsers import parse_pmrep_csv


def test_parses_rows_into_samples():
    stdout = (
        'Time,"filesys.free-/dev/sda3","filesys.free-/dev/sda2"\n'
        "2026-09-09T16:52:31-0400,13333556,195420\n"
        "2026-09-09T17:52:31-0400,13233428,195420\n"
    )

    samples = parse_pmrep_csv(stdout)

    assert [sample.time for sample in samples] == [
        "2026-09-09T16:52:31-0400",
        "2026-09-09T17:52:31-0400",
    ]
    assert samples[0].metrics == {
        "filesys.free-/dev/sda3": "13333556",
        "filesys.free-/dev/sda2": "195420",
    }


def test_drops_empty_cells_and_valueless_samples():
    stdout = (
        'Time,"kernel.all.cpu.user","mem.util.used"\n2026-09-09T15:52:31-0400,,\n2026-09-09T16:52:31-0400,,13333556\n'
    )

    samples = parse_pmrep_csv(stdout)

    assert len(samples) == 1
    assert samples[0].metrics == {"mem.util.used": "13333556"}


def test_metric_names_with_commas_stay_intact():
    stdout = 'Time,"disk.dev.read-sda,sdb"\n2026-09-09T16:52:31-0400,42\n'

    assert parse_pmrep_csv(stdout)[0].metrics == {"disk.dev.read-sda,sdb": "42"}


def test_header_only_and_empty_output_yield_nothing():
    assert parse_pmrep_csv('Time,"kernel.all.cpu.user"\n') == []
    assert parse_pmrep_csv("") == []


@pytest.mark.parametrize("stamp", ["2026-09-09T20:52:31Z", "2026-09-09T20:52:31"])
def test_utc_timestamps_are_rendered_in_the_target_timezone(stamp):
    """A stamp carrying no zone is assumed UTC, which is what pmrep emits."""
    stdout = f'Time,"mem.util.used"\n{stamp},13333556\n'

    samples = parse_pmrep_csv(stdout, zoneinfo.ZoneInfo("America/New_York"))

    assert samples[0].time == "2026-09-09T16:52:31-04:00"


def test_unreadable_timestamp_is_rejected_only_when_converting():
    """Converting one would claim a zone it does not have; passing it through
    untouched claims nothing, so only the conversion path rejects it.
    """
    stdout = 'Time,"mem.util.used"\nnot a time,13333556\n'

    with pytest.raises(ValueError, match="Unrecognised timestamp"):
        parse_pmrep_csv(stdout, timezone.utc)

    assert parse_pmrep_csv(stdout)[0].time == "not a time"
