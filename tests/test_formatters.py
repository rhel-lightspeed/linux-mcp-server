"""Tests for formatters module."""

from linux_mcp_server.formatters import format_audit_logs
from linux_mcp_server.formatters import format_block_devices
from linux_mcp_server.formatters import format_cpu_info
from linux_mcp_server.formatters import format_directory_listing
from linux_mcp_server.formatters import format_disk_usage
from linux_mcp_server.formatters import format_file_listing
from linux_mcp_server.formatters import format_hardware_info
from linux_mcp_server.formatters import format_journal_logs
from linux_mcp_server.formatters import format_listening_ports
from linux_mcp_server.formatters import format_log_file
from linux_mcp_server.formatters import format_memory_info
from linux_mcp_server.formatters import format_network_connections
from linux_mcp_server.formatters import format_network_interfaces
from linux_mcp_server.formatters import format_process_detail
from linux_mcp_server.formatters import format_process_list
from linux_mcp_server.formatters import format_service_logs
from linux_mcp_server.formatters import format_service_status
from linux_mcp_server.formatters import format_services_list
from linux_mcp_server.formatters import format_system_info
from linux_mcp_server.utils.types import CpuInfo
from linux_mcp_server.utils.types import ListeningPort
from linux_mcp_server.utils.types import MemoryInfo
from linux_mcp_server.utils.types import NetworkConnection
from linux_mcp_server.utils.types import NetworkInterface
from linux_mcp_server.utils.types import NodeEntry
from linux_mcp_server.utils.types import ProcessInfo
from linux_mcp_server.utils.types import SwapInfo
from linux_mcp_server.utils.types import SystemInfo
from linux_mcp_server.utils.types import SystemMemory


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
                pid="1",
                user="root",
                cpu_percent="0.0",
                mem_percent="0.1",
                vsz="169436",
                rss="11892",
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
                pid=str(i),
                user="user",
                cpu_percent="0.0",
                mem_percent="0.1",
                vsz="1000",
                rss="500",
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


class TestFormatMemoryInfo:
    """Tests for format_memory_info function."""

    def test_format_ram_only(self):
        """Test formatting RAM only."""
        memory = SystemMemory(
            ram=MemoryInfo(
                total=16000000000,
                used=8000000000,
                free=4000000000,
                available=8000000000,
            )
        )
        result = format_memory_info(memory)
        assert "=== RAM Information ===" in result
        assert "Total:" in result
        assert "Available:" in result
        assert "Used:" in result
        assert "Free:" in result

    def test_format_with_swap(self):
        """Test formatting with swap."""
        memory = SystemMemory(
            ram=MemoryInfo(
                total=16000000000,
                used=8000000000,
                free=4000000000,
                available=8000000000,
            ),
            swap=SwapInfo(
                total=2000000000,
                used=100000000,
                free=1900000000,
            ),
        )
        result = format_memory_info(memory)
        assert "=== RAM Information ===" in result
        assert "=== Swap Information ===" in result

    def test_format_with_buffers_and_cache(self):
        """Test formatting with buffers and cache (wide output format)."""
        memory = SystemMemory(
            ram=MemoryInfo(
                total=16000000000,
                used=8000000000,
                free=4000000000,
                shared=134217728,
                buffers=1234567890,
                cached=2859072814,
                available=8000000000,
            )
        )
        result = format_memory_info(memory)
        assert "=== RAM Information ===" in result
        assert "Buffers:" in result
        assert "Cache:" in result


class TestFormatSystemInfo:
    """Tests for format_system_info function."""

    def test_format_empty_info(self):
        """Test formatting empty system info."""
        info = SystemInfo()
        result = format_system_info(info)
        assert result == ""

    def test_format_full_info(self):
        """Test formatting full system info."""
        info = SystemInfo(
            hostname="myserver",
            os_name="Ubuntu 22.04.3 LTS",
            os_version="22.04",
            kernel="5.15.0-91-generic",
            arch="x86_64",
            uptime="up 5 days",
            boot_time="2024-01-01 10:00:00",
        )
        result = format_system_info(info)
        assert "Hostname: myserver" in result
        assert "Operating System: Ubuntu 22.04.3 LTS" in result
        assert "OS Version: 22.04" in result
        assert "Kernel Version: 5.15.0-91-generic" in result
        assert "Architecture: x86_64" in result


class TestFormatCpuInfo:
    """Tests for format_cpu_info function."""

    def test_format_empty_info(self):
        """Test formatting empty CPU info."""
        info = CpuInfo()
        result = format_cpu_info(info)
        assert result == ""

    def test_format_full_info(self):
        """Test formatting full CPU info."""
        info = CpuInfo(
            model="Intel(R) Core(TM) i7-10700 CPU @ 2.90GHz",
            logical_cores=16,
            physical_cores=8,
            frequency_mhz=2900.0,
            load_avg_1m=0.50,
            load_avg_5m=0.75,
            load_avg_15m=1.00,
        )
        result = format_cpu_info(info)
        assert "CPU Model: Intel(R) Core(TM) i7-10700 CPU @ 2.90GHz" in result
        assert "CPU Physical Cores: 8" in result
        assert "CPU Logical Cores (threads): 16" in result
        assert "Load Average" in result


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


class TestFormatJournalLogs:
    """Tests for format_journal_logs function."""

    def test_format_no_filters(self):
        """Test formatting without filters."""
        stdout = "Dec 12 10:00:00 host kernel: Log message"
        result = format_journal_logs(stdout, 100)
        assert "=== Journal Logs (last 100 entries, no filters) ===" in result

    def test_format_with_filters(self):
        """Test formatting with filters."""
        stdout = "Dec 12 10:00:00 host sshd[1234]: Message"
        result = format_journal_logs(stdout, 50, unit="ssh.service", priority="err", since="today")
        assert "unit=ssh.service" in result
        assert "priority=err" in result
        assert "since=today" in result


class TestFormatAuditLogs:
    """Tests for format_audit_logs function."""

    def test_format_audit_logs(self):
        """Test formatting audit logs."""
        stdout = "type=SYSCALL msg=audit(1702389600.123:1234)"
        result = format_audit_logs(stdout, 100)
        assert "=== Audit Logs (last 100 entries) ===" in result
        assert "type=SYSCALL" in result


class TestFormatLogFile:
    """Tests for format_log_file function."""

    def test_format_log_file(self):
        """Test formatting log file."""
        stdout = "2024-01-01 10:00:00 INFO Application started"
        result = format_log_file(stdout, "/var/log/app.log", 100)
        assert "=== Log File: /var/log/app.log (last 100 lines) ===" in result
        assert "Application started" in result


class TestFormatBlockDevices:
    """Tests for format_block_devices function."""

    def test_format_basic(self):
        """Test basic formatting."""
        stdout = "NAME SIZE TYPE MOUNTPOINT FSTYPE MODEL\nsda 100G disk"
        result = format_block_devices(stdout)
        assert "=== Block Devices ===" in result
        assert "sda" in result

    def test_format_with_disk_io(self):
        """Test formatting with disk I/O."""
        stdout = "NAME SIZE\nsda 100G"
        disk_io = "sda: Read: 1GB Write: 500MB"
        result = format_block_devices(stdout, disk_io)
        assert "=== Disk I/O Statistics (per disk) ===" in result


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


class TestFormatDirectoryListing:
    """Tests for format_directory_listing function."""

    def test_format_empty_list(self):
        """Test formatting empty list."""
        result = format_directory_listing([], "/path", "name")
        assert "=== Directories in /path ===" in result
        assert "Total directories: 0" in result

    def test_format_by_name(self):
        """Test formatting directories by name."""
        entries = [
            NodeEntry(name="gamma"),
            NodeEntry(name="alpha"),
            NodeEntry(name="beta"),
        ]
        result = format_directory_listing(entries, "/path", "name")
        assert "alpha" in result
        assert "beta" in result
        assert "gamma" in result
        # Should be sorted
        alpha_pos = result.find("alpha")
        beta_pos = result.find("beta")
        gamma_pos = result.find("gamma")
        assert alpha_pos < beta_pos < gamma_pos

    def test_format_by_size(self):
        """Test formatting directories by size."""
        entries = [
            NodeEntry(name="small", size=100),
            NodeEntry(name="large", size=1000),
            NodeEntry(name="medium", size=500),
        ]
        result = format_directory_listing(entries, "/path", "size")
        assert "small" in result
        assert "large" in result
        assert "medium" in result

    def test_format_descending(self):
        """Test formatting in descending order."""
        entries = [
            NodeEntry(name="alpha"),
            NodeEntry(name="beta"),
            NodeEntry(name="gamma"),
        ]
        result = format_directory_listing(entries, "/path", "name", reverse=True)
        gamma_pos = result.find("gamma")
        beta_pos = result.find("beta")
        alpha_pos = result.find("alpha")
        assert gamma_pos < beta_pos < alpha_pos


class TestFormatFileListing:
    """Tests for format_file_listing function."""

    def test_format_empty_list(self):
        """Test formatting empty list."""
        result = format_file_listing([], "/path", "name")
        assert "=== Files in /path ===" in result
        assert "Total files: 0" in result

    def test_format_by_name(self):
        """Test formatting files by name."""
        entries = [
            NodeEntry(name="file3.txt"),
            NodeEntry(name="file1.txt"),
            NodeEntry(name="file2.txt"),
        ]
        result = format_file_listing(entries, "/path", "name")
        assert "file1.txt" in result
        assert "file2.txt" in result
        assert "file3.txt" in result
        # Should be sorted
        file1_pos = result.find("file1.txt")
        file2_pos = result.find("file2.txt")
        file3_pos = result.find("file3.txt")
        assert file1_pos < file2_pos < file3_pos

    def test_format_by_size(self):
        """Test formatting files by size."""
        entries = [
            NodeEntry(name="small.txt", size=100),
            NodeEntry(name="large.txt", size=1000),
        ]
        result = format_file_listing(entries, "/path", "size")
        assert "small.txt" in result
        assert "large.txt" in result

    def test_format_by_modified(self):
        """Test formatting files by modification time."""
        entries = [
            NodeEntry(name="old.txt", modified=1700000000.0),
            NodeEntry(name="new.txt", modified=1700100000.0),
        ]
        result = format_file_listing(entries, "/path", "modified")
        assert "old.txt" in result
        assert "new.txt" in result
