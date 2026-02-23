"""Tests for formatters module."""

from linux_mcp_server.formatters import format_disk_usage
from linux_mcp_server.formatters import format_hardware_info
from linux_mcp_server.formatters import format_listening_ports
from linux_mcp_server.formatters import format_network_connections
from linux_mcp_server.formatters import format_network_interfaces
from linux_mcp_server.formatters import format_process_detail
from linux_mcp_server.formatters import format_process_list
from linux_mcp_server.formatters import format_service_logs
from linux_mcp_server.formatters import format_service_status
from linux_mcp_server.formatters import format_services_list
from linux_mcp_server.models import ListeningPort
from linux_mcp_server.models import NetworkConnection
from linux_mcp_server.models import NetworkInterface
from linux_mcp_server.models import ProcessInfo


class TestFormatNetworkConnections:
    """Tests for format_network_connections function."""

    def test_format_empty_list(self):
        """Test formatting an empty list."""
        result = format_network_connections([])
        assert "=== Active Network Connections ===" in result
        assert "Total connections: 0" in result

    def test_format_single_connection(self):
        """Test formatting a single connection."""
        connections = [
            NetworkConnection(
                protocol="TCP",
                state="ESTABLISHED",
                local_address="192.168.1.100",
                local_port="22",
                remote_address="192.168.1.1",
                remote_port="54321",
                process="sshd",
            )
        ]
        result = format_network_connections(connections)
        assert "TCP" in result
        assert "192.168.1.100:22" in result
        assert "192.168.1.1:54321" in result
        assert "ESTABLISHED" in result
        assert "Total connections: 1" in result

    def test_format_custom_header(self):
        """Test formatting with custom header."""
        result = format_network_connections([], header="=== Custom Header ===\n")
        assert "=== Custom Header ===" in result


class TestFormatListeningPorts:
    """Tests for format_listening_ports function."""

    def test_format_empty_list(self):
        """Test formatting an empty list."""
        result = format_listening_ports([])
        assert "=== Listening Ports ===" in result
        assert "Total listening ports: 0" in result

    def test_format_single_port(self):
        """Test formatting a single listening port."""
        ports = [
            ListeningPort(
                protocol="TCP",
                local_address="0.0.0.0",
                local_port="22",
                process="sshd",
            )
        ]
        result = format_listening_ports(ports)
        assert "TCP" in result
        assert "0.0.0.0:22" in result
        assert "LISTEN" in result
        assert "Total listening ports: 1" in result


class TestFormatProcessList:
    """Tests for format_process_list function."""

    def test_format_empty_list(self):
        """Test formatting an empty list."""
        result = format_process_list([])
        assert "=== Running Processes ===" in result
        assert "Total processes: 0" in result

    def test_format_single_process(self):
        """Test formatting a single process."""
        processes = [
            ProcessInfo(
                pid=1,
                user="root",
                cpu_percent=0.0,
                mem_percent=0.1,
                vsz=169436,
                rss=11892,
                tty="?",
                stat="Ss",
                start="Dec11",
                time="0:01",
                command="/sbin/init",
            )
        ]
        result = format_process_list(processes)
        assert "root" in result
        assert "1" in result
        assert "Total processes: 1" in result

    def test_format_truncation(self):
        """Test that process list is truncated."""
        processes = [
            ProcessInfo(
                pid=i,
                user="user",
                cpu_percent=0.0,
                mem_percent=0.1,
                vsz=1000,
                rss=500,
                tty="?",
                stat="S",
                start="Dec11",
                time="0:00",
                command=f"process{i}",
            )
            for i in range(150)
        ]
        result = format_process_list(processes, max_display=100)
        assert "Total processes: 150" in result
        assert "Showing: First 100 processes" in result


class TestFormatNetworkInterfaces:
    """Tests for format_network_interfaces function."""

    def test_format_empty_interfaces(self):
        """Test formatting empty interfaces."""
        result = format_network_interfaces({})
        assert "=== Network Interfaces ===" in result

    def test_format_with_interfaces(self):
        """Test formatting with interfaces."""
        interfaces = {
            "eth0": NetworkInterface(
                name="eth0",
                status="UP",
                addresses=["192.168.1.100/24"],
            ),
            "lo": NetworkInterface(
                name="lo",
                status="UNKNOWN",
                addresses=["127.0.0.1/8"],
            ),
        }
        result = format_network_interfaces(interfaces)
        assert "eth0:" in result
        assert "Status: UP" in result
        assert "192.168.1.100/24" in result

    def test_format_with_stats(self):
        """Test formatting with statistics."""
        interfaces = {
            "eth0": NetworkInterface(name="eth0", status="UP"),
        }
        stats = {
            "eth0": NetworkInterface(
                name="eth0",
                rx_bytes=1000000,
                tx_bytes=500000,
                rx_packets=10000,
                tx_packets=5000,
            ),
        }
        result = format_network_interfaces(interfaces, stats)
        assert "RX:" in result
        assert "TX:" in result


class TestFormatProcessDetail:
    """Tests for format_process_detail function."""

    def test_format_basic(self):
        """Test basic formatting."""
        ps_output = (
            "PID USER STAT %CPU %MEM VSZ RSS TIME COMMAND ARGS\n1 root Ss 0.0 0.1 169436 11892 0:01 init /sbin/init"
        )
        result = format_process_detail(ps_output)
        assert ps_output.strip() in result

    def test_format_with_pid_header(self):
        """Test formatting with PID header."""
        ps_output = "PID USER STAT\n1 root Ss"
        result = format_process_detail(ps_output, pid=1)
        assert "=== Process Information for PID 1 ===" in result

    def test_format_with_proc_status(self):
        """Test formatting with /proc status."""
        ps_output = "PID USER\n1 root"
        proc_status = {"Name": "init", "State": "S (sleeping)", "Threads": "1"}
        result = format_process_detail(ps_output, proc_status, pid=1)
        assert "=== Detailed Status (/proc) ===" in result
        assert "Name: init" in result
        assert "State: S (sleeping)" in result


class TestFormatServicesList:
    """Tests for format_services_list function."""

    def test_format_basic(self):
        """Test basic formatting."""
        stdout = "UNIT LOAD ACTIVE SUB DESCRIPTION\nssh.service loaded active running SSH"
        result = format_services_list(stdout)
        assert "=== System Services ===" in result
        assert "ssh.service" in result

    def test_format_with_count(self):
        """Test formatting with running count."""
        stdout = "UNIT LOAD\nssh.service loaded"
        result = format_services_list(stdout, running_count=5)
        assert "Summary: 5 services currently running" in result


class TestFormatServiceStatus:
    """Tests for format_service_status function."""

    def test_format_service_status(self):
        """Test formatting service status."""
        stdout = "● ssh.service - OpenBSD Secure Shell server\n   Active: active (running)"
        result = format_service_status(stdout, "ssh.service")
        assert "=== Status of ssh.service ===" in result
        assert "Active: active (running)" in result


class TestFormatServiceLogs:
    """Tests for format_service_logs function."""

    def test_format_service_logs(self):
        """Test formatting service logs."""
        stdout = "Dec 12 10:00:00 host sshd[1234]: Accepted publickey"
        result = format_service_logs(stdout, "ssh.service", 50)
        assert "=== Last 50 log entries for ssh.service ===" in result
        assert "Accepted publickey" in result


class TestFormatDiskUsage:
    """Tests for format_disk_usage function."""

    def test_format_basic(self):
        """Test basic formatting."""
        stdout = "Filesystem Size Used Avail Use% Mounted\n/dev/sda1 100G 50G 50G 50% /"
        result = format_disk_usage(stdout)
        assert "=== Filesystem Usage ===" in result
        assert "/dev/sda1" in result

    def test_format_with_disk_io(self):
        """Test formatting with disk I/O."""
        stdout = "Filesystem Size\n/dev/sda1 100G"
        disk_io = "Read: 1GB Write: 500MB"
        result = format_disk_usage(stdout, disk_io)
        assert "=== Disk I/O Statistics (since boot) ===" in result


class TestFormatHardwareInfo:
    """Tests for format_hardware_info function."""

    def test_format_empty(self):
        """Test formatting empty results."""
        result = format_hardware_info({})
        assert "=== Hardware Information ===" in result
        assert "No hardware information tools available." in result

    def test_format_with_data(self):
        """Test formatting with data."""
        results = {
            "lscpu": "Architecture: x86_64\nCPU(s): 8",
            "lspci": "00:00.0 Host bridge: Intel Corporation\n00:02.0 VGA compatible controller: Intel",
            "lsusb": "Bus 001 Device 001: ID 1d6b:0002 Linux Foundation 2.0 root hub",
        }
        result = format_hardware_info(results)
        assert "=== CPU Architecture (lscpu) ===" in result
        assert "=== PCI Devices ===" in result
        assert "=== USB Devices ===" in result

    def test_format_truncates_pci(self):
        """Test that PCI devices are truncated at 50."""
        pci_lines = "\n".join([f"00:{i:02d}.0 Device {i}" for i in range(60)])
        results = {"lspci": pci_lines}
        result = format_hardware_info(results)
        assert "... and 10 more PCI devices" in result
