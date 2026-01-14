import textwrap

from linux_mcp_server.parsers import parse_df_output


def test_parse_df_output_empty():
    """Test parsing empty output."""
    result = parse_df_output("")

    assert result == []


def test_parse_df_output_header_only():
    """Test parsing output with only header."""
    stdout = """Filesystem     1M-blocks      Used Available Use% Mounted on"""
    result = parse_df_output(stdout)

    assert result == []


def test_parse_df_output():
    """Test parsing df output into DiskUsage objects."""
    stdout = """
    Filesystem     1M-blocks      Used Available Use% Mounted on
    /dev/sda1         102400     51200     46080  53% /
    /dev/sdb1         204800    102400     92160  53% /home
    tmpfs              16384      1024     15360   7% /tmp
    /dev/sdc1        1048576    209715    839861  21% /data
    """
    result = parse_df_output(textwrap.dedent(stdout))

    assert len(result) == 4

    # Check /dev/sda1 (root partition)
    assert result[0].filesystem == "/dev/sda1"
    # 102400 MB = 100 GB
    assert round(result[0].size_gb, 6) == 100.0
    assert round(result[0].used_gb, 6) == 50.0
    assert round(result[0].available_gb, 6) == 45.0
    assert result[0].use_percent == 53.0
    assert result[0].mount_point == "/"

    # Check /dev/sdb1 (/home partition)
    assert result[1].filesystem == "/dev/sdb1"
    # 204800 MB = 200 GB
    assert round(result[1].size_gb, 6) == 200.0
    assert round(result[1].used_gb, 6) == 100.0
    assert round(result[1].available_gb, 6) == 90.0
    assert result[1].use_percent == 53.0
    assert result[1].mount_point == "/home"

    # Check tmpfs
    assert result[2].filesystem == "tmpfs"
    # 16384 MB = 16 GB
    assert round(result[2].size_gb, 6) == 16.0
    assert round(result[2].used_gb, 6) == 1.0
    assert round(result[2].available_gb, 6) == 15.0
    assert result[2].use_percent == 7.0
    assert result[2].mount_point == "/tmp"

    # Check /dev/sdc1 (/data partition)
    assert result[3].filesystem == "/dev/sdc1"
    # 1048576 MB = 1024 GB = 1 TB
    assert round(result[3].size_gb, 6) == 1024.0
    assert round(result[3].used_gb, 6) == 204.799805
    assert round(result[3].available_gb, 6) == 820.176758
    assert result[3].use_percent == 21.0
    assert result[3].mount_point == "/data"


def test_parse_df_output_with_invalid_lines():
    """Test parsing df output with some invalid lines."""
    stdout = """
    Filesystem     1M-blocks      Used Available Use% Mounted on
    /dev/sda1         102400     51200     46080  53% /
    invalid line
    incomplete
    /dev/sdb1         204800    102400     92160  53% /home
    """
    result = parse_df_output(textwrap.dedent(stdout))

    assert len(result) == 2
    assert result[0].filesystem == "/dev/sda1"
    assert result[0].mount_point == "/"
    assert result[1].filesystem == "/dev/sdb1"
    assert result[1].mount_point == "/home"


def test_parse_df_output_100_percent():
    """Test parsing df output with 100% usage."""
    stdout = """
    Filesystem     1M-blocks      Used Available Use% Mounted on
    /dev/sda1         102400    102400         0 100% /
    """
    result = parse_df_output(textwrap.dedent(stdout))

    assert len(result) == 1
    assert result[0].use_percent == 100.0
    assert result[0].available_gb == 0.0


def test_parse_df_output_with_invalid_values():
    """Test parsing df output with invalid values."""
    stdout = """
    Filesystem     1M-blocks      Used Available Use% Mounted on
    /dev/sda1         None       51200     46080  53% /
    /dev/sdb1         204800    102400     92160  53% /home
    """
    result = parse_df_output(textwrap.dedent(stdout))

    assert len(result) == 1
    assert result[0].filesystem == "/dev/sdb1"
    assert result[0].mount_point == "/home"
