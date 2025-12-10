"""Command-line sanitization utilities to prevent secret exposure."""

# Common flags that precede secrets
_SECRET_FLAGS: frozenset[str] = frozenset(
    {
        "-p",
        "--password",
        "--pass",
        "--passwd",
        "--secret",
        "--token",
        "--api-key",
        "--api_key",
        "--apikey",
        "-k",
        "--key",
        "--auth",
        "--credential",
        "--private-key",
        "--secret-key",
        "--access-key",
    }
)

# Patterns in key=value format
_SECRET_PATTERNS: tuple[str, ...] = (
    "password=",
    "passwd=",
    "pass=",
    "token=",
    "secret=",
    "apikey=",
    "api_key=",
    "credential=",
    "auth=",
    "key=",
)

REDACTED = "***REDACTED***"


def _is_secret_key_value(arg: str) -> bool:
    """Check if arg is a key=value pattern containing a secret."""
    arg_lower = arg.lower()
    return any(arg_lower.startswith(p) for p in _SECRET_PATTERNS)


def _process_arg(arg: str) -> tuple[str, bool]:
    """Process a single argument for secrets.

    Args:
        arg: Command line argument to process

    Returns:
        Tuple of (processed_arg, should_redact_next)
    """
    # Secret flag without value (e.g., -p, --password) - redact next arg
    if arg in _SECRET_FLAGS:
        return arg, True

    # Handle --flag=value or key=value patterns
    if "=" in arg:
        key = arg.split("=", 1)[0]
        if key in _SECRET_FLAGS or _is_secret_key_value(arg):
            return f"{key}={REDACTED}", False

    return arg, False


def sanitize_cmdline(cmdline: list[str] | None) -> list[str] | None:
    """Sanitize command line arguments to redact potential secrets.

    Redacts arguments following common secret flags (e.g., -p, --password)
    and key=value patterns containing sensitive keywords.

    Args:
        cmdline: List of command line arguments (or None)

    Returns:
        Sanitized list with secrets replaced by REDACTED, or None if input was None

    Note:
        Not foolproof - secrets in non-standard formats may still leak.
        Defense in depth: also ensure logs use sanitize_parameters().
    """
    if cmdline is None:
        return None
    if not cmdline:
        return []

    result: list[str] = []
    redact_next = False

    for arg in cmdline:
        if redact_next:
            result.append(REDACTED)
            redact_next = False
        else:
            processed, redact_next = _process_arg(arg)
            result.append(processed)

    return result
