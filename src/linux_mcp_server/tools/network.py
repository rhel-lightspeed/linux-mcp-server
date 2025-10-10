"""Network diagnostic tools."""

import psutil
import socket

from .decorators import log_tool_output


@log_tool_output
async def get_network_interfaces() -> str:
    """Get network interface information."""
    try:
        info = []
        info.append("=== Network Interfaces ===\n")
        
        # Get network interface addresses
        net_if_addrs = psutil.net_if_addrs()
        net_if_stats = psutil.net_if_stats()
        
        for interface, addrs in sorted(net_if_addrs.items()):
            info.append(f"\n{interface}:")
            
            # Get interface stats
            if interface in net_if_stats:
                stats = net_if_stats[interface]
                status = "UP" if stats.isup else "DOWN"
                info.append(f"  Status: {status}")
                info.append(f"  Speed: {stats.speed} Mbps")
                info.append(f"  MTU: {stats.mtu}")
            
            # Get addresses
            for addr in addrs:
                if addr.family == socket.AF_INET:
                    info.append(f"  IPv4 Address: {addr.address}")
                    if addr.netmask:
                        info.append(f"    Netmask: {addr.netmask}")
                    if addr.broadcast:
                        info.append(f"    Broadcast: {addr.broadcast}")
                elif addr.family == socket.AF_INET6:
                    info.append(f"  IPv6 Address: {addr.address}")
                    if addr.netmask:
                        info.append(f"    Netmask: {addr.netmask}")
                elif addr.family == psutil.AF_LINK:
                    info.append(f"  MAC Address: {addr.address}")
        
        # Network I/O statistics
        net_io = psutil.net_io_counters()
        info.append("\n\n=== Network I/O Statistics (total) ===")
        info.append(f"Bytes Sent: {_format_bytes(net_io.bytes_sent)}")
        info.append(f"Bytes Received: {_format_bytes(net_io.bytes_recv)}")
        info.append(f"Packets Sent: {net_io.packets_sent}")
        info.append(f"Packets Received: {net_io.packets_recv}")
        info.append(f"Errors In: {net_io.errin}")
        info.append(f"Errors Out: {net_io.errout}")
        info.append(f"Drops In: {net_io.dropin}")
        info.append(f"Drops Out: {net_io.dropout}")
        
        return "\n".join(info)
    except Exception as e:
        return f"Error getting network interface information: {str(e)}"


@log_tool_output
async def get_network_connections() -> str:
    """Get active network connections."""
    try:
        info = []
        info.append("=== Active Network Connections ===\n")
        info.append(f"{'Proto':<8} {'Local Address':<30} {'Remote Address':<30} {'Status':<15} {'PID/Program'}")
        info.append("-" * 110)
        
        # Get all network connections
        connections = psutil.net_connections(kind='inet')
        
        for conn in connections:
            proto = "TCP" if conn.type == socket.SOCK_STREAM else "UDP"
            
            local_addr = f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else "N/A"
            remote_addr = f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else "N/A"
            status = conn.status if conn.status else "N/A"
            
            # Try to get process info
            pid_info = str(conn.pid) if conn.pid else "N/A"
            if conn.pid:
                try:
                    proc = psutil.Process(conn.pid)
                    pid_info = f"{conn.pid}/{proc.name()}"
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            
            info.append(
                f"{proto:<8} {local_addr:<30} {remote_addr:<30} {status:<15} {pid_info}"
            )
        
        info.append(f"\n\nTotal connections: {len(connections)}")
        
        return "\n".join(info)
    except psutil.AccessDenied:
        return "Permission denied. This tool requires elevated privileges to view all network connections."
    except Exception as e:
        return f"Error getting network connections: {str(e)}"


@log_tool_output
async def get_listening_ports() -> str:
    """Get listening ports."""
    try:
        info = []
        info.append("=== Listening Ports ===\n")
        info.append(f"{'Proto':<8} {'Local Address':<30} {'Status':<15} {'PID/Program'}")
        info.append("-" * 80)
        
        # Get connections in LISTEN state
        connections = psutil.net_connections(kind='inet')
        listening = [c for c in connections if c.status == 'LISTEN' or c.type == socket.SOCK_DGRAM]
        
        for conn in listening:
            proto = "TCP" if conn.type == socket.SOCK_STREAM else "UDP"
            
            local_addr = f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else "N/A"
            status = conn.status if conn.status else "LISTENING"
            
            # Try to get process info
            pid_info = str(conn.pid) if conn.pid else "N/A"
            if conn.pid:
                try:
                    proc = psutil.Process(conn.pid)
                    pid_info = f"{conn.pid}/{proc.name()}"
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            
            info.append(
                f"{proto:<8} {local_addr:<30} {status:<15} {pid_info}"
            )
        
        info.append(f"\n\nTotal listening ports: {len(listening)}")
        
        return "\n".join(info)
    except psutil.AccessDenied:
        return "Permission denied. This tool requires elevated privileges to view all listening ports."
    except Exception as e:
        return f"Error getting listening ports: {str(e)}"


def _format_bytes(bytes: int) -> str:
    """Format bytes into human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes < 1024.0:
            return f"{bytes:.1f}{unit}"
        bytes /= 1024.0
    return f"{bytes:.1f}PB"

