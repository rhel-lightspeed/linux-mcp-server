"""Tests for PCP historical performance data tools."""

import json

import pytest

from fastmcp.exceptions import ToolError


@pytest.fixture
def mock_execute(mock_execute_with_fallback_for):
    """Mock execute_with_fallback for commands module."""
    return mock_execute_with_fallback_for("linux_mcp_server.commands")


class TestListPcpMetrics:
    async def test_list_all_metrics(self, mcp_client, mock_execute):
        mock_execute.return_value = (
            0,
            "kernel.all.cpu.user [total user CPU time]\nmem.util.used [used memory]\n",
            "",
        )
        result = await mcp_client.call_tool("pcp_list_metrics", {"host": "localhost"})
        result_text = result.content[0].text

        assert "kernel.all.cpu.user" in result_text
        assert "mem.util.used" in result_text

    @pytest.mark.parametrize(
        ("result", "expected"),
        [
            pytest.param((1, "", "command not found"), "not installed", id="pminfo-missing"),
            pytest.param((1, "", "pminfo: cannot connect to pmcd"), "cannot connect to pmcd", id="pmcd-unreachable"),
            pytest.param((0, "   \n", ""), "No PCP metrics found", id="no-metrics"),
        ],
    )
    async def test_failures_are_reported(self, mcp_client, mock_execute, result, expected):
        mock_execute.return_value = result

        with pytest.raises(ToolError, match=expected):
            await mcp_client.call_tool("pcp_list_metrics", {"host": "localhost"})


ARCHIVE_DIR_OUTPUT = (
    "\npmcd.pmlogger.archive\n"
    '    inst [2384 or "2384"] value "/var/log/pcp/pmlogger/mcpvm-lazy-whisk.local/20260904.00.10"\n'
    '    inst [0 or "primary"] value "/var/log/pcp/pmlogger/mcpvm-lazy-whisk.local/20260904.00.10"\n'
)

# A farm host logs other hosts too, and they can be listed before the primary.
MIXED_ARCHIVE_OUTPUT = (
    "\npmcd.pmlogger.archive\n"
    '    inst [999 or "999"] value "/var/log/pcp/pmlogger/other-host/20260904.00.10"\n'
    '    inst [0 or "primary"] value "/var/log/pcp/pmlogger/this-host/20260904.00.10"\n'
)

OTHER_HOST_ARCHIVE_OUTPUT = (
    '\npmcd.pmlogger.archive\n    inst [999 or "999"] value "/var/log/pcp/pmlogger/other-host/20260904.00.10"\n'
)

TIMEZONE_OUTPUT = "America/New_York\n"

# pmrep runs against UTC because its %z escape is never substituted; the tool
# converts to the target timezone on the way out.
PMREP_CSV_OUTPUT = (
    'Time,"kernel.all.cpu.user","mem.util.used"\n'
    "2026-09-09T19:52:31Z,,\n"
    "2026-09-09T20:52:31Z,0.667,13333556\n"
    "2026-09-09T21:52:31Z,0.333,13233428\n"
)

# The stages pcp_query_metrics and pcp_performance_summary run, in order,
# when nothing goes wrong.
TIMEZONE_OK = (0, TIMEZONE_OUTPUT, "")
ARCHIVE_OK = (0, ARCHIVE_DIR_OUTPUT, "")
PMREP_OK = (0, PMREP_CSV_OUTPUT, "")
XSOS_OK = (0, "OS\n  Hostname: myhost\n", "")


@pytest.fixture
def mock_query(mock_execute):
    """Stub the timezone lookup, archive discovery and pmrep call in order."""
    mock_execute.side_effect = [TIMEZONE_OK, ARCHIVE_OK, PMREP_OK]
    return mock_execute


async def query(mcp_client, **kwargs):
    """Call pcp_query_metrics, defaulting to a single valid metric."""
    kwargs.setdefault("metrics", ["kernel.all.cpu.user"])
    kwargs.setdefault("host", "localhost")
    return await mcp_client.call_tool("pcp_query_metrics", arguments=kwargs)


async def summary(mcp_client, **kwargs):
    """Call pcp_performance_summary."""
    kwargs.setdefault("host", "localhost")
    return await mcp_client.call_tool("pcp_performance_summary", arguments=kwargs)


def pmrep_args(mock_execute):
    """The argument tuple of the pmrep call."""
    return mock_execute.call_args_list[2].args[0]


class TestQueryPcpMetrics:
    async def test_query_success(self, mcp_client, mock_query):
        result = await query(
            mcp_client,
            metrics=["kernel.all.cpu.user", "mem.util.used"],
            start_time="-30minutes",
            end_time="now",
        )
        samples = json.loads(result.content[0].text)

        # The first CSV row has no values yet, so it is dropped. UTC
        # timestamps come back in the target system's timezone.
        assert samples == [
            {
                "time": "2026-09-09T16:52:31-04:00",
                "metrics": {"kernel.all.cpu.user": "0.667", "mem.util.used": "13333556"},
            },
            {
                "time": "2026-09-09T17:52:31-04:00",
                "metrics": {"kernel.all.cpu.user": "0.333", "mem.util.used": "13233428"},
            },
        ]

    @pytest.mark.parametrize(
        ("timezone_result", "expected"),
        [
            pytest.param((1, "", "timedatectl: not found"), "Unable to determine", id="command-failed"),
            # discover_timezone_name swallows the exception and returns None.
            pytest.param(OSError("ssh: connect failed"), "Unable to determine", id="connection-failed"),
            # A name timedatectl reports but zoneinfo cannot load.
            pytest.param((0, "Mars/Olympus_Mons\n", ""), "Cannot load", id="unloadable-name"),
        ],
    )
    async def test_timezone_discovery_failures_stop_the_query(
        self, mcp_client, mock_execute, timezone_result, expected
    ):
        mock_execute.side_effect = [timezone_result, ARCHIVE_OK, PMREP_OK]

        with pytest.raises(ToolError, match=f"{expected} the target system's timezone"):
            await query(mcp_client)

        # Nothing beyond the timezone lookup should have run.
        assert mock_execute.call_count == 1

    async def test_window_bounds_name_their_timezone(self, mcp_client, mock_query):
        """pmrep is told UTC twice, so a missing --timezone cannot shift the window."""
        await query(mcp_client, start_time="2026-09-09 09:00:00", end_time="2026-09-09 11:00:00")

        args = pmrep_args(mock_query)
        # 09:00 in America/New_York is 13:00 UTC.
        assert args[args.index("--start") + 1] == "@2026-09-09 13:00:00 UTC"
        assert args[args.index("--finish") + 1] == "@2026-09-09 15:00:00 UTC"

    async def test_end_before_start_is_rejected(self, mcp_client, mock_query):
        with pytest.raises(ToolError, match="must be after start time"):
            await query(mcp_client, start_time="2026-09-09 10:00:00", end_time="2026-09-09 09:00:00")

    @pytest.mark.parametrize(
        ("start_time", "end_time", "interval", "expect_finish", "expect_samples", "expect_interval"),
        [
            ("-24hours", "now", "1second", True, False, "1second"),
            ("2026-09-09 09:00:00", None, "5min", False, True, "5min"),
            (None, "2026-09-09 10:00:00", "5min", False, True, "5min"),
            # A bare range picks its own interval: two hours over 20 samples is
            # 6min, rounded up the ladder to 10min.
            ("2026-09-09 09:00:00", "2026-09-09 11:00:00", None, True, False, "10min"),
            ("2026-09-09 09:00:00", None, None, True, False, "5min"),
            (None, "2026-09-09 10:00:00", None, True, False, "5min"),
            (None, None, "30seconds", False, True, "30seconds"),
            # Nothing given at all: one hour over 20 samples is 3min, rounded to 5min.
            (None, None, None, True, False, "5min"),
        ],
    )
    async def test_window_flags_are_consistent(
        self, mcp_client, mock_query, start_time, end_time, interval, expect_finish, expect_samples, expect_interval
    ):
        """--finish and --samples are never both passed: pmrep recalculates a
        supplied interval when it is given both."""
        await query(mcp_client, start_time=start_time, end_time=end_time, interval=interval)

        args = pmrep_args(mock_query)
        assert ("--finish" in args) is expect_finish
        assert ("--samples" in args) is expect_samples
        assert args[args.index("--interval") + 1] == expect_interval
        # Relative specs are resolved here so pmrep does not re-resolve them
        # against its own clock.
        assert args[args.index("--start") + 1].startswith("@")
        assert "" not in args
        assert "None" not in args
        if expect_samples:
            assert args[args.index("--samples") + 1] == "20"

    async def test_rejects_malformed_metric_names(self, mcp_client, mock_execute):
        """Validation runs before any command. Which names are invalid is
        covered exhaustively in tests/utils/test_validation.py."""
        with pytest.raises(ToolError, match="Invalid PCP metric name"):
            await query(mcp_client, metrics=["--output-file"])

        mock_execute.assert_not_called()

    async def test_prefers_primary_logger_over_first_instance(self, mcp_client, mock_execute):
        mock_execute.side_effect = [TIMEZONE_OK, (0, MIXED_ARCHIVE_OUTPUT, ""), PMREP_OK]

        await query(mcp_client)

        args = pmrep_args(mock_execute)
        assert args[args.index("--archive") + 1] == "/var/log/pcp/pmlogger/this-host"

    @pytest.mark.parametrize(
        "archive_output",
        [
            # Without a primary logger the only archives here belong to other hosts.
            pytest.param(OTHER_HOST_ARCHIVE_OUTPUT, id="another-hosts-archive"),
            pytest.param("Performance Co-Pilot\n hardware: 2 cpus\n", id="no-archives"),
        ],
    )
    async def test_archive_discovery_failures_are_reported(self, mcp_client, mock_execute, archive_output):
        mock_execute.side_effect = [TIMEZONE_OK, (0, archive_output, "")]

        with pytest.raises(ToolError, match="Primary archive location could not be discovered"):
            await query(mcp_client)

        assert mock_execute.call_count == 2

    @pytest.mark.parametrize(
        ("earlier_stages", "failure", "expected"),
        [
            pytest.param([], (127, "", "pminfo: command not found"), "PCP is not installed", id="pminfo-missing"),
            # A stopped pmcd is a running-service problem, not a missing package.
            pytest.param(
                [],
                (1, "", 'pminfo: Cannot connect to PMCD on host "local:"'),
                "Cannot connect to PMCD",
                id="pmcd-unreachable",
            ),
            pytest.param(
                [ARCHIVE_OK], (127, "", "pmrep: command not found"), "pmrep is not installed", id="pmrep-missing"
            ),
            pytest.param(
                [ARCHIVE_OK], (1, "", "pmrep: no archive files found"), "no archive files found", id="pmrep-failed"
            ),
        ],
    )
    async def test_command_failures_are_reported(self, mcp_client, mock_execute, earlier_stages, failure, expected):
        mock_execute.side_effect = [TIMEZONE_OK, *earlier_stages, failure]

        with pytest.raises(ToolError, match=expected):
            await query(mcp_client)

    @pytest.mark.parametrize(
        ("csv_output", "expected"),
        [
            pytest.param('Time,"kernel.all.cpu.user"\n', "No data returned", id="no-samples"),
            # Samples are only meaningful if their times can be placed on a clock.
            pytest.param(
                'Time,"kernel.all.cpu.user"\nnot a time,0.667\n', "Unrecognised timestamp", id="unreadable-timestamp"
            ),
        ],
    )
    async def test_unusable_csv_is_reported(self, mcp_client, mock_execute, csv_output, expected):
        mock_execute.side_effect = [TIMEZONE_OK, ARCHIVE_OK, (0, csv_output, "")]

        with pytest.raises(ToolError, match=expected):
            await query(mcp_client)


class TestGetPerformanceSummary:
    async def test_live_summary(self, mcp_client, mock_execute):
        mock_execute.return_value = (0, "OS\n  Hostname: myhost\nMEMORY\n  RAM: 3.5 GiB\n", "")

        result = await summary(mcp_client)
        result_text = result.content[0].text

        assert "Hostname" in result_text
        assert "MEMORY" in result_text

    @pytest.mark.parametrize(
        ("timestamp", "expected_origin"),
        [
            # A naive timestamp is the target's local time, but it goes back out
            # as UTC: pcp xsos has no --timezone option, so the origin has to
            # name its own zone to be unambiguous.
            pytest.param("2026-09-04 03:00:00", "@2026-09-04 07:00:00 UTC", id="naive-is-target-local"),
            # US clocks repeat 01:00-02:00 on 2026-11-01, so these two instants
            # share a wall-clock reading and are told apart only by the offset.
            pytest.param("2026-11-01T01:30:00-04:00", "@2026-11-01 05:30:00 UTC", id="dst-first-pass"),
            pytest.param("2026-11-01T01:30:00-05:00", "@2026-11-01 06:30:00 UTC", id="dst-second-pass"),
        ],
    )
    async def test_archive_and_origin_are_passed_to_xsos(self, mcp_client, mock_execute, timestamp, expected_origin):
        mock_execute.side_effect = [TIMEZONE_OK, ARCHIVE_OK, XSOS_OK]

        await summary(mcp_client, timestamp=timestamp)

        args = mock_execute.call_args_list[2].args[0]
        assert args[args.index("--archive") + 1] == "/var/log/pcp/pmlogger/mcpvm-lazy-whisk.local"
        assert args[args.index("--origin") + 1] == expected_origin

    async def test_malformed_timestamp_is_rejected(self, mcp_client, mock_execute):
        mock_execute.return_value = TIMEZONE_OK

        with pytest.raises(ToolError, match="Invalid time specification"):
            await summary(mcp_client, timestamp="half past ten")

    async def test_unknown_target_timezone_stops_the_summary(self, mcp_client, mock_execute):
        mock_execute.return_value = (1, "", "timedatectl: not found")

        with pytest.raises(ToolError, match="Unable to determine the target system's timezone"):
            await summary(mcp_client, timestamp="2026-09-04 03:00:00")

        # Nothing beyond the timezone lookup should have run.
        assert mock_execute.call_count == 1

    async def test_live_summary_needs_no_timezone(self, mcp_client, mock_execute):
        """Without a timestamp there is nothing to interpret, so do not ask."""
        mock_execute.return_value = XSOS_OK

        await summary(mcp_client)

        assert mock_execute.call_count == 1
        assert mock_execute.call_args_list[0].args[0][:2] == ("pcp", "xsos")

    @pytest.mark.parametrize(
        ("result", "expected"),
        [
            pytest.param((1, "", "command not found"), "not available", id="xsos-missing"),
            pytest.param((1, "", "pcp xsos: no metrics available"), "no metrics available", id="xsos-failed"),
            pytest.param((0, "  \n", ""), "No performance summary data", id="empty-summary"),
        ],
    )
    async def test_failures_are_reported(self, mcp_client, mock_execute, result, expected):
        mock_execute.return_value = result

        with pytest.raises(ToolError, match=expected):
            await summary(mcp_client)
