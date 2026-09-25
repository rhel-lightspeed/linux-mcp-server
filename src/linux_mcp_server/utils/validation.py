import re

from pathlib import Path


_PCP_METRIC_NAME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_.]*$")


class PathValidationError(ValueError):
    """Raised when path validation fails.

    This is a ValueError subclass for compatibility with existing error handling,
    but provides a distinct type for path-specific validation failures.
    """

    pass


def validate_path(path: str) -> Path:
    """Validate a filesystem path for security and correctness.

    Performs security checks to prevent command injection and path traversal attacks:
    - Rejects paths containing newlines, carriage returns, or null bytes
    - Rejects paths starting with '-' (prevents flag injection)
    - Requires absolute paths

    Args:
        path: The filesystem path to validate.

    Returns:
        The validated path in POSIX format.

    Raises:
        PathValidationError: If the path fails any validation check.

    Examples:
        >>> validate_path("/var/log/messages")
        '/var/log/messages'

        >>> validate_path("relative/path")
        PathValidationError: Path must be absolute: relative/path

        >>> validate_path("/path\\nwith\\nnewlines")
        PathValidationError: Path contains invalid characters: /path\\nwith\\nnewlines
    """
    if not path:
        raise PathValidationError("Path cannot be empty")

    # Check for injection characters (newlines, carriage returns, null bytes)
    if any(c in path for c in ["\n", "\r", "\x00"]):
        raise PathValidationError(f"Path contains invalid characters: {path!r}")

    # Prevent flag injection (paths starting with -)
    if path.startswith("-"):
        raise PathValidationError(f"Path cannot start with '-': {path}")

    # Require absolute paths
    if not Path(path).is_absolute():
        raise PathValidationError(f"Path must be absolute: {path}")

    # Prevent path traversal via '..' components
    if ".." in path.split("/"):
        raise PathValidationError(f"Path contains invalid component '..': {path}")

    return Path(path)


def validate_pcp_metrics(metrics: list[str]) -> tuple[str, ...]:
    """Validate PCP metric names to prevent option injection.

    Args:
        metrics: Metric names to validate.

    Returns:
        The validated metric names as a tuple.

    Raises:
        ValueError: If the list is empty or any name is not a bare metric name.
    """
    if not metrics:
        raise ValueError("At least one PCP metric name is required")

    for metric in metrics:
        if not _PCP_METRIC_NAME_RE.fullmatch(metric):
            raise ValueError(
                f"Invalid PCP metric name: {metric!r}. Names must start with a letter "
                "and contain only letters, digits, underscores, and dots."
            )

    return tuple(metrics)


def is_empty_output(stdout: str | None) -> bool:
    """Check if command output is empty or whitespace-only.

    Args:
        stdout: Command output string, or None.

    Returns:
        True if stdout is None, empty string, or contains only whitespace.
    """
    return not stdout or not stdout.strip()


def is_successful_output(returncode: int, stdout: str | None) -> bool:
    """Check if command succeeded with non-empty output.

    Args:
        returncode: Command exit code (0 indicates success).
        stdout: Command output string, or None.

    Returns:
        True if returncode is 0 and stdout contains non-whitespace content.
    """
    return returncode == 0 and not is_empty_output(stdout)
