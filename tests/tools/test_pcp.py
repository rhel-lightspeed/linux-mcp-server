"""Tests for PCP historical performance data tools."""

import pytest


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
        result = await mcp_client.call_tool("list_pcp_metrics")
        result_text = result.content[0].text

        assert "kernel.all.cpu.user" in result_text
        assert "mem.util.used" in result_text

    async def test_keyword_filter(self, mcp_client, mock_execute):
        mock_execute.return_value = (
            0,
            "kernel.all.cpu.user [total user CPU time]\nkernel.all.cpu.sys [total sys CPU time]\nmem.util.used [used memory]\n",
            "",
        )
        result = await mcp_client.call_tool("list_pcp_metrics", arguments={"search_keyword": "cpu"})
        result_text = result.content[0].text

        assert "kernel.all.cpu.user" in result_text
        assert "kernel.all.cpu.sys" in result_text
        assert "mem.util.used" not in result_text

    async def test_pcp_not_installed(self, mcp_client, mock_execute):
        mock_execute.return_value = (1, "", "command not found")
        result = await mcp_client.call_tool("list_pcp_metrics")

        assert "not installed" in result.content[0].text


class TestListPcpArchives:
    async def test_list_archives_success(self, mcp_client, mock_execute):
        mock_execute.side_effect = [
            (
                0,
                "/var/log/pcp/pmlogger/mcpvm-lazy-whisk.local/20260903.index\n",
                "",
            ),
            (
                0,
                "Log Label\n"
                "    commencing Thu Sep  3 14:42:29.392267385 2026\n"
                "    ending     Fri Sep  4 00:10:37.287627058 2026\n"
                "Archive timezone: UTC\n",
                "",
            ),
        ]

        result = await mcp_client.call_tool("list_pcp_archives")
        result_text = result.content[0].text

        assert "commencing Thu Sep  3" in result_text
        assert "ending     Fri Sep  4" in result_text
        assert "14:42:29.392267385" in result_text
        assert "00:10:37.287627058" in result_text
        assert "Archive timezone: UTC" in result_text

    async def test_no_archives(self, mcp_client, mock_execute):
        mock_execute.return_value = (0, "", "")

        result = await mcp_client.call_tool("list_pcp_archives")
        result_text = result.content[0].text

        assert "No PCP archives found" in result_text


class TestQueryPcpMetrics:
    async def test_query_success(self, mcp_client, mock_execute):
        mock_execute.side_effect = [
            (
                0,
                "pmlogger: primary logger: /var/log/pcp/pmlogger/mcpvm-lazy-whisk.local/20260904.00.10\n",
                "",
            ),
            (
                0,
                "[ 1] - kernel.all.cpu.user - ms/s\n\n         1\n     0.667\n     0.333\n",
                "",
            ),
        ]

        result = await mcp_client.call_tool(
            "query_pcp_metrics",
            arguments={
                "metrics": ["kernel.all.cpu.user"],
                "start_time": "-30minutes",
                "end_time": "now",
            },
        )
        result_text = result.content[0].text

        assert "kernel.all.cpu.user" in result_text
        assert "0.667" in result_text
        assert "0.333" in result_text

    async def test_no_archives(self, mcp_client, mock_execute):
        mock_execute.return_value = (
            0,
            "Performance Co-Pilot\n hardware: 2 cpus\n",
            "",
        )

        result = await mcp_client.call_tool(
            "query_pcp_metrics",
            arguments={
                "metrics": ["kernel.all.cpu.user"],
                "start_time": "-30minutes",
                "end_time": "now",
            },
        )

        assert "No PCP archives found" in result.content[0].text


class TestGetPerformanceSummary:
    async def test_live_summary(self, mcp_client, mock_execute):
        mock_execute.return_value = (
            0,
            "OS\n  Hostname: myhost\nMEMORY\n  RAM: 3.5 GiB\n",
            "",
        )
        result = await mcp_client.call_tool("get_performance_summary")
        result_text = result.content[0].text

        assert "Hostname" in result_text
        assert "MEMORY" in result_text

    async def test_not_installed(self, mcp_client, mock_execute):
        mock_execute.return_value = (1, "", "command not found")
        result = await mcp_client.call_tool("get_performance_summary")

        assert "not available" in result.content[0].text
