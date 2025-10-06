"""Storage and hardware tools."""

import asyncio
import subprocess
import psutil
from pathlib import Path


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


async def get_hardware_info() -> str:
    """Get hardware information."""
    try:
        info = []
        info.append("=== Hardware Information ===\n")
        
        # Try lscpu for CPU info
        try:
            proc = await asyncio.create_subprocess_exec(
                "lscpu",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            
            if proc.returncode == 0:
                info.append("=== CPU Architecture (lscpu) ===")
                info.append(stdout.decode())
        except FileNotFoundError:
            info.append("CPU info: lscpu command not available")
        
        # Try lspci for PCI devices
        try:
            proc = await asyncio.create_subprocess_exec(
                "lspci",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            
            if proc.returncode == 0:
                pci_output = stdout.decode()
                pci_lines = pci_output.strip().split('\n')
                
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
            proc = await asyncio.create_subprocess_exec(
                "lsusb",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            
            if proc.returncode == 0:
                info.append("\n\n=== USB Devices ===")
                info.append(stdout.decode())
        except FileNotFoundError:
            info.append("\nUSB devices: lsusb command not available")
        
        # Memory hardware info from dmidecode (requires root)
        try:
            proc = await asyncio.create_subprocess_exec(
                "dmidecode", "-t", "memory",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            
            if proc.returncode == 0:
                info.append("\n\n=== Memory Hardware (dmidecode) ===")
                info.append(stdout.decode())
            elif "Permission denied" in stderr.decode():
                info.append("\n\nMemory hardware info: Requires root privileges (dmidecode)")
        except FileNotFoundError:
            info.append("\nMemory hardware info: dmidecode command not available")
        
        if len(info) == 1:  # Only the header
            info.append("No hardware information tools available.")
        
        return "\n".join(info)
    except Exception as e:
        return f"Error getting hardware information: {str(e)}"


def _format_bytes(bytes: int) -> str:
    """Format bytes into human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes < 1024.0:
            return f"{bytes:.1f}{unit}"
        bytes /= 1024.0
    return f"{bytes:.1f}PB"


async def get_biggest_directories(path: str, recursive: bool, top_n: int) -> str:
    """
    Get the biggest directories under a specified path.
    
    This function provides a secure way to analyze disk space usage by finding
    the largest directories. It includes comprehensive input validation and
    security checks to prevent command injection and path traversal attacks.
    
    Args:
        path: The directory path to analyze
        recursive: If True, search all subdirectories recursively. 
                   If False, only search immediate subdirectories.
        top_n: Number of top directories to return (1-1000)
    
    Returns:
        Formatted string with directory sizes, or error message if validation fails
    
    Security Features:
        - Path validation and resolution using pathlib
        - No shell command execution
        - Input sanitization for all parameters
        - Graceful error handling for permission issues
    """
    import os
    from pathlib import Path
    from typing import List, Tuple
    
    try:
        # Validate top_n parameter
        if not isinstance(top_n, int) or top_n <= 0:
            return "Error: top_n must be a positive integer"
        
        # Cap top_n at reasonable limit to prevent resource exhaustion
        MAX_TOP_N = 1000
        if top_n > MAX_TOP_N:
            top_n = MAX_TOP_N
        
        # Validate and resolve path using pathlib for security
        try:
            path_obj = Path(path).resolve(strict=True)
        except (OSError, RuntimeError) as e:
            return f"Error: Path does not exist or cannot be resolved: {path}"
        
        # Check if path is a directory
        if not path_obj.is_dir():
            return f"Error: Path is not a directory: {path}"
        
        # Check if we have read permissions
        if not os.access(path_obj, os.R_OK):
            return f"Error: Permission denied to read directory: {path}"
        
        # Calculate directory sizes
        dir_sizes: List[Tuple[str, int]] = []
        
        if recursive:
            # Recursive mode: scan all subdirectories
            try:
                for root, dirs, files in os.walk(path_obj, topdown=True):
                    root_path = Path(root)
                    
                    # Calculate size of each subdirectory we encounter
                    for dirname in dirs:
                        dir_path = root_path / dirname
                        try:
                            size = _calculate_directory_size(dir_path)
                            # Store relative path for cleaner output
                            relative_path = dir_path.relative_to(path_obj)
                            dir_sizes.append((str(relative_path), size))
                        except (PermissionError, OSError):
                            # Skip directories we can't access
                            continue
                            
            except (PermissionError, OSError) as e:
                return f"Error scanning directory: {str(e)}"
        else:
            # Non-recursive mode: only immediate subdirectories
            try:
                for entry in path_obj.iterdir():
                    if entry.is_dir():
                        try:
                            size = _calculate_directory_size(entry)
                            dir_sizes.append((entry.name, size))
                        except (PermissionError, OSError):
                            # Skip directories we can't access
                            continue
            except (PermissionError, OSError) as e:
                return f"Error reading directory contents: {str(e)}"
        
        # Check if we found any directories
        if not dir_sizes:
            return f"No subdirectories found in: {path}"
        
        # Sort by size (descending) and take top N
        dir_sizes.sort(key=lambda x: x[1], reverse=True)
        top_dirs = dir_sizes[:top_n]
        
        # Format output
        result = []
        result.append(f"=== Top {len(top_dirs)} Largest Directories ===")
        result.append(f"Path: {path_obj}")
        result.append(f"Mode: {'Recursive' if recursive else 'Non-recursive'}")
        result.append(f"\nTotal subdirectories found: {len(dir_sizes)}\n")
        
        # Add directory listings with formatted sizes
        for i, (dir_name, size) in enumerate(top_dirs, 1):
            result.append(f"{i}. {dir_name}")
            result.append(f"   Size: {_format_bytes(size)}")
        
        return "\n".join(result)
        
    except Exception as e:
        # Catch any unexpected errors and return safe error message
        return f"Error analyzing directories: {str(e)}"


def _calculate_directory_size(directory: Path) -> int:
    """
    Calculate total size of a directory and all its contents.
    
    Args:
        directory: Path object for the directory
    
    Returns:
        Total size in bytes
    
    Note:
        This function does not follow symbolic links to avoid counting files 
        multiple times. Permission errors are handled gracefully.
    """
    total_size = 0
    
    try:
        for entry in directory.rglob('*'):
            try:
                # Check if it's a symlink first (don't follow symlinks)
                if entry.is_symlink():
                    continue
                    
                if entry.is_file():
                    total_size += entry.stat().st_size
            except (PermissionError, OSError):
                # Skip files we can't access
                continue
    except (PermissionError, OSError):
        # If we can't read the directory at all, return 0
        pass
    
    return total_size

