# Toolset matching for authorization policies
# Maps @fixed/@run_script/@both in policy rules to tag-based tool filters.

from dataclasses import dataclass


@dataclass
class Toolset:
    name: str
    includes_tags: set[str]  # Tool must have all of these tags
    excludes_tags: set[str]  # Tool must have none of these tags

    def includes_tool(self, tool_tags: set[str]) -> bool:
        # Tool must have all required tags
        if self.includes_tags and not self.includes_tags.issubset(tool_tags):
            return False

        # Tool must not have any excluded tags
        if self.excludes_tags and self.excludes_tags.intersection(tool_tags):
            return False

        return True


# Registry of available toolsets for policy matching
_TOOLSETS = {
    "fixed": Toolset(
        name="fixed",
        includes_tags=set(),
        excludes_tags={"run_script"},
    ),
    "run_script": Toolset(
        name="run_script",
        includes_tags={"run_script"},
        excludes_tags=set(),
    ),
    "both": Toolset(
        name="both",
        includes_tags=set(),
        excludes_tags=set(),
    ),
}


def get_toolset(name: str) -> Toolset | None:
    """Get a toolset by name (e.g., "fixed", "run_script", "both")."""
    return _TOOLSETS.get(name)
