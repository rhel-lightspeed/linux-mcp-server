"""System information tools."""

import os
import platform
import subprocess
from datetime import datetime, timedelta
import psutil


async def get_system_info() -> str:
    """Get basic system information."""
    info = []
    
    try:
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


async def get_cpu_info() -> str:
    """Get CPU information."""
    info = []
    
    try:
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


async def get_memory_info() -> str:
    """Get memory information."""
    info = []
    
    try:
        # Virtual memory (RAM)
        mem = psutil.virtual_memory()
        info.append("=== RAM Information ===")
        info.append(f"Total: {_format_bytes(mem.total)}")
        info.append(f"Available: {_format_bytes(mem.available)}")
        info.append(f"Used: {_format_bytes(mem.used)} ({mem.percent}%)")
        info.append(f"Free: {_format_bytes(mem.free)}")
        
        if hasattr(mem, 'buffers'):
            info.append(f"Buffers: {_format_bytes(mem.buffers)}")
        if hasattr(mem, 'cached'):
            info.append(f"Cached: {_format_bytes(mem.cached)}")
        
        # Swap memory
        swap = psutil.swap_memory()
        info.append("\n=== Swap Information ===")
        info.append(f"Total: {_format_bytes(swap.total)}")
        info.append(f"Used: {_format_bytes(swap.used)} ({swap.percent}%)")
        info.append(f"Free: {_format_bytes(swap.free)}")
        
        return "\n".join(info)
    except Exception as e:
        return f"Error gathering memory information: {str(e)}"


async def get_disk_usage() -> str:
    """Get disk usage information."""
    info = []
    
    try:
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
                    f"{_format_bytes(usage.total):<10} "
                    f"{_format_bytes(usage.used):<10} "
                    f"{_format_bytes(usage.free):<10} "
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
                info.append(f"Read: {_format_bytes(disk_io.read_bytes)}")
                info.append(f"Write: {_format_bytes(disk_io.write_bytes)}")
                info.append(f"Read Count: {disk_io.read_count}")
                info.append(f"Write Count: {disk_io.write_count}")
        except Exception:
            pass  # Disk I/O might not be available
        
        return "\n".join(info)
    except Exception as e:
        return f"Error gathering disk usage information: {str(e)}"


def _format_bytes(bytes: int) -> str:
    """Format bytes into human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes < 1024.0:
            return f"{bytes:.1f}{unit}"
        bytes /= 1024.0
    return f"{bytes:.1f}PB"

