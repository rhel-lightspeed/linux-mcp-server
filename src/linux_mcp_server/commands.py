"""Command registry for unified local and remote execution.

This module provides a centralized registry of commands used by tools,
enabling consistent execution across local and remote systems.
"""

from pydantic import BaseModel


class CommandSpec(BaseModel):
    """Specification for a single command with optional fallback.

    Attributes:
        args: Command arguments as a list of strings.
        fallback: Alternative command arguments if primary fails.
    """

    args: list[str]
    fallback: list[str] | None = None


class CommandGroup(BaseModel):
    """Group of related commands for multi-command tool operations.

    Attributes:
        commands: Named commands within the group.
    """

    commands: dict[str, CommandSpec]


# Type alias for registry entries
CommandEntry = CommandSpec | CommandGroup

COMMANDS: dict[str, CommandEntry] = {
    # === Single-command tools ===
    # Services
    "list_services": CommandSpec(args=["systemctl", "list-units", "--type=service", "--all", "--no-pager"]),
    "running_services": CommandSpec(
        args=["systemctl", "list-units", "--type=service", "--state=running", "--no-pager"]
    ),
    "service_status": CommandSpec(args=["systemctl", "status", "{service_name}", "--no-pager", "--full"]),
    "service_logs": CommandSpec(args=["journalctl", "-u", "{service_name}", "-n", "{lines}", "--no-pager"]),
    # Network (single commands)
    "network_connections": CommandSpec(
        args=["ss", "-tunap"],
        fallback=["netstat", "-tunap"],
    ),
    "listening_ports": CommandSpec(
        args=["ss", "-tulnp"],
        fallback=["netstat", "-tulnp"],
    ),
    # Logs - base command without optional flags
    "journal_logs": CommandSpec(args=["journalctl", "-n", "{lines}", "--no-pager"]),
    "audit_logs": CommandSpec(args=["tail", "-n", "{lines}", "/var/log/audit/audit.log"]),
    "read_log_file": CommandSpec(args=["tail", "-n", "{lines}", "{log_path}"]),
    # Processes (single command)
    "list_processes": CommandSpec(args=["ps", "aux", "--sort=-%cpu"]),
    # Storage
    "list_block_devices": CommandSpec(args=["lsblk", "-o", "NAME,SIZE,TYPE,MOUNTPOINT,FSTYPE,MODEL", "--no-pager"]),
    "disk_usage": CommandSpec(
        args=["df", "-h", "--output=source,size,used,avail,pcent,target"],
        fallback=["df", "-h"],
    ),
    # Directory listing commands
    "list_directories_size": CommandSpec(args=["du", "-b", "--max-depth=1", "{path}"]),
    "list_directories_name": CommandSpec(
        args=["find", "{path}", "-mindepth", "1", "-maxdepth", "1", "-type", "d", "-printf", "%f\\n"]
    ),
    "list_directories_modified": CommandSpec(
        args=["find", "{path}", "-mindepth", "1", "-maxdepth", "1", "-type", "d", "-printf", "%T@\\t%f\\n"]
    ),
    # File listing commands
    "list_files_size": CommandSpec(
        args=["find", "{path}", "-mindepth", "1", "-maxdepth", "1", "-type", "f", "-printf", "%s\\t%f\\n"]
    ),
    "list_files_name": CommandSpec(
        args=["find", "{path}", "-mindepth", "1", "-maxdepth", "1", "-type", "f", "-printf", "%f\\n"]
    ),
    "list_files_modified": CommandSpec(
        args=["find", "{path}", "-mindepth", "1", "-maxdepth", "1", "-type", "f", "-printf", "%T@\\t%f\\n"]
    ),
    # File content
    "read_file": CommandSpec(args=["cat", "{path}"]),
    # === Multi-command tools (CommandGroup) ===
    "network_interfaces": CommandGroup(
        commands={
            "brief": CommandSpec(args=["ip", "-brief", "address"]),
            "detail": CommandSpec(args=["ip", "address"]),
            "stats": CommandSpec(args=["cat", "/proc/net/dev"]),
        }
    ),
    "system_info": CommandGroup(
        commands={
            "hostname": CommandSpec(args=["hostname"]),
            "os_release": CommandSpec(args=["cat", "/etc/os-release"]),
            "kernel": CommandSpec(args=["uname", "-r"]),
            "arch": CommandSpec(args=["uname", "-m"]),
            "uptime": CommandSpec(args=["uptime", "-p"]),
            "boot_time": CommandSpec(args=["uptime", "-s"]),
        }
    ),
    "cpu_info": CommandGroup(
        commands={
            "model": CommandSpec(args=["grep", "-m", "1", "model name", "/proc/cpuinfo"]),
            "logical_cores": CommandSpec(args=["grep", "-c", "^processor", "/proc/cpuinfo"]),
            "physical_cores": CommandSpec(args=["grep", "^core id", "/proc/cpuinfo"]),
            "frequency": CommandSpec(args=["grep", "-m", "1", "cpu MHz", "/proc/cpuinfo"]),
            "load_avg": CommandSpec(args=["cat", "/proc/loadavg"]),
            "top_snapshot": CommandSpec(args=["top", "-bn1"]),
        }
    ),
    "memory_info": CommandGroup(
        commands={
            "free": CommandSpec(args=["free", "-b", "-w"]),
        }
    ),
    "process_info": CommandGroup(
        commands={
            "ps_detail": CommandSpec(
                args=["ps", "-p", "{pid}", "-o", "pid,user,stat,pcpu,pmem,vsz,rss,etime,comm,args"]
            ),
            "proc_status": CommandSpec(args=["cat", "/proc/{pid}/status"]),
        }
    ),
    "hardware_info": CommandGroup(
        commands={
            "lscpu": CommandSpec(args=["lscpu"]),
            "lspci": CommandSpec(args=["lspci"]),
            "lsusb": CommandSpec(args=["lsusb"]),
        }
    ),
}


def get_command(name: str) -> CommandEntry:
    """Get a command specification by name.

    Args:
        name: The command name in the registry.

    Returns:
        The CommandSpec or CommandGroup for the given name.

    Raises:
        TypeError: If the command name is not found in the registry or
        if the entry is not a valid CommandSpec or CommandGroup.
    """
    try:
        cmd = COMMANDS[name]

        # Match both the CommandGroup and CommandSpec
        if not isinstance(cmd, (CommandSpec, CommandGroup)):
            raise TypeError(f"Expected CommandSpec or CommandGroup for '{name}', got {type(cmd).__name__}")
    except KeyError as e:
        raise TypeError(f"CommandSpec for '{name}' not found.") from e

    return cmd


def substitute_command_args(args: list[str], **kwargs) -> list[str]:
    """Substitute placeholder values in command arguments.

    Args:
        args: List of command arguments, possibly with {placeholder} values.
        **kwargs: Key-value pairs to substitute into placeholders.

    Returns:
        List of command arguments with placeholders replaced.

    Raises:
        ValueError: If any placeholders are missing from kwargs or remain
            unsubstituted after replacement.

    Example:
        >>> substitute_command_args(["ps", "-p", "{pid}"], pid=1234)
        ["ps", "-p", "1234"]
    """
    try:
        result = [arg.format(**kwargs) for arg in args]
    except KeyError as e:
        raise ValueError(f"Missing required placeholder: {e}") from e

    # Validate all placeholders were replaced (catches edge cases like nested braces)
    for arg in result:
        if "{" in arg and "}" in arg:
            raise ValueError(f"Unsubstituted placeholder in command argument: {arg}")

    return result


def build_journal_command(
    lines: int,
    unit: str | None = None,
    priority: str | None = None,
    since: str | None = None,
) -> list[str]:
    """Build journalctl command with optional flags.

    Args:
        lines: Number of lines to retrieve.
        unit: Optional service unit filter.
        priority: Optional priority filter (e.g., "err", "warning").
        since: Optional time filter (e.g., "1 hour ago", "today").

    Returns:
        Complete journalctl command arguments.
    """
    cmd = ["journalctl", "-n", str(lines), "--no-pager"]

    if unit:
        cmd.extend(["--unit", unit])
    if priority:
        cmd.extend(["--priority", priority])
    if since:
        cmd.extend(["--since", since])

    return cmd
