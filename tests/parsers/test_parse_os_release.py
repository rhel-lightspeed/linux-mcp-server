import textwrap

from linux_mcp_server.parsers import parse_os_release


def test_parse_os_release_empty():
    """Test parsing empty output."""
    result = parse_os_release("")

    assert result == {}


def test_parse_os_release():
    """Test parsing /etc/os-release content."""
    stdout = """NAME="Ubuntu"
        VERSION="22.04.3 LTS (Jammy Jellyfish)"
        ID=ubuntu
        ID_LIKE=debian
        PRETTY_NAME="Ubuntu 22.04.3 LTS"
        VERSION_ID="22.04"
    """
    result = parse_os_release(textwrap.dedent(stdout))

    assert result["NAME"] == "Ubuntu"
    assert result["VERSION_ID"] == "22.04"
    assert result["PRETTY_NAME"] == "Ubuntu 22.04.3 LTS"
    assert result["ID"] == "ubuntu"
