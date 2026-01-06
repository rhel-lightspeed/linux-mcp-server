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
