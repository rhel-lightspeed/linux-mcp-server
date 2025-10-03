"""Storage and hardware tools."""

import asyncio
import subprocess
import psutil


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

