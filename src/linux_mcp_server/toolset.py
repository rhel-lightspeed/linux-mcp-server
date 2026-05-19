# Toolset matching for authorization policies
# Maps @fixed/@run_script/@both in policy rules to tag-based tool filters.

from dataclasses import dataclass


@dataclass
class Toolset:
    name: str
    tags: set[str]  # Tool must have one of these tags

    def includes_tool(self, tool_tags: set[str]) -> bool:
        # Tool must have one of the required tags
        return not self.tags.isdisjoint(tool_tags)


# Registry of available toolsets for policy matching
_TOOLSETS = {
    "fixed": Toolset(
        name="fixed",
        tags={"fixed"},
    ),
    "run_script": Toolset(
        name="run_script",
        tags={"run_script"},
    ),
    "both": Toolset(
        name="both",
        tags={
            "fixed",
            "run_script",
        },
    ),
}


# Get a toolset by name(fixed, run_script, both)
def get_toolset(name: str) -> Toolset | None:
    return _TOOLSETS.get(name)
