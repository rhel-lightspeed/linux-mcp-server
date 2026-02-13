import re

from pathlib import Path


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

    return Path(path)


def validate_dnf_package_name(value: str) -> str:
    """Validate a dnf package identifier for safety.

    Allows a conservative RPM token charset (letters, digits, . _ + : -).
    Rejects empty values, whitespace/control characters, leading '-' and slashes.
    """
    if not value:
        raise ValueError("Package name cannot be empty")

    if any(c in value for c in ["\n", "\r", "\x00", "\t", " "]):
        raise ValueError("Package name contains invalid characters")

    if value.startswith("-"):
        raise ValueError("Package name cannot start with '-'")

    if "/" in value:
        raise ValueError("Package name cannot contain '/'")

    if not re.fullmatch(r"[A-Za-z0-9._+:-]+", value):
        raise ValueError("Package name contains invalid characters")

    return value


def validate_dnf_repo_id(value: str) -> str:
    """Validate a dnf repository identifier for safety.

    Allows a conservative charset (letters, digits, . _ + : -).
    Rejects empty values, whitespace/control characters, leading '-' and slashes.
    """
    if not value:
        raise ValueError("Repository id cannot be empty")

    if any(c in value for c in ["\n", "\r", "\x00", "\t", " "]):
        raise ValueError("Repository id contains invalid characters")

    if value.startswith("-"):
        raise ValueError("Repository id cannot start with '-'")

    if "/" in value:
        raise ValueError("Repository id cannot contain '/'")

    if not re.fullmatch(r"[A-Za-z0-9._+:-]+", value):
        raise ValueError("Repository id contains invalid characters")

    return value


def validate_dnf_group_name(value: str) -> str:
    """Validate a dnf group name for safety.

    Allows letters, digits, spaces and common punctuation used in group names.
    Rejects empty values, control characters, and leading '-'.
    """
    if not value:
        raise ValueError("Group name cannot be empty")

    if any(c in value for c in ["\n", "\r", "\x00", "\t"]):
        raise ValueError("Group name contains invalid characters")

    if value.startswith("-"):
        raise ValueError("Group name cannot start with '-'")

    if not re.fullmatch(r"[A-Za-z0-9 ._+:'()&,-]+", value):
        raise ValueError("Group name contains invalid characters")

    return value


def validate_dnf_module_name(value: str) -> str:
    """Validate a dnf module name for safety.

    Allows a conservative charset (letters, digits, . _ + : -).
    Rejects empty values, whitespace/control characters, leading '-' and slashes.
    """
    if not value:
        raise ValueError("Module name cannot be empty")

    if any(c in value for c in ["\n", "\r", "\x00", "\t", " "]):
        raise ValueError("Module name contains invalid characters")

    if value.startswith("-"):
        raise ValueError("Module name cannot start with '-'")

    if "/" in value:
        raise ValueError("Module name cannot contain '/'")

    if not re.fullmatch(r"[A-Za-z0-9._+:-]+", value):
        raise ValueError("Module name contains invalid characters")

    return value


def validate_optional_dnf_module_name(value: str | None) -> str | None:
    """Validate an optional dnf module name."""
    if value is None:
        return None

    return validate_dnf_module_name(value)


def validate_dnf_provides_query(value: str) -> str:
    """Validate a dnf provides query for safety.

    Accepts file paths or binary names with optional glob wildcards (*, ?).
    Rejects empty values, whitespace/control characters, and leading '-'.
    """
    if not value:
        raise ValueError("Provides query cannot be empty")

    if any(c in value for c in ["\n", "\r", "\x00", "\t", " "]):
        raise ValueError("Provides query contains invalid characters")

    if value.startswith("-"):
        raise ValueError("Provides query cannot start with '-'")

    if ".." in value:
        raise ValueError("Provides query cannot contain '..'")

    if not re.fullmatch(r"[A-Za-z0-9._+:/@*?-]+", value):
        raise ValueError("Provides query contains invalid characters")

    return value


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
