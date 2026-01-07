"""Tests for input validation utilities."""

import pytest

from linux_mcp_server.utils.validation import is_empty_output


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
