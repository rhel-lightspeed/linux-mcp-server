import textwrap

from linux_mcp_server.parsers import parse_ps_output


def test_parse_ps_output_empty():
    """Test parsing empty output."""
    result = parse_ps_output("")

    assert result == []


def test_parse_ps_output_process():
    """Test parsing a process entry."""
    stdout = """USER       PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND
        root         1  0.0  0.1 169436 11892 ?        Ss   Dec11   0:01 /sbin/init
    """
    result = parse_ps_output(textwrap.dedent(stdout))
    proc = result[0]

    assert len(result) == 1
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


def test_parse_ps_output_multiple_processes():
    """Test parsing multiple processes."""
    stdout = """USER       PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND
        root         1  0.0  0.1 169436 11892 ?        Ss   Dec11   0:01 /sbin/init
        nobody     100  1.5  2.0  50000 20000 ?        S    Dec11   5:00 /usr/bin/app
    """
    result = parse_ps_output(textwrap.dedent(stdout))

    assert len(result) == 2


def test_parse_ps_output_skips_malformed_lines():
    """Test that malformed lines are skipped (too few parts or invalid values)."""
    stdout = """USER       PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND
        root         1  0.0  0.1 169436 11892 ?        Ss   Dec11   0:01 /sbin/init
        truncated  line with too few parts
        nobody     abc  1.5  2.0  50000 20000 ?        S    Dec11   5:00 /usr/bin/invalid_pid
        valid      200  0.5  0.5  10000 5000  ?        S    Dec11   1:00 /usr/bin/valid
    """
    result = parse_ps_output(textwrap.dedent(stdout))

    assert len(result) == 2
    assert result[0].pid == 1
    assert result[1].pid == 200
