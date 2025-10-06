"""Storage and hardware tools."""

import asyncio
import subprocess
import psutil
from pathlib import Path

from .validation import validate_positive_int


async def list_block_devices() -> str:
    """List block devices."""
    try:
        # Try using lsblk first (most readable)
        proc = await asyncio.create_subprocess_exec(
            "lsblk", "-o", "NAME,SIZE,TYPE,MOUNTPOINT,FSTYPE,MODEL", "--no-pager",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        
        if proc.returncode == 0:
            output = stdout.decode()
            result = ["=== Block Devices ===\n"]
            result.append(output)
            
            # Add disk I/O per-disk stats if available
            try:
                disk_io_per_disk = psutil.disk_io_counters(perdisk=True)
                if disk_io_per_disk:
                    result.append("\n=== Disk I/O Statistics (per disk) ===")
                    for disk, stats in sorted(disk_io_per_disk.items()):
                        result.append(f"\n{disk}:")
                        result.append(f"  Read: {_format_bytes(stats.read_bytes)}")
                        result.append(f"  Write: {_format_bytes(stats.write_bytes)}")
                        result.append(f"  Read Count: {stats.read_count}")
                        result.append(f"  Write Count: {stats.write_count}")
            except Exception:
                pass
            
            return "\n".join(result)
        else:
            # Fallback to listing partitions with psutil
            result = ["=== Block Devices (fallback) ===\n"]
            partitions = psutil.disk_partitions(all=True)
            
            for partition in partitions:
                result.append(f"\nDevice: {partition.device}")
                result.append(f"  Mountpoint: {partition.mountpoint}")
                result.append(f"  Filesystem: {partition.fstype}")
                result.append(f"  Options: {partition.opts}")
            
            return "\n".join(result)
    except FileNotFoundError:
        # If lsblk is not available, use psutil
        result = ["=== Block Devices ===\n"]
        partitions = psutil.disk_partitions(all=True)
        
        for partition in partitions:
            result.append(f"\nDevice: {partition.device}")
            result.append(f"  Mountpoint: {partition.mountpoint}")
            result.append(f"  Filesystem: {partition.fstype}")
            result.append(f"  Options: {partition.opts}")
        
        return "\n".join(result)
    except Exception as e:
        return f"Error listing block devices: {str(e)}"


def _format_bytes(bytes: int) -> str:
    """Format bytes into human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes < 1024.0:
            return f"{bytes:.1f}{unit}"
        bytes /= 1024.0
    return f"{bytes:.1f}PB"


async def list_directories_by_size(path: str, top_n: int) -> str:
    """
    List directories under a specified path sorted by size (largest first).
    
    This function uses efficient Linux primitives (du command) to calculate directory
    sizes, making it much faster than Python-based directory traversal.
    
    Args:
        path: The directory path to analyze
        top_n: Number of top directories to return (1-1000). Accepts int or float 
               (floats are truncated to integers)
    
    Returns:
        Formatted string with directory sizes, or error message if validation fails
    
    Security Features:
        - Path validation and resolution using pathlib
        - Command parameters passed as list (not shell string)
        - Input sanitization for all parameters
        - Graceful error handling for permission issues
    """
    import os
    from pathlib import Path
    
    try:
        # Validate and normalize top_n parameter
        top_n, error = validate_positive_int(
            top_n,
            param_name="top_n",
            min_value=1,
            max_value=1000
        )
        if error:
            return error
        
        # Validate and resolve path using pathlib for security
        try:
            path_obj = Path(path).resolve(strict=True)
        except (OSError, RuntimeError):
            return f"Error: Path does not exist or cannot be resolved: {path}"
        
        # Check if path is a directory
        if not path_obj.is_dir():
            return f"Error: Path is not a directory: {path}"
        
        # Check if we have read permissions
        if not os.access(path_obj, os.R_OK):
            return f"Error: Permission denied to read directory: {path}"
        
        # Use du command to get directory sizes efficiently
        # -b: display sizes in bytes
        # --max-depth=1: only immediate subdirectories (conflicts with -s, so we don't use it)
        # Note: du outputs permission errors to stderr but continues processing,
        # so we suppress/ignore stderr and only use stdout results
        # du may return non-zero if it encounters permission errors, but still produces valid output
        proc = await asyncio.create_subprocess_exec(
            "du", "-b", "--max-depth=1", str(path_obj),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL  # Suppress permission denied errors
        )
        stdout, _ = await proc.communicate()
        
        # Parse output - du may return non-zero on permission errors but still give valid data
        lines = stdout.decode().strip().split('\n')
        dir_sizes = []
        
        for line in lines:
            if not line:
                continue
            parts = line.split('\t', 1)
            if len(parts) == 2:
                try:
                    size = int(parts[0])
                    dir_path = Path(parts[1])
                    # Skip the parent directory itself
                    if dir_path != path_obj:
                        dir_sizes.append((dir_path.name, size))
                except (ValueError, IndexError):
                    continue
        
        if not dir_sizes:
            # Only error if we got no output AND a bad return code
            if proc.returncode != 0:
                return f"Error: du command failed and returned no directory data"
            return f"No subdirectories found in: {path}"
        
        # Sort by size (descending) and take top N
        dir_sizes.sort(key=lambda x: x[1], reverse=True)
        top_dirs = dir_sizes[:top_n]
        
        # Format output
        result = []
        result.append(f"=== Top {len(top_dirs)} Largest Directories ===")
        result.append(f"Path: {path_obj}")
        result.append(f"\nTotal subdirectories found: {len(dir_sizes)}\n")
        
        for i, (dir_name, size) in enumerate(top_dirs, 1):
            result.append(f"{i}. {dir_name}")
            result.append(f"   Size: {_format_bytes(size)}")
        
        return "\n".join(result)
        
    except Exception as e:
        return f"Error analyzing directories: {str(e)}"


async def list_directories_by_name(path: str, reverse: bool = False) -> str:
    """
    List directories under a specified path sorted by name.
    
    This function uses efficient Linux primitives (find and sort) to list directories.
    
    Args:
        path: The directory path to analyze
        reverse: If True, sort in reverse alphabetical order (Z-A)
    
    Returns:
        Formatted string with directory names, or error message if validation fails
    """
    import os
    from pathlib import Path
    
    try:
        # Validate and resolve path
        try:
            path_obj = Path(path).resolve(strict=True)
        except (OSError, RuntimeError):
            return f"Error: Path does not exist or cannot be resolved: {path}"
        
        if not path_obj.is_dir():
            return f"Error: Path is not a directory: {path}"
        
        if not os.access(path_obj, os.R_OK):
            return f"Error: Permission denied to read directory: {path}"
        
        # Use find to list only immediate subdirectories
        # Suppress stderr to avoid permission denied errors cluttering output
        proc = await asyncio.create_subprocess_exec(
            "find", str(path_obj), "-mindepth", "1", "-maxdepth", "1", "-type", "d",
            "-printf", "%f\\n",
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL
        )
        stdout, _ = await proc.communicate()
        
        if proc.returncode != 0:
            return f"Error running find command: command failed with return code {proc.returncode}"
        
        # Parse and sort output
        directories = [line for line in stdout.decode().strip().split('\n') if line]
        
        if not directories:
            return f"No subdirectories found in: {path}"
        
        # Sort alphabetically
        directories.sort(reverse=reverse)
        
        # Format output
        result = []
        sort_order = "Reverse Alphabetical" if reverse else "Alphabetical"
        result.append(f"=== Directories ({sort_order}) ===")
        result.append(f"Path: {path_obj}")
        result.append(f"\nTotal subdirectories found: {len(directories)}\n")
        
        for i, dir_name in enumerate(directories, 1):
            result.append(f"{i}. {dir_name}")
        
        return "\n".join(result)
        
    except Exception as e:
        return f"Error listing directories: {str(e)}"


async def list_directories_by_modified_date(path: str, newest_first: bool = True) -> str:
    """
    List directories under a specified path sorted by modification date.
    
    This function uses efficient Linux primitives (find) to list directories with timestamps.
    
    Args:
        path: The directory path to analyze
        newest_first: If True, show newest first; if False, show oldest first
    
    Returns:
        Formatted string with directory names and dates, or error message if validation fails
    """
    import os
    from pathlib import Path
    from datetime import datetime
    
    try:
        # Validate and resolve path
        try:
            path_obj = Path(path).resolve(strict=True)
        except (OSError, RuntimeError):
            return f"Error: Path does not exist or cannot be resolved: {path}"
        
        if not path_obj.is_dir():
            return f"Error: Path is not a directory: {path}"
        
        if not os.access(path_obj, os.R_OK):
            return f"Error: Permission denied to read directory: {path}"
        
        # Use find with modification time
        # -printf "%T@\t%f\n" outputs: timestamp filename
        # Suppress stderr to avoid permission denied errors cluttering output
        proc = await asyncio.create_subprocess_exec(
            "find", str(path_obj), "-mindepth", "1", "-maxdepth", "1", "-type", "d",
            "-printf", "%T@\\t%f\\n",
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL
        )
        stdout, _ = await proc.communicate()
        
        if proc.returncode != 0:
            return f"Error running find command: command failed with return code {proc.returncode}"
        
        # Parse output
        directories = []
        for line in stdout.decode().strip().split('\n'):
            if line:
                parts = line.split('\t', 1)
                if len(parts) == 2:
                    try:
                        timestamp = float(parts[0])
                        dir_name = parts[1]
                        directories.append((timestamp, dir_name))
                    except ValueError:
                        continue
        
        if not directories:
            return f"No subdirectories found in: {path}"
        
        # Sort by timestamp
        directories.sort(key=lambda x: x[0], reverse=newest_first)
        
        # Format output
        result = []
        sort_order = "Newest First" if newest_first else "Oldest First"
        result.append(f"=== Directories ({sort_order}) ===")
        result.append(f"Path: {path_obj}")
        result.append(f"\nTotal subdirectories found: {len(directories)}\n")
        
        for i, (timestamp, dir_name) in enumerate(directories, 1):
            dt = datetime.fromtimestamp(timestamp)
            result.append(f"{i}. {dir_name}")
            result.append(f"   Modified: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
        
        return "\n".join(result)
        
    except Exception as e:
        return f"Error listing directories: {str(e)}"

