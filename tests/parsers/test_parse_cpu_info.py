import pytest

from linux_mcp_server.parsers import parse_cpu_info


@pytest.mark.parametrize(
    "stdout, expected",
    [
        ({}, {"model": "", "logical_cores": 0}),
        (
            {
                "model": "model name\t: Intel(R) Core(TM) i7-10700 CPU @ 2.90GHz\n",
                "logical_cores": "8\n",
                "physical_cores": "core id\t\t: 0\ncore id\t\t: 1\ncore id\t\t: 2\ncore id\t\t: 3\n",
                "frequency": "cpu MHz\t\t: 2900.000\n",
                "load_avg": "0.50 0.75 1.00 1/234 5678\n",
            },
            {
                "model": "Intel(R) Core(TM) i7-10700 CPU @ 2.90GHz",
                "logical_cores": 8,
                "physical_cores": 4,
                "frequency_mhz": 2900.0,
                "load_avg_1m": 0.50,
                "load_avg_5m": 0.75,
                "load_avg_15m": 1.00,
            },
        ),
    ],
)
def test_parse_cpu_info(stdout, expected):
    result = parse_cpu_info(stdout)

    assert all(getattr(result, attr) == value for attr, value in expected.items())
