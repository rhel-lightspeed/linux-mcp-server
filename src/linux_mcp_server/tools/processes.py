"""Process management tools."""

import typing as t

from datetime import datetime

import psutil

from mcp.types import ToolAnnotations
from pydantic import Field

from linux_mcp_server.audit import log_tool_call
from linux_mcp_server.connection.ssh import execute_command
from linux_mcp_server.server import mcp
from linux_mcp_server.utils import format_bytes
from linux_mcp_server.utils import is_ipv6_link_local
from linux_mcp_server.utils.decorators import disallow_local_execution_in_containers
from linux_mcp_server.utils.types import Host
from linux_mcp_server.utils.validation import validate_pid


def _truncate(value: str | None, max_len: int, suffix: str = "...") -> str:
    """Truncate a string to max length with suffix.

    Args:
        value: The string value to truncate (or None)
        max_len: Maximum length including suffix
        suffix: Suffix to append when truncated (default "...")

    Returns:
        Truncated string, original if short enough, or "N/A" if None
    """
    if value is None:
        return "N/A"
    if len(value) <= max_len:
        return value
    return value[: max_len - len(suffix)] + suffix


def _format_cmdline(cmdline: list[str] | None, fallback: str, max_len: int = 40) -> str:
    """Format command line with fallback and truncation.

    Args:
        cmdline: List of command line arguments (should be pre-sanitized!)
        fallback: Fallback value if cmdline is empty/None (typically process name)
        max_len: Maximum length for the formatted command

    Returns:
        Formatted, truncated command string
    """
    if cmdline:
        cmd = " ".join(cmdline)
        return _truncate(cmd, max_len)
    return fallback


@mcp.tool(
    title="List processes",
    description="List running processes",
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def list_processes(
    host: Host | None = None,
) -> str:
    try:
        if host:
            # Remote execution - use ps command
            returncode, stdout, _ = await execute_command(["ps", "aux", "--sort=-%cpu"], host=host)

            if returncode == 0 and stdout:
                info = []
                info.append("=== Running Processes ===\n")

                lines = stdout.strip().split("\n")
                # Take header and top 100 processes
                if len(lines) > 101:
                    info.append("\n".join(lines[:101]))
                    info.append(f"\n\nTotal processes: {len(lines) - 1}")
                    info.append("Showing: Top 100 by CPU usage")
                else:
                    info.append(stdout)
                    info.append(f"\n\nTotal processes: {len(lines) - 1}")

                return "\n".join(info)
            else:
                return "Error executing ps command on remote host"
        else:
            # Local execution - use psutil
            info = []
            info.append("=== Running Processes ===\n")
            info.append(f"{'PID':<8} {'User':<12} {'CPU%':<8} {'Memory%':<10} {'Status':<12} {'Name':<30} {'Command'}")
            info.append("-" * 120)

            # Get all processes
            processes = []
            for proc in psutil.process_iter(
                ["pid", "name", "username", "cpu_percent", "memory_percent", "status", "cmdline"],
            ):
                try:
                    processes.append(proc.info)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

            # Sort by CPU usage (descending)
            processes.sort(key=lambda x: x.get("cpu_percent", 0) or 0, reverse=True)

            # Show top processes (limit to reasonable number)
            for proc_info in processes[:100]:  # Show top 100 processes
                pid = proc_info.get("pid", "N/A")
                username_val = _truncate(proc_info.get("username"), 12)
                cpu = proc_info.get("cpu_percent", 0) or 0
                mem = proc_info.get("memory_percent", 0) or 0
                status = proc_info.get("status", "N/A")
                name = _truncate(proc_info.get("name"), 30)
                cmd = _format_cmdline(proc_info.get("cmdline"), name, 40)

                info.append(f"{pid:<8} {username_val:<12} {cpu:<8.1f} {mem:<10.1f} {status:<12} {name:<30} {cmd}")

            # Add summary
            total_processes = len(list(psutil.process_iter()))
            info.append(f"\n\nTotal processes: {total_processes}")
            info.append("Showing: Top 100 by CPU usage")

            return "\n".join(info)
    except Exception as e:
        return f"Error listing processes: {str(e)}"


@mcp.tool(
    title="Process details",
    description="Get information about a specific process.",
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def get_process_info(  # noqa: C901
    pid: t.Annotated[int, Field(description="Process ID")],
    host: Host | None = None,
) -> str:
    # Validate PID (accepts floats from LLMs)
    validated_pid, error = validate_pid(pid)
    if error:
        return error

    if validated_pid is None:
        return "Invalid PID"

    try:
        if host:
            # Remote execution - use ps command
            returncode, stdout, _ = await execute_command(
                ["ps", "-p", str(validated_pid), "-o", "pid,user,stat,pcpu,pmem,vsz,rss,etime,comm,args"],
                host=host,
            )

            if returncode != 0:
                return f"Process with PID {validated_pid} does not exist on remote host."

            if stdout:
                info = []
                info.append(f"=== Process Information for PID {validated_pid} ===\n")
                info.append(stdout)

                # Try to get more details with /proc
                returncode, stdout, _ = await execute_command(
                    ["cat", f"/proc/{validated_pid}/status"],
                    host=host,
                )

                if returncode == 0 and stdout:
                    info.append("\n=== Detailed Status (/proc) ===")
                    # Filter to show most relevant fields
                    relevant_fields = [
                        "Name:",
                        "State:",
                        "Tgid:",
                        "Pid:",
                        "PPid:",
                        "Threads:",
                        "VmPeak:",
                        "VmSize:",
                        "VmRSS:",
                    ]
                    for line in stdout.split("\n"):
                        if any(field in line for field in relevant_fields):
                            info.append(line)

                return "\n".join(info)
            else:
                return f"Process with PID {validated_pid} does not exist on remote host."
        else:
            # Local execution - use psutil
            # Check if process exists
            if not psutil.pid_exists(validated_pid):
                return f"Process with PID {validated_pid} does not exist."

            proc = psutil.Process(validated_pid)
            info = []

            info.append(f"=== Process Information for PID {validated_pid} ===\n")

            # Basic info
            try:
                info.append(f"Name: {proc.name()}")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

            try:
                info.append(f"Executable: {proc.exe()}")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                info.append("Executable: [Access Denied]")

            try:
                info.append(f"Command Line: {' '.join(proc.cmdline())}")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

            try:
                info.append(f"Status: {proc.status()}")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

            try:
                info.append(f"User: {proc.username()}")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

            # Process IDs
            try:
                info.append(f"\nPID: {proc.pid}")
                info.append(f"Parent PID: {proc.ppid()}")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

            # Resource usage
            try:
                info.append("\n=== Resource Usage ===")
                cpu_percent = proc.cpu_percent(interval=0.1)
                info.append(f"CPU Percent: {cpu_percent}%")

                mem_info = proc.memory_info()
                info.append(f"Memory RSS: {format_bytes(mem_info.rss)}")
                info.append(f"Memory VMS: {format_bytes(mem_info.vms)}")
                info.append(f"Memory Percent: {proc.memory_percent():.2f}%")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                info.append("Resource usage: [Access Denied]")

            # Timing
            try:
                create_time = datetime.fromtimestamp(proc.create_time())
                info.append("\n=== Timing ===")
                info.append(f"Created: {create_time.strftime('%Y-%m-%d %H:%M:%S')}")

                cpu_times = proc.cpu_times()
                info.append(f"CPU Time (user): {cpu_times.user:.2f}s")
                info.append(f"CPU Time (system): {cpu_times.system:.2f}s")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

            # Threads
            try:
                num_threads = proc.num_threads()
                info.append(f"\nThreads: {num_threads}")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

            # File descriptors
            try:
                num_fds = proc.num_fds()
                info.append(f"Open File Descriptors: {num_fds}")
            except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError):
                pass  # Not available on all systems

            # Connections
            try:
                connections = proc.net_connections()
                # Filter out link-local connections
                filtered_conns = [
                    c
                    for c in connections
                    if not (c.laddr and is_ipv6_link_local(c.laddr.ip))
                    and not (c.raddr and is_ipv6_link_local(c.raddr.ip))
                ]
                if filtered_conns:
                    info.append(f"\n=== Network Connections ({len(filtered_conns)}) ===")
                    for conn in filtered_conns[:10]:  # Show first 10
                        local_addr = f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else "N/A"
                        remote_addr = f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else "N/A"
                        info.append(
                            f"  {conn.type.name}: {local_addr} -> {remote_addr} [{conn.status}]",
                        )
                    if len(filtered_conns) > 10:
                        info.append(f"  ... and {len(filtered_conns) - 10} more")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

            return "\n".join(info)
    except psutil.NoSuchProcess:
        return f"Process with PID {validated_pid} does not exist."
    except psutil.AccessDenied:
        return f"Access denied to process with PID {validated_pid}. Try running with elevated privileges."
    except Exception as e:
        return f"Error getting process information: {str(e)}"
