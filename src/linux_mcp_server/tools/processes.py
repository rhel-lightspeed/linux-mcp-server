"""Process management tools."""

from datetime import datetime

import psutil

from .ssh_executor import execute_command
from .utils import format_bytes
from .validation import validate_pid


async def list_processes(
    host: str | None = None,
    username: str | None = None,
) -> str:
    """
    List running processes.

    Args:
        host: Optional remote host to connect to
        username: Optional SSH username (required if host is provided)

    Returns:
        Formatted string with process list
    """
    try:
        if host:
            # Remote execution - use ps command
            returncode, stdout, _ = await execute_command(["ps", "aux", "--sort=-%cpu"], host=host, username=username)

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
                username_val = proc_info.get("username", "N/A")
                if username_val and len(username_val) > 12:
                    username_val = username_val[:9] + "..."

                cpu = proc_info.get("cpu_percent", 0) or 0
                mem = proc_info.get("memory_percent", 0) or 0
                status = proc_info.get("status", "N/A")
                name = proc_info.get("name", "N/A")
                if name and len(name) > 30:
                    name = name[:27] + "..."

                cmdline = proc_info.get("cmdline", [])
                if cmdline:
                    cmd = " ".join(cmdline)
                    if len(cmd) > 40:
                        cmd = cmd[:37] + "..."
                else:
                    cmd = name

                info.append(f"{pid:<8} {username_val:<12} {cpu:<8.1f} {mem:<10.1f} {status:<12} {name:<30} {cmd}")

            # Add summary
            total_processes = len(list(psutil.process_iter()))
            info.append(f"\n\nTotal processes: {total_processes}")
            info.append("Showing: Top 100 by CPU usage")

            return "\n".join(info)
    except Exception as e:
        return f"Error listing processes: {str(e)}"


async def get_process_info(  # noqa: C901
    pid: int,
    host: str | None = None,
    username: str | None = None,
) -> str:
    """
    Get information about a specific process.

    Args:
        pid: Process ID
        host: Optional remote host to connect to
        username: Optional SSH username (required if host is provided)

    Returns:
        Formatted string with process information
    """
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
                username=username,
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
                    username=username,
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
                connections = proc.connections()
                if connections:
                    info.append(f"\n=== Network Connections ({len(connections)}) ===")
                    for _, conn in enumerate(connections[:10]):  # Show first 10
                        info.append(
                            f"  {conn.type.name}: {conn.laddr} -> {conn.raddr if conn.raddr else 'N/A'} [{conn.status}]",
                        )
                    if len(connections) > 10:
                        info.append(f"  ... and {len(connections) - 10} more")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

            return "\n".join(info)
    except psutil.NoSuchProcess:
        return f"Process with PID {validated_pid} does not exist."
    except psutil.AccessDenied:
        return f"Access denied to process with PID {validated_pid}. Try running with elevated privileges."
    except Exception as e:
        return f"Error getting process information: {str(e)}"
