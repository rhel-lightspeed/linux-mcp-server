"""Process management tools."""

import psutil
from datetime import datetime

from .decorators import log_tool_output
from .validation import validate_pid


@log_tool_output
async def list_processes() -> str:
    """List running processes."""
    try:
        info = []
        info.append("=== Running Processes ===\n")
        info.append(f"{'PID':<8} {'User':<12} {'CPU%':<8} {'Memory%':<10} {'Status':<12} {'Name':<30} {'Command'}")
        info.append("-" * 120)
        
        # Get all processes
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'username', 'cpu_percent', 'memory_percent', 'status', 'cmdline']):
            try:
                processes.append(proc.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        # Sort by CPU usage (descending)
        processes.sort(key=lambda x: x.get('cpu_percent', 0) or 0, reverse=True)
        
        # Show top processes (limit to reasonable number)
        for proc_info in processes[:100]:  # Show top 100 processes
            pid = proc_info.get('pid', 'N/A')
            username = proc_info.get('username', 'N/A')
            if username and len(username) > 12:
                username = username[:9] + '...'
            
            cpu = proc_info.get('cpu_percent', 0) or 0
            mem = proc_info.get('memory_percent', 0) or 0
            status = proc_info.get('status', 'N/A')
            name = proc_info.get('name', 'N/A')
            if name and len(name) > 30:
                name = name[:27] + '...'
            
            cmdline = proc_info.get('cmdline', [])
            if cmdline:
                cmd = ' '.join(cmdline)
                if len(cmd) > 40:
                    cmd = cmd[:37] + '...'
            else:
                cmd = name
            
            info.append(
                f"{pid:<8} {username:<12} {cpu:<8.1f} {mem:<10.1f} {status:<12} {name:<30} {cmd}"
            )
        
        # Add summary
        total_processes = len(list(psutil.process_iter()))
        info.append(f"\n\nTotal processes: {total_processes}")
        info.append(f"Showing: Top 100 by CPU usage")
        
        return "\n".join(info)
    except Exception as e:
        return f"Error listing processes: {str(e)}"


@log_tool_output
async def get_process_info(pid: int) -> str:
    """Get information about a specific process."""
    try:
        # Validate PID (accepts floats from LLMs)
        pid, error = validate_pid(pid)
        if error:
            return error
        
        # Check if process exists
        if not psutil.pid_exists(pid):
            return f"Process with PID {pid} does not exist."
        
        proc = psutil.Process(pid)
        info = []
        
        info.append(f"=== Process Information for PID {pid} ===\n")
        
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
            info.append(f"\n=== Resource Usage ===")
            cpu_percent = proc.cpu_percent(interval=0.1)
            info.append(f"CPU Percent: {cpu_percent}%")
            
            mem_info = proc.memory_info()
            info.append(f"Memory RSS: {_format_bytes(mem_info.rss)}")
            info.append(f"Memory VMS: {_format_bytes(mem_info.vms)}")
            info.append(f"Memory Percent: {proc.memory_percent():.2f}%")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            info.append("Resource usage: [Access Denied]")
        
        # Timing
        try:
            create_time = datetime.fromtimestamp(proc.create_time())
            info.append(f"\n=== Timing ===")
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
                for i, conn in enumerate(connections[:10]):  # Show first 10
                    info.append(f"  {conn.type.name}: {conn.laddr} -> {conn.raddr if conn.raddr else 'N/A'} [{conn.status}]")
                if len(connections) > 10:
                    info.append(f"  ... and {len(connections) - 10} more")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        
        return "\n".join(info)
    except psutil.NoSuchProcess:
        return f"Process with PID {pid} does not exist."
    except psutil.AccessDenied:
        return f"Access denied to process with PID {pid}. Try running with elevated privileges."
    except Exception as e:
        return f"Error getting process information: {str(e)}"


def _format_bytes(bytes: int) -> str:
    """Format bytes into human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes < 1024.0:
            return f"{bytes:.1f}{unit}"
        bytes /= 1024.0
    return f"{bytes:.1f}PB"

