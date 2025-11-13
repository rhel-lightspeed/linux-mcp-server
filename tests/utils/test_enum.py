import pytest

from linux_mcp_server.utils.enum import StrEnum


@pytest.fixture
def color():
    class Color(StrEnum):
        red = "red"
        blue = "blue"

    return Color


def test_enum(color):
    assert color.red == "red"
    assert color.blue == "blue"
    assert color.red in "Little red riding hood"
    assert color.blue in "I'm blue, da-ba-dee, da-ba-di"


def test_enum_str(color):
    assert str(color.red) == "red"
    assert str(color.blue) == "blue"
