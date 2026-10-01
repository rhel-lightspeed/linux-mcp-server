from pathlib import PurePosixPath
from pathlib import PureWindowsPath


class PathValidationError(ValueError):
    """Raised when path validation fails.

    This is a ValueError subclass for compatibility with existing error handling,
    but provides a distinct type for path-specific validation failures.
    """

    pass


def validate_path(path: str) -> str:
    """Validate an absolute local or remote path without coercing its syntax.

    Performs security checks to prevent command injection and path traversal attacks:
    - Rejects paths containing newlines, carriage returns, or null bytes
    - Rejects paths starting with '-' (prevents flag injection)
        - Requires an absolute POSIX or Windows path; remote paths receive stricter
            POSIX validation once the target host is known
        - Rejects path traversal via '..' components
    """
    if not path:
        raise PathValidationError("Path cannot be empty")

    # Check for injection characters (newlines, carriage returns, null bytes)
    if any(c in path for c in ["\n", "\r", "\x00"]):
        raise PathValidationError(f"Path contains invalid characters: {path!r}")

    # Prevent flag injection (paths starting with -)
    if path.startswith("-"):
        raise PathValidationError(f"Path cannot start with '-': {path}")

    if not PurePosixPath(path).is_absolute() and not PureWindowsPath(path).is_absolute():
        raise PathValidationError(f"Path must be absolute: {path}")

    # Check both separators so traversal is rejected before local/remote routing.
    if ".." in path.replace("\\", "/").split("/"):
        raise PathValidationError(f"Path contains invalid component '..': {path}")

    return path


def validate_remote_path(path: str) -> str:
    """Validate and normalize a path that will be passed to a remote Linux host."""
    validate_path(path)
    remote_path = PurePosixPath(path)
    if not remote_path.is_absolute() or "\\" in path:
        raise PathValidationError(f"Path must be an absolute POSIX path: {path}")
    return str(remote_path)


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
