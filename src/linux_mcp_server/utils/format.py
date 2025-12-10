import ipaddress


def is_ipv6_link_local(address: str) -> bool:
    """Check if an IPv6 address is link-local (fe80::/10).

    Link-local addresses are only valid on a single network segment and
    require a scope identifier to route. They're not useful for enterprise
    cross-machine communication.

    Args:
        address: IPv6 address string, possibly with scope identifier (e.g., "fe80::1%eth0")

    Returns:
        True if the address is link-local, False otherwise

    Examples:
        >>> is_ipv6_link_local("fe80::1")
        True
        >>> is_ipv6_link_local("fe80::1%eth0")
        True
        >>> is_ipv6_link_local("2001:db8::1")
        False
        >>> is_ipv6_link_local("192.168.1.1")
        False
    """
    try:
        # Parse and check if it's link-local
        addr = ipaddress.IPv6Address(address)
        return addr.is_link_local
    except (ValueError, ipaddress.AddressValueError):
        # Not a valid IPv6 address (could be IPv4, empty, or malformed)
        return False


def format_bytes(bytes_value: int | float) -> str:
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
