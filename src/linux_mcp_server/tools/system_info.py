"""System information tools."""

import asyncio
import os
import platform
import subprocess
from datetime import datetime, timedelta
from typing import Optional
import psutil

from .decorators import log_tool_output
from .ssh_executor import execute_command
from .utils import format_bytes


@log_tool_output
async def get_system_info(host: Optional[str] = None, username: Optional[str] = None) -> str:
    """
    Get basic system information.
    
    Args:
        host: Optional remote host to connect to
        username: Optional SSH username (required if host is provided)
        
    Returns:
        Formatted string with basic system information
    """
    info = []
    
    try:
        if host:
            # Remote execution - use Linux commands
            # Hostname
            returncode, stdout, _ = await execute_command(
                ["hostname"],
                host=host,
                username=username
            )
            if returncode == 0 and stdout:
                info.append(f"Hostname: {stdout.strip()}")
            
            # OS Information from /etc/os-release
            returncode, stdout, _ = await execute_command(
                ["cat", "/etc/os-release"],
                host=host,
                username=username
            )
            if returncode == 0 and stdout:
                os_info = {}
                for line in stdout.split('\n'):
                    line = line.strip()
                    if "=" in line:
                        key, value = line.split("=", 1)
                        os_info[key] = value.strip('"')
                
                info.append(f"Operating System: {os_info.get('PRETTY_NAME', 'Unknown')}")
                if 'VERSION_ID' in os_info:
                    info.append(f"OS Version: {os_info['VERSION_ID']}")
            
            # Kernel version
            returncode, stdout, _ = await execute_command(
                ["uname", "-r"],
                host=host,
                username=username
            )
            if returncode == 0 and stdout:
                info.append(f"Kernel Version: {stdout.strip()}")
            
            # Architecture
            returncode, stdout, _ = await execute_command(
                ["uname", "-m"],
                host=host,
                username=username
            )
            if returncode == 0 and stdout:
                info.append(f"Architecture: {stdout.strip()}")
            
            # Uptime
            returncode, stdout, _ = await execute_command(
                ["uptime", "-p"],
                host=host,
                username=username
            )
            if returncode == 0 and stdout:
                info.append(f"Uptime: {stdout.strip()}")
            
            # Boot time
            returncode, stdout, _ = await execute_command(
                ["uptime", "-s"],
                host=host,
                username=username
            )
            if returncode == 0 and stdout:
                info.append(f"Boot Time: {stdout.strip()}")
        else:
            # Local execution - use psutil and platform
            # Hostname
            hostname = platform.node()
            info.append(f"Hostname: {hostname}")
            
            # OS Information
            if os.path.exists("/etc/os-release"):
                os_info = {}
                with open("/etc/os-release", "r") as f:
                    for line in f:
                        line = line.strip()
                        if "=" in line:
                            key, value = line.split("=", 1)
                            os_info[key] = value.strip('"')
                
                info.append(f"Operating System: {os_info.get('PRETTY_NAME', 'Unknown')}")
                if 'VERSION_ID' in os_info:
                    info.append(f"OS Version: {os_info['VERSION_ID']}")
            else:
                info.append(f"Operating System: {platform.system()} {platform.release()}")
            
            # Kernel version
            kernel = platform.release()
            info.append(f"Kernel Version: {kernel}")
            
            # Architecture
            arch = platform.machine()
            info.append(f"Architecture: {arch}")
            
            # Uptime
            boot_time = datetime.fromtimestamp(psutil.boot_time())
            uptime = datetime.now() - boot_time
            days = uptime.days
            hours, remainder = divmod(uptime.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            info.append(f"Uptime: {days}d {hours}h {minutes}m {seconds}s")
            info.append(f"Boot Time: {boot_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        return "\n".join(info)
    except Exception as e:
        return f"Error gathering system information: {str(e)}"


@log_tool_output
async def get_cpu_info(host: Optional[str] = None, username: Optional[str] = None) -> str:
    """
    Get CPU information.
    
    Args:
        host: Optional remote host to connect to
        username: Optional SSH username (required if host is provided)
        
    Returns:
        Formatted string with CPU information
    """
    info = []
    
    try:
        if host:
            # Remote execution - use Linux commands
            # Get CPU model from /proc/cpuinfo
            returncode, stdout, _ = await execute_command(
                ["grep", "-m", "1", "model name", "/proc/cpuinfo"],
                host=host,
                username=username
            )
            if returncode == 0 and stdout:
                cpu_model = stdout.split(":", 1)[1].strip() if ":" in stdout else stdout.strip()
                info.append(f"CPU Model: {cpu_model}")
            
            # Get CPU core counts from /proc/cpuinfo
            returncode, stdout, _ = await execute_command(
                ["grep", "-c", "^processor", "/proc/cpuinfo"],
                host=host,
                username=username
            )
            if returncode == 0 and stdout:
                logical_cores = int(stdout.strip())
                info.append(f"CPU Logical Cores (threads): {logical_cores}")
            
            # Get physical cores (using core id uniqueness)
            returncode, stdout, _ = await execute_command(
                ["grep", "^core id", "/proc/cpuinfo"],
                host=host,
                username=username
            )
            if returncode == 0 and stdout:
                core_ids = set(line.split(":", 1)[1].strip() for line in stdout.strip().split('\n') if ":" in line)
                physical_cores = len(core_ids)
                info.append(f"CPU Physical Cores: {physical_cores}")
            
            # Get CPU frequency from /proc/cpuinfo
            returncode, stdout, _ = await execute_command(
                ["grep", "-m", "1", "cpu MHz", "/proc/cpuinfo"],
                host=host,
                username=username
            )
            if returncode == 0 and stdout and ":" in stdout:
                cpu_mhz = stdout.split(":", 1)[1].strip()
                info.append(f"CPU Frequency: Current={cpu_mhz}MHz")
            
            # Get load average
            returncode, stdout, _ = await execute_command(
                ["cat", "/proc/loadavg"],
                host=host,
                username=username
            )
            if returncode == 0 and stdout:
                load_parts = stdout.strip().split()
                if len(load_parts) >= 3:
                    info.append(f"\nLoad Average (1m, 5m, 15m): {load_parts[0]}, {load_parts[1]}, {load_parts[2]}")
            
            # Get CPU usage using top (one iteration)
            returncode, stdout, _ = await execute_command(
                ["top", "-bn1"],
                host=host,
                username=username
            )
            if returncode == 0 and stdout:
                for line in stdout.split('\n'):
                    if 'Cpu(s):' in line or '%Cpu' in line:
                        info.append(f"\n{line.strip()}")
                        break
        else:
            # Local execution - use psutil
            # CPU count
            physical_cores = psutil.cpu_count(logical=False)
            logical_cores = psutil.cpu_count(logical=True)
            info.append(f"CPU Physical Cores: {physical_cores}")
            info.append(f"CPU Logical Cores (threads): {logical_cores}")
            
            # CPU frequency
            try:
                cpu_freq = psutil.cpu_freq()
                if cpu_freq:
                    info.append(f"CPU Frequency: Current={cpu_freq.current:.2f}MHz, Min={cpu_freq.min:.2f}MHz, Max={cpu_freq.max:.2f}MHz")
            except Exception:
                pass  # CPU frequency might not be available
            
            # CPU usage per core
            cpu_percent = psutil.cpu_percent(interval=1, percpu=True)
            info.append(f"\nCPU Usage per Core:")
            for i, percent in enumerate(cpu_percent):
                info.append(f"  Core {i}: {percent}%")
            
            # Overall CPU usage
            overall_cpu = psutil.cpu_percent(interval=1)
            info.append(f"\nOverall CPU Usage: {overall_cpu}%")
            
            # Load average
            load_avg = os.getloadavg()
            info.append(f"\nLoad Average (1m, 5m, 15m): {load_avg[0]:.2f}, {load_avg[1]:.2f}, {load_avg[2]:.2f}")
            
            # Try to get CPU model info from /proc/cpuinfo
            try:
                with open("/proc/cpuinfo", "r") as f:
                    for line in f:
                        if line.startswith("model name"):
                            cpu_model = line.split(":")[1].strip()
                            info.insert(0, f"CPU Model: {cpu_model}")
                            break
            except Exception:
                pass
        
        return "\n".join(info)
    except Exception as e:
        return f"Error gathering CPU information: {str(e)}"


@log_tool_output
async def get_memory_info(host: Optional[str] = None, username: Optional[str] = None) -> str:
    """
    Get memory information.
    
    Args:
        host: Optional remote host to connect to
        username: Optional SSH username (required if host is provided)
        
    Returns:
        Formatted string with memory information
    """
    info = []
    
    try:
        if host:
            # Remote execution - use free command
            returncode, stdout, _ = await execute_command(
                ["free", "-b"],
                host=host,
                username=username
            )
            
            if returncode == 0 and stdout:
                lines = stdout.strip().split('\n')
                
                # Parse memory line
                for line in lines:
                    if line.startswith('Mem:'):
                        parts = line.split()
                        if len(parts) >= 7:
                            total = int(parts[1])
                            used = int(parts[2])
                            free = int(parts[3])
                            available = int(parts[6]) if len(parts) > 6 else free
                            percent = (used / total * 100) if total > 0 else 0
                            
                            info.append("=== RAM Information ===")
                            info.append(f"Total: {format_bytes(total)}")
                            info.append(f"Available: {format_bytes(available)}")
                            info.append(f"Used: {format_bytes(used)} ({percent:.1f}%)")
                            info.append(f"Free: {format_bytes(free)}")
                    
                    elif line.startswith('Swap:'):
                        parts = line.split()
                        if len(parts) >= 4:
                            total = int(parts[1])
                            used = int(parts[2])
                            free = int(parts[3])
                            percent = (used / total * 100) if total > 0 else 0
                            
                            info.append("\n=== Swap Information ===")
                            info.append(f"Total: {format_bytes(total)}")
                            info.append(f"Used: {format_bytes(used)} ({percent:.1f}%)")
                            info.append(f"Free: {format_bytes(free)}")
        else:
            # Local execution - use psutil
            # Virtual memory (RAM)
            mem = psutil.virtual_memory()
            info.append("=== RAM Information ===")
            info.append(f"Total: {format_bytes(mem.total)}")
            info.append(f"Available: {format_bytes(mem.available)}")
            info.append(f"Used: {format_bytes(mem.used)} ({mem.percent}%)")
            info.append(f"Free: {format_bytes(mem.free)}")
            
            if hasattr(mem, 'buffers'):
                info.append(f"Buffers: {format_bytes(mem.buffers)}")
            if hasattr(mem, 'cached'):
                info.append(f"Cached: {format_bytes(mem.cached)}")
            
            # Swap memory
            swap = psutil.swap_memory()
            info.append("\n=== Swap Information ===")
            info.append(f"Total: {format_bytes(swap.total)}")
            info.append(f"Used: {format_bytes(swap.used)} ({swap.percent}%)")
            info.append(f"Free: {format_bytes(swap.free)}")
        
        return "\n".join(info)
    except Exception as e:
        return f"Error gathering memory information: {str(e)}"


@log_tool_output
async def get_disk_usage(host: Optional[str] = None, username: Optional[str] = None) -> str:
    """
    Get disk usage information.
    
    Args:
        host: Optional remote host to connect to
        username: Optional SSH username (required if host is provided)
        
    Returns:
        Formatted string with disk usage information
    """
    info = []
    
    try:
        if host:
            # Remote execution - use df command
            returncode, stdout, _ = await execute_command(
                ["df", "-h", "--output=source,size,used,avail,pcent,target"],
                host=host,
                username=username
            )
            
            if returncode == 0 and stdout:
                info.append("=== Filesystem Usage ===\n")
                info.append(stdout)
            else:
                # Fallback to basic df command
                returncode, stdout, _ = await execute_command(
                    ["df", "-h"],
                    host=host,
                    username=username
                )
                if returncode == 0 and stdout:
                    info.append("=== Filesystem Usage ===\n")
                    info.append(stdout)
        else:
            # Local execution - use psutil
            info.append("=== Filesystem Usage ===\n")
            info.append(f"{'Filesystem':<30} {'Size':<10} {'Used':<10} {'Avail':<10} {'Use%':<6} {'Mounted on'}")
            info.append("-" * 90)
            
            # Get all disk partitions
            partitions = psutil.disk_partitions(all=False)
            
            for partition in partitions:
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    info.append(
                        f"{partition.device:<30} "
                        f"{format_bytes(usage.total):<10} "
                        f"{format_bytes(usage.used):<10} "
                        f"{format_bytes(usage.free):<10} "
                        f"{usage.percent:<6.1f} "
                        f"{partition.mountpoint}"
                    )
                except PermissionError:
                    # Skip partitions we can't access
                    continue
                except Exception as e:
                    info.append(f"{partition.device:<30} Error: {str(e)}")
            
            # Disk I/O statistics
            try:
                disk_io = psutil.disk_io_counters()
                if disk_io:
                    info.append("\n=== Disk I/O Statistics (since boot) ===")
                    info.append(f"Read: {format_bytes(disk_io.read_bytes)}")
                    info.append(f"Write: {format_bytes(disk_io.write_bytes)}")
                    info.append(f"Read Count: {disk_io.read_count}")
                    info.append(f"Write Count: {disk_io.write_count}")
            except Exception:
                pass  # Disk I/O might not be available
        
        return "\n".join(info)
    except Exception as e:
        return f"Error gathering disk usage information: {str(e)}"


@log_tool_output
async def get_hardware_info(host: Optional[str] = None, username: Optional[str] = None) -> str:
    """
    Get hardware information.
    
    Args:
        host: Optional remote host to connect to
        username: Optional SSH username (required if host is provided)
        
    Returns:
        Formatted string with hardware information
    """
    try:
        info = []
        info.append("=== Hardware Information ===\n")
        
        # Try lscpu for CPU info
        try:
            returncode, stdout, stderr = await execute_command(
                ["lscpu"],
                host=host,
                username=username
            )
            
            if returncode == 0:
                info.append("=== CPU Architecture (lscpu) ===")
                info.append(stdout)
        except FileNotFoundError:
            info.append("CPU info: lscpu command not available")
        
        # Try lspci for PCI devices
        try:
            returncode, stdout, stderr = await execute_command(
                ["lspci"],
                host=host,
                username=username
            )
            
            if returncode == 0:
                pci_lines = stdout.strip().split('\n')
                
                info.append("\n=== PCI Devices ===")
                # Show first 50 devices to avoid overwhelming output
                for line in pci_lines[:50]:
                    info.append(line)
                
                if len(pci_lines) > 50:
                    info.append(f"\n... and {len(pci_lines) - 50} more PCI devices")
        except FileNotFoundError:
            info.append("\nPCI devices: lspci command not available")
        
        # Try lsusb for USB devices
        try:
            returncode, stdout, stderr = await execute_command(
                ["lsusb"],
                host=host,
                username=username
            )
            
            if returncode == 0:
                info.append("\n\n=== USB Devices ===")
                info.append(stdout)
        except FileNotFoundError:
            info.append("\nUSB devices: lsusb command not available")
        
        # Memory hardware info from dmidecode (requires root)
        try:
            returncode, stdout, stderr = await execute_command(
                ["dmidecode", "-t", "memory"],
                host=host,
                username=username
            )
            
            if returncode == 0:
                info.append("\n\n=== Memory Hardware (dmidecode) ===")
                info.append(stdout)
            elif "Permission denied" in stderr:
                info.append("\n\nMemory hardware info: Requires root privileges (dmidecode)")
        except FileNotFoundError:
            info.append("\nMemory hardware info: dmidecode command not available")
        
        if len(info) == 1:  # Only the header
            info.append("No hardware information tools available.")
        
        return "\n".join(info)
    except Exception as e:
        return f"Error getting hardware information: {str(e)}"

