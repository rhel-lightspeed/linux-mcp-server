"""Input validation utilities for MCP tools.

This module provides reusable validation functions to handle common input
validation patterns, particularly for numeric parameters where LLMs often
pass floats instead of integers.
"""

from typing import Union, Optional, Tuple


def validate_positive_int(
    value: Union[int, float],
    param_name: str = "parameter",
    min_value: int = 1,
    max_value: Optional[int] = None
) -> Tuple[Optional[int], Optional[str]]:
    """
    Validate and normalize a numeric value to a positive integer.
    
    This function accepts both int and float types (since LLMs often pass floats)
    and truncates floats to integers. It then validates the value is within
    specified bounds.
    
    Args:
        value: The value to validate (int or float)
        param_name: Name of the parameter for error messages
        min_value: Minimum acceptable value (default: 1)
        max_value: Maximum acceptable value (default: None for no limit)
    
    Returns:
        A tuple of (validated_int, error_message). If validation succeeds,
        returns (int_value, None). If validation fails, returns (None, error_msg).
    
    Examples:
        >>> validate_positive_int(5)
        (5, None)
        
        >>> validate_positive_int(5.9)
        (5, None)
        
        >>> validate_positive_int(-1)
        (None, 'Error: parameter must be at least 1')
        
        >>> validate_positive_int(1500, max_value=1000)
        (1000, None)  # Capped at max_value
    """
    # Check type
    if not isinstance(value, (int, float)):
        return None, f"Error: {param_name} must be a number"
    
    # Truncate float to integer
    int_value = int(value)
    
    # Validate minimum
    if int_value < min_value:
        return None, f"Error: {param_name} must be at least {min_value}"
    
    # Cap at maximum if specified
    if max_value is not None and int_value > max_value:
        int_value = max_value
    
    return int_value, None


def validate_pid(pid: Union[int, float]) -> Tuple[Optional[int], Optional[str]]:
    """
    Validate a process ID (PID).
    
    PIDs must be positive integers. This function accepts floats (from LLMs)
    and truncates them to integers.
    
    Args:
        pid: The PID to validate
    
    Returns:
        A tuple of (validated_pid, error_message). If validation succeeds,
        returns (int_pid, None). If validation fails, returns (None, error_msg).
    
    Examples:
        >>> validate_pid(1234)
        (1234, None)
        
        >>> validate_pid(1234.5)
        (1234, None)
        
        >>> validate_pid(0)
        (None, 'Error: PID must be a positive integer')
    """
    return validate_positive_int(pid, param_name="PID", min_value=1)


def validate_line_count(
    lines: Union[int, float],
    default: int = 100,
    max_lines: int = 10000
) -> Tuple[int, Optional[str]]:
    """
    Validate a line count parameter for log reading functions.
    
    Line counts must be positive integers, capped at a reasonable maximum
    to prevent resource exhaustion.
    
    Args:
        lines: Number of lines requested
        default: Default value if validation fails
        max_lines: Maximum allowed line count
    
    Returns:
        A tuple of (validated_lines, error_message). If validation succeeds,
        returns (int_lines, None). If validation fails, returns (default, error_msg).
    
    Examples:
        >>> validate_line_count(50)
        (50, None)
        
        >>> validate_line_count(50.7)
        (50, None)
        
        >>> validate_line_count(-10)
        (100, 'Error: lines must be at least 1')
    """
    validated, error = validate_positive_int(
        lines,
        param_name="lines",
        min_value=1,
        max_value=max_lines
    )
    
    if error:
        return default, error
    
    return validated, None

