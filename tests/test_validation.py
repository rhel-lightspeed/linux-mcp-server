"""Tests for input validation utilities."""

from linux_mcp_server.tools.validation import validate_line_count
from linux_mcp_server.tools.validation import validate_pid
from linux_mcp_server.tools.validation import validate_positive_int


class TestValidatePositiveInt:
    """Test validate_positive_int function."""

    def test_valid_integer(self):
        """Test with valid integer."""
        result, error = validate_positive_int(5)
        assert result == 5
        assert error is None

    def test_valid_float_truncates(self):
        """Test that float is truncated to integer."""
        result, error = validate_positive_int(5.9)
        assert result == 5
        assert error is None

    def test_exact_float_truncates(self):
        """Test that exact float like 10.0 works."""
        result, error = validate_positive_int(10.0)
        assert result == 10
        assert error is None

    def test_zero_fails(self):
        """Test that zero fails validation (default min is 1)."""
        result, error = validate_positive_int(0)
        assert result is None
        assert error is not None
        assert "at least 1" in error.lower()

    def test_negative_fails(self):
        """Test that negative numbers fail validation."""
        result, error = validate_positive_int(-5)
        assert result is None
        assert error is not None
        assert "at least" in error.lower()

    def test_string_fails(self):
        """Test that string fails validation."""
        result, error = validate_positive_int("123")
        assert result is None
        assert error is not None
        assert "must be a number" in error.lower()

    def test_custom_min_value(self):
        """Test with custom minimum value."""
        result, error = validate_positive_int(5, min_value=10)
        assert result is None
        assert error is not None
        assert "at least 10" in error.lower()

    def test_max_value_caps(self):
        """Test that max_value caps the result."""
        result, error = validate_positive_int(1500, max_value=1000)
        assert result == 1000
        assert error is None

    def test_custom_param_name_in_error(self):
        """Test that custom parameter name appears in error message."""
        result, error = validate_positive_int(-1, param_name="top_n")
        assert result is None
        assert "top_n" in error

    def test_min_value_zero(self):
        """Test with min_value of 0 (allowing zero)."""
        result, error = validate_positive_int(0, min_value=0)
        assert result == 0
        assert error is None


class TestValidatePid:
    """Test validate_pid function."""

    def test_valid_pid(self):
        """Test with valid PID."""
        result, error = validate_pid(1234)
        assert result == 1234
        assert error is None

    def test_float_pid_truncates(self):
        """Test that float PID is truncated."""
        result, error = validate_pid(1234.7)
        assert result == 1234
        assert error is None

    def test_zero_pid_fails(self):
        """Test that PID 0 fails."""
        result, error = validate_pid(0)
        assert result is None
        assert error is not None
        assert "pid" in error.lower()

    def test_negative_pid_fails(self):
        """Test that negative PID fails."""
        result, error = validate_pid(-1)
        assert result is None
        assert error is not None

    def test_large_pid(self):
        """Test with large PID (no max limit)."""
        result, error = validate_pid(99999)
        assert result == 99999
        assert error is None


class TestValidateLineCount:
    """Test validate_line_count function."""

    def test_valid_line_count(self):
        """Test with valid line count."""
        result, error = validate_line_count(50)
        assert result == 50
        assert error is None

    def test_float_line_count_truncates(self):
        """Test that float is truncated."""
        result, error = validate_line_count(50.8)
        assert result == 50
        assert error is None

    def test_zero_returns_default(self):
        """Test that zero returns default value."""
        result, error = validate_line_count(0, default=100)
        assert result == 100
        assert error is not None
        assert "lines" in error.lower()

    def test_negative_returns_default(self):
        """Test that negative returns default value."""
        result, error = validate_line_count(-10, default=100)
        assert result == 100
        assert error is not None

    def test_exceeds_max_caps_at_max(self):
        """Test that exceeding max_lines caps at maximum."""
        result, error = validate_line_count(50000, max_lines=10000)
        assert result == 10000
        assert error is None

    def test_custom_default(self):
        """Test with custom default value."""
        result, error = validate_line_count(-1, default=200)
        assert result == 200
        assert error is not None

    def test_custom_max_lines(self):
        """Test with custom max_lines."""
        result, error = validate_line_count(5000, max_lines=1000)
        assert result == 1000
        assert error is None

    def test_at_max_boundary(self):
        """Test exactly at max boundary."""
        result, error = validate_line_count(1000, max_lines=1000)
        assert result == 1000
        assert error is None
