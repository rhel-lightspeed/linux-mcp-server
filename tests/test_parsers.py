"""Tests for parsers module."""

from linux_mcp_server.parsers import parse_cpu_info
from linux_mcp_server.parsers import parse_directory_listing
from linux_mcp_server.parsers import parse_file_listing
from linux_mcp_server.parsers import parse_free_output
from linux_mcp_server.parsers import parse_ip_brief
from linux_mcp_server.parsers import parse_os_release
from linux_mcp_server.parsers import parse_proc_net_dev
from linux_mcp_server.parsers import parse_proc_status
from linux_mcp_server.parsers import parse_ps_output
from linux_mcp_server.parsers import parse_service_count
from linux_mcp_server.parsers import parse_ss_connections
from linux_mcp_server.parsers import parse_ss_listening
from linux_mcp_server.parsers import parse_system_info


class TestParseSsConnections:
    """Tests for parse_ss_connections function."""

    def test_parse_empty_output(self):
        """Test parsing empty output."""
        result = parse_ss_connections("")
        assert result == []

    def test_parse_header_only(self):
        """Test parsing output with only header."""
        stdout = "Netid  State      Recv-Q Send-Q Local Address:Port               Peer Address:Port"
        result = parse_ss_connections(stdout)
        assert result == []

    def test_parse_tcp_connection(self):
        """Test parsing a TCP connection."""
        stdout = """Netid  State      Recv-Q Send-Q Local Address:Port               Peer Address:Port
tcp    ESTAB      0      0      192.168.1.100:22                 192.168.1.1:54321"""
        result = parse_ss_connections(stdout)
        assert len(result) == 1
        conn = result[0]
        assert conn.protocol == "TCP"
        assert conn.state == "ESTAB"
        assert conn.local_address == "192.168.1.100"
        assert conn.local_port == "22"

    def test_parse_udp_connection(self):
        """Test parsing a UDP connection."""
        stdout = """Netid  State      Recv-Q Send-Q Local Address:Port               Peer Address:Port
udp    UNCONN     0      0      0.0.0.0:68                       0.0.0.0:*"""
        result = parse_ss_connections(stdout)
        assert len(result) == 1
        conn = result[0]
        assert conn.protocol == "UDP"


class TestParseSsListening:
    """Tests for parse_ss_listening function."""

    def test_parse_empty_output(self):
        """Test parsing empty output."""
        result = parse_ss_listening("")
        assert result == []

    def test_parse_listening_port(self):
        """Test parsing a listening port."""
        stdout = """Netid  State      Recv-Q Send-Q Local Address:Port               Peer Address:Port
tcp    LISTEN     0      128    0.0.0.0:22                       0.0.0.0:*"""
        result = parse_ss_listening(stdout)
        assert len(result) == 1
        port = result[0]
        assert port.protocol == "TCP"
        assert port.local_address == "0.0.0.0"
        assert port.local_port == "22"


class TestParsePsOutput:
    """Tests for parse_ps_output function."""

    def test_parse_empty_output(self):
        """Test parsing empty output."""
        result = parse_ps_output("")
        assert result == []

    def test_parse_process(self):
        """Test parsing a process entry."""
        stdout = """USER       PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND
root         1  0.0  0.1 169436 11892 ?        Ss   Dec11   0:01 /sbin/init"""
        result = parse_ps_output(stdout)
        assert len(result) == 1
        proc = result[0]
        assert proc.user == "root"
        assert proc.pid == 1
        assert proc.cpu_percent == 0.0
        assert proc.mem_percent == 0.1
        assert proc.vsz == 169436
        assert proc.rss == 11892
        assert proc.tty == "?"
        assert proc.stat == "Ss"
        assert proc.start == "Dec11"
        assert proc.time == "0:01"
        assert proc.command == "/sbin/init"

    def test_parse_multiple_processes(self):
        """Test parsing multiple processes."""
        stdout = """USER       PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND
root         1  0.0  0.1 169436 11892 ?        Ss   Dec11   0:01 /sbin/init
nobody     100  1.5  2.0  50000 20000 ?        S    Dec11   5:00 /usr/bin/app"""
        result = parse_ps_output(stdout)
        assert len(result) == 2

    def test_parse_skips_malformed_lines(self):
        """Test that malformed lines are skipped (too few parts or invalid values)."""
        stdout = """USER       PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND
root         1  0.0  0.1 169436 11892 ?        Ss   Dec11   0:01 /sbin/init
truncated  line with too few parts
nobody     abc  1.5  2.0  50000 20000 ?        S    Dec11   5:00 /usr/bin/invalid_pid
valid      200  0.5  0.5  10000 5000  ?        S    Dec11   1:00 /usr/bin/valid"""
        result = parse_ps_output(stdout)
        assert len(result) == 2
        assert result[0].pid == 1
        assert result[1].pid == 200


class TestParseOsRelease:
    """Tests for parse_os_release function."""

    def test_parse_empty_output(self):
        """Test parsing empty output."""
        result = parse_os_release("")
        assert result == {}

    def test_parse_os_release(self):
        """Test parsing /etc/os-release content."""
        stdout = """NAME="Ubuntu"
VERSION="22.04.3 LTS (Jammy Jellyfish)"
ID=ubuntu
ID_LIKE=debian
PRETTY_NAME="Ubuntu 22.04.3 LTS"
VERSION_ID="22.04"
"""
        result = parse_os_release(stdout)
        assert result["NAME"] == "Ubuntu"
        assert result["VERSION_ID"] == "22.04"
        assert result["PRETTY_NAME"] == "Ubuntu 22.04.3 LTS"
        assert result["ID"] == "ubuntu"


class TestParseFreeOutput:
    """Tests for parse_free_output function."""

    def test_parse_empty_output(self):
        """Test parsing empty output."""
        result = parse_free_output("")
        assert result.ram.total == 0
        assert result.swap is None

    def test_parse_free_output(self):
        """Test parsing free -b -w output (wide format with separate buffers/cache)."""
        stdout = """              total        used        free      shared     buffers       cache   available
Mem:    16777216000  8388608000  4294967296   134217728  1234567890  2859072814  8000000000
Swap:    2147483648   104857600  2042626048"""
        result = parse_free_output(stdout)
        assert result.ram.total == 16777216000
        assert result.ram.used == 8388608000
        assert result.ram.free == 4294967296
        assert result.ram.shared == 134217728
        assert result.ram.buffers == 1234567890
        assert result.ram.cached == 2859072814
        assert result.ram.available == 8000000000
        assert result.swap is not None
        assert result.swap.total == 2147483648
        assert result.swap.used == 104857600
        assert result.swap.free == 2042626048


class TestParseProcNetDev:
    """Tests for parse_proc_net_dev function."""

    def test_parse_empty_output(self):
        """Test parsing empty output."""
        result = parse_proc_net_dev("")
        assert result == {}

    def test_parse_proc_net_dev(self):
        """Test parsing /proc/net/dev content."""
        stdout = """Inter-|   Receive                                                |  Transmit
 face |bytes    packets errs drop fifo frame compressed multicast|bytes    packets errs drop fifo colls carrier compressed
    lo: 1234567   12345    0    0    0     0          0         0  1234567   12345    0    0    0     0       0          0
  eth0: 9876543   98765   10    5    0     0          0       100  5432100   54321   20   10    0     0       0          0"""
        result = parse_proc_net_dev(stdout)
        assert "lo" in result
        assert "eth0" in result
        lo = result["lo"]
        assert lo.rx_bytes == 1234567
        assert lo.rx_packets == 12345
        eth0 = result["eth0"]
        assert eth0.rx_bytes == 9876543
        assert eth0.rx_errors == 10
        assert eth0.tx_bytes == 5432100


class TestParseIpBrief:
    """Tests for parse_ip_brief function."""

    def test_parse_empty_output(self):
        """Test parsing empty output."""
        result = parse_ip_brief("")
        assert result == {}

    def test_parse_ip_brief(self):
        """Test parsing ip -brief address output."""
        stdout = """lo               UNKNOWN        127.0.0.1/8 ::1/128
eth0             UP             192.168.1.100/24 fe80::1/64"""
        result = parse_ip_brief(stdout)
        assert "lo" in result
        assert "eth0" in result
        lo = result["lo"]
        assert lo.status == "UNKNOWN"
        assert "127.0.0.1/8" in lo.addresses
        eth0 = result["eth0"]
        assert eth0.status == "UP"
        assert "192.168.1.100/24" in eth0.addresses


class TestParseSystemInfo:
    """Tests for parse_system_info function."""

    def test_parse_empty_results(self):
        """Test parsing empty results."""
        result = parse_system_info({})
        assert result.hostname == ""
        assert result.os_name == ""

    def test_parse_system_info(self):
        """Test parsing system info results."""
        results = {
            "hostname": "myserver\n",
            "os_release": 'PRETTY_NAME="Ubuntu 22.04.3 LTS"\nVERSION_ID="22.04"\n',
            "kernel": "5.15.0-91-generic\n",
            "arch": "x86_64\n",
            "uptime": "up 5 days, 3 hours\n",
            "boot_time": "2024-01-01 10:00:00\n",
        }
        result = parse_system_info(results)
        assert result.hostname == "myserver"
        assert result.os_name == "Ubuntu 22.04.3 LTS"
        assert result.os_version == "22.04"
        assert result.kernel == "5.15.0-91-generic"
        assert result.arch == "x86_64"


class TestParseCpuInfo:
    """Tests for parse_cpu_info function."""

    def test_parse_empty_results(self):
        """Test parsing empty results."""
        result = parse_cpu_info({})
        assert result.model == ""
        assert result.logical_cores == 0

    def test_parse_cpu_info(self):
        """Test parsing CPU info results."""
        results = {
            "model": "model name\t: Intel(R) Core(TM) i7-10700 CPU @ 2.90GHz\n",
            "logical_cores": "8\n",
            "physical_cores": "core id\t\t: 0\ncore id\t\t: 1\ncore id\t\t: 2\ncore id\t\t: 3\n",
            "frequency": "cpu MHz\t\t: 2900.000\n",
            "load_avg": "0.50 0.75 1.00 1/234 5678\n",
        }
        result = parse_cpu_info(results)
        assert result.model == "Intel(R) Core(TM) i7-10700 CPU @ 2.90GHz"
        assert result.logical_cores == 8
        assert result.physical_cores == 4
        assert result.frequency_mhz == 2900.0
        assert result.load_avg_1m == 0.50
        assert result.load_avg_5m == 0.75
        assert result.load_avg_15m == 1.00


class TestParseProcStatus:
    """Tests for parse_proc_status function."""

    def test_parse_empty_output(self):
        """Test parsing empty output."""
        result = parse_proc_status("")
        assert result == {}

    def test_parse_proc_status(self):
        """Test parsing /proc/{pid}/status content."""
        stdout = """Name:	bash
State:	S (sleeping)
Tgid:	1234
Pid:	1234
PPid:	1000
Threads:	1
VmPeak:	    12000 kB
VmSize:	    10000 kB
VmRSS:	     5000 kB
SigPnd:	0000000000000000"""
        result = parse_proc_status(stdout)
        assert result["Name"] == "bash"
        assert result["State"] == "S (sleeping)"
        assert result["Pid"] == "1234"
        assert result["PPid"] == "1000"
        assert result["Threads"] == "1"
        assert result["VmRSS"] == "5000 kB"
        # SigPnd should not be included (not in relevant_fields)
        assert "SigPnd" not in result


class TestParseServiceCount:
    """Tests for parse_service_count function."""

    def test_parse_empty_output(self):
        """Test parsing empty output."""
        result = parse_service_count("")
        assert result == 0

    def test_parse_service_count(self):
        """Test counting services."""
        stdout = """UNIT                     LOAD   ACTIVE SUB     DESCRIPTION
ssh.service              loaded active running OpenBSD Secure Shell server
cron.service             loaded active running Regular background program processing
nginx.service            loaded active running A high performance web server
"""
        result = parse_service_count(stdout)
        assert result == 3

    def test_parse_service_count_mixed(self):
        """Test counting services with mixed content."""
        stdout = """Some header text
ssh.service is running
another.service is active
not a service line"""
        result = parse_service_count(stdout)
        assert result == 2


class TestParseDirectoryListing:
    """Tests for parse_directory_listing function."""

    def test_parse_empty_output(self):
        """Test parsing empty output."""
        result = parse_directory_listing("", "name")
        assert result == []

    def test_parse_by_name(self):
        """Test parsing directory names."""
        stdout = "alpha\nbeta\ngamma"
        result = parse_directory_listing(stdout, "name")
        assert len(result) == 3
        names = [e.name for e in result]
        assert names == ["alpha", "beta", "gamma"]

    def test_parse_by_size(self):
        """Test parsing directories with sizes from du output."""
        stdout = "4096\t/path/alpha\n8192\t/path/beta\n2048\t/path/gamma"
        result = parse_directory_listing(stdout, "size")
        assert len(result) == 3
        assert result[0].size == 4096
        assert result[0].name == "alpha"
        assert result[1].size == 8192
        assert result[1].name == "beta"

    def test_parse_by_modified(self):
        """Test parsing directories with modification times."""
        stdout = "1700000000.0\talpha\n1700100000.0\tbeta\n1700200000.0\tgamma"
        result = parse_directory_listing(stdout, "modified")
        assert len(result) == 3
        assert result[0].modified == 1700000000.0
        assert result[0].name == "alpha"


class TestParseFileListing:
    """Tests for parse_file_listing function."""

    def test_parse_empty_output(self):
        """Test parsing empty output."""
        result = parse_file_listing("", "name")
        assert result == []

    def test_parse_by_name(self):
        """Test parsing file names."""
        stdout = "file1.txt\nfile2.txt\nfile3.txt"
        result = parse_file_listing(stdout, "name")
        assert len(result) == 3
        names = [e.name for e in result]
        assert names == ["file1.txt", "file2.txt", "file3.txt"]

    def test_parse_by_size(self):
        """Test parsing files with sizes."""
        stdout = "1024\tfile1.txt\n2048\tfile2.txt\n512\tfile3.txt"
        result = parse_file_listing(stdout, "size")
        assert len(result) == 3
        assert result[0].size == 1024
        assert result[0].name == "file1.txt"

    def test_parse_by_modified(self):
        """Test parsing files with modification times."""
        stdout = "1700000000.0\tfile1.txt\n1700100000.0\tfile2.txt"
        result = parse_file_listing(stdout, "modified")
        assert len(result) == 2
        assert result[0].modified == 1700000000.0
        assert result[0].name == "file1.txt"
