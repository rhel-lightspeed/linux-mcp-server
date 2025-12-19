import textwrap

import pytest

from linux_mcp_server.parsers import parse_service_count


@pytest.mark.parametrize(
    "stdout, expected",
    [
        ("", 0),
        (
            """UNIT                     LOAD   ACTIVE SUB     DESCRIPTION
               ssh.service              loaded active running OpenBSD Secure Shell server
               cron.service             loaded active running Regular background program processing
               nginx.service            loaded active running A high performance web server
            """,
            3,
        ),
        (
            """Some header text
               ssh.service is running
               another.service is active
               not a service line
            """,
            2,
        ),
    ],
)
def test_parse_service_count(stdout, expected):
    result = parse_service_count(textwrap.dedent(stdout))

    assert result == expected
