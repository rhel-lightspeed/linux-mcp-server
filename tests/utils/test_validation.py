"""Tests for input validation utilities."""

import pytest

from linux_mcp_server.utils.validation import is_empty_output
from linux_mcp_server.utils.validation import is_successful_output


class TestIsEmptyOutput:
    """Test is_empty_output function."""

    @pytest.mark.parametrize(
        "stdout,expected",
        [
            # Empty cases - should return True
            (None, True),
            ("", True),
            ("   ", True),
            ("\t", True),
            ("\n", True),
            ("\r\n", True),
            ("  \t\n  ", True),
            # Non-empty cases - should return False
            ("output", False),
            ("  output  ", False),
            ("\noutput\n", False),
            ("0", False),
            ("false", False),
        ],
    )
    def test_is_empty_output(self, stdout, expected):
        """Test is_empty_output with various inputs."""
        assert is_empty_output(stdout) is expected


class TestIsSuccessfulOutput:
    """Test is_successful_output function."""

    @pytest.mark.parametrize(
        "returncode,stdout,expected",
        [
            # Successful cases - should return True
            (0, "output", True),
            (0, "  output  ", True),
            (0, "\noutput\n", True),
            (0, "0", True),
            (0, "false", True),
            # Failed due to non-zero returncode - should return False
            (1, "output", False),
            (1, "error message", False),
            (-1, "output", False),
            (127, "command not found", False),
            # Failed due to empty stdout - should return False
            (0, None, False),
            (0, "", False),
            (0, "   ", False),
            (0, "\t", False),
            (0, "\n", False),
            (0, "\r\n", False),
            (0, "  \t\n  ", False),
            # Both conditions fail - should return False
            (1, None, False),
            (1, "", False),
            (1, "   ", False),
        ],
    )
    def test_is_successful_output(self, returncode, stdout, expected):
        """Test is_successful_output with various returncode and stdout combinations."""
        assert is_successful_output(returncode, stdout) is expected
