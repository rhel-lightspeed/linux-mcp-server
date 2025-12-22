from linux_mcp_server.parsers import parse_system_info


def test_parse_system_info_empty():
    """Test parsing empty results."""
    result = parse_system_info({})

    assert result.hostname == ""
    assert result.os_name == ""


def test_parse_system_info():
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

    assert result.arch == "x86_64"
    assert result.boot_time == "2024-01-01 10:00:00"
    assert result.hostname == "myserver"
    assert result.kernel == "5.15.0-91-generic"
    assert result.os_name == "Ubuntu 22.04.3 LTS"
    assert result.os_version == "22.04"
    assert result.uptime == "up 5 days, 3 hours"
