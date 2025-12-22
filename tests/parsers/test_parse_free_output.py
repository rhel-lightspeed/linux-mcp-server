import textwrap

from linux_mcp_server.parsers import parse_free_output


def test_parse_free_output_empty():
    """Test parsing empty output."""
    result = parse_free_output("")

    assert result.ram.total == 0
    assert result.swap is None


def test_parse_free_output():
    """Test parsing free -b -w output (wide format with separate buffers/cache)."""
    stdout = """              total        used        free      shared     buffers       cache   available
            Mem:    16777216000  8388608000  4294967296   134217728  1234567890  2859072814  8000000000
            Swap:    2147483648   104857600  2042626048
    """
    result = parse_free_output(textwrap.dedent(stdout))

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
