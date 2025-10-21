import typing as t


def format_bytes(bytes_value: t.Union[int, float]) -> str:
    """
    Format bytes into human-readable format.

    Args:
        bytes_value: Number of bytes to format

    Returns:
        Human-readable string representation (e.g., "1.5GB", "256.0MB")

    Examples:
        >>> format_bytes(1024)
        '1.0KB'
        >>> format_bytes(1536)
        '1.5KB'
        >>> format_bytes(1073741824)
        '1.0GB'
    """
    value = float(bytes_value)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if value < 1024.0:
            return f"{value:.1f}{unit}"

        value /= 1024.0

    return f"{value:.1f}PB"
