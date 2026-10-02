from pathlib import PurePosixPath


class PathValidationError(ValueError):
    """Raised when path validation fails.

    This is a ValueError subclass for compatibility with existing error handling,
    but provides a distinct type for path-specific validation failures.
    """

    pass


def validate_path(path: str) -> PurePosixPath:
    """Validate a filesystem path for security and correctness.

    The path names a file on the target host, which is always Linux, so it is judged
    by POSIX rules whatever the server itself runs on. Deciding with ``pathlib.Path``
    would make the answer depend on the server's OS: a Windows-hosted server would
    reject "/var/log/secure" as relative and accept "C:/logs/app.log" as absolute.

    Performs security checks to prevent command injection and path traversal attacks:
    - Rejects paths containing newlines, carriage returns, or null bytes
    - Rejects paths starting with '-' (prevents flag injection)
    - Requires absolute POSIX paths

    Args:
        path: The filesystem path to validate.

    Returns:
        The validated path in POSIX format.

    Raises:
        PathValidationError: If the path fails any validation check.

    Examples:
        >>> validate_path("/var/log/messages")
        PurePosixPath('/var/log/messages')

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

    # Require absolute paths, by POSIX rules rather than the server OS's rules
    if not path.startswith("/"):
        raise PathValidationError(f"Path must be absolute: {path}")

    # Prevent path traversal via '..' components
    if ".." in path.split("/"):
        raise PathValidationError(f"Path contains invalid component '..': {path}")

    return PurePosixPath(path)


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
