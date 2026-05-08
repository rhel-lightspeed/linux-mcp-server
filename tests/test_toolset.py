from linux_mcp_server.toolset import get_toolset
from linux_mcp_server.toolset import Toolset


class TestToolset:
    def test_includes_tool_with_required_tags(self):
        # Toolset requires "run_script" tag
        toolset = Toolset(
            name="run_script",
            tags={"run_script"},
        )

        # Tool has the required tag
        assert toolset.includes_tool({"run_script"})
        assert toolset.includes_tool({"run_script", "other_tag"})

    def test_includes_tool_missing_required_tags(self):
        # Toolset requires "run_script" tag
        toolset = Toolset(
            name="run_script",
            tags={"run_script"},
        )

        # Tool doesn't have the required tag
        assert not toolset.includes_tool(set())
        assert not toolset.includes_tool({"other_tag"})


class TestGetToolset:
    def test_get_fixed_toolset(self):
        toolset = get_toolset("fixed")
        assert toolset is not None
        assert toolset.name == "fixed"
        assert toolset.tags == {"fixed"}

    def test_get_run_script_toolset(self):
        toolset = get_toolset("run_script")
        assert toolset is not None
        assert toolset.name == "run_script"
        assert toolset.tags == {"run_script"}

    def test_get_both_toolset(self):
        toolset = get_toolset("both")
        assert toolset is not None
        assert toolset.name == "both"
        assert toolset.tags == {"fixed", "run_script"}

    def test_get_unknown_toolset(self):
        toolset = get_toolset("unknown")
        assert toolset is None
