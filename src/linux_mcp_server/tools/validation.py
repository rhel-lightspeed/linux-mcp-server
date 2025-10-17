"""Input validation utilities for MCP tools.

Provides validation functions for handling numeric parameters where LLMs often
pass floats instead of integers.
"""

from typing import Union, Optional, Tuple


def validate_positive_int(
    value: Union[int, float],
    param_name: str = "parameter",
    min_value: int = 1,
    max_value: Optional[int] = None,
) -> Tuple[Optional[int], Optional[str]]:
    """
    Validate and normalize a numeric value to a positive integer.

    Accepts both int and float (LLMs often pass floats) and truncates to int.
    Validates bounds and caps at max_value if specified.

    Returns:
        (validated_int, error_message) tuple. On success: (int_value, None).
        On failure: (None, error_msg).
    """
    if not isinstance(value, (int, float)):
        return None, f"Error: {param_name} must be a number"

    int_value = int(value)

    if int_value < min_value:
        return None, f"Error: {param_name} must be at least {min_value}"

    if max_value is not None and int_value > max_value:
        int_value = max_value

    return int_value, None


def validate_pid(pid: Union[int, float]) -> Tuple[Optional[int], Optional[str]]:
    """Validate a process ID (PID). Accepts floats from LLMs and truncates to int."""
    return validate_positive_int(pid, param_name="PID", min_value=1)


def validate_line_count(
    lines: Union[int, float],
    default: int = 100,
    max_lines: int = 10000,
) -> Tuple[int, Optional[str]]:
    """
    Validate line count for log reading functions.

    Accepts floats from LLMs, truncates to int, caps at max_lines.
    Returns default value if validation fails.
    """
    validated, error = validate_positive_int(lines, "lines", 1, max_lines)
    return (default, error) if error else (validated, None)
