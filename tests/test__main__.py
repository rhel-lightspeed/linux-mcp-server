import pytest

from linux_mcp_server.__main__ import cli


def test_cli():
    with pytest.raises(SystemExit):
        cli()
