# Toolset matching for authorization policies
# Maps @fixed/@run_script/@both in policy rules to tag-based tool filters.

from dataclasses import dataclass


@dataclass
class Toolset:
    name: str
    include_tags: set[str]  # Tool must have all of these tags
    exclude_tags: set[str]  # Tool must have none of these tags

    def includes_tool(self, tool_tags: set[str]) -> bool:
        # Tool must have all required tags
        if self.include_tags and not self.include_tags.issubset(tool_tags):
            return False

        # Tool must not have any excluded tags
        if self.exclude_tags and self.exclude_tags.intersection(tool_tags):
            return False

        return True


# Registry of available toolsets for policy matching
_TOOLSETS = {
    "fixed": Toolset(
        name="fixed",
        include_tags=set(),
        exclude_tags={"run_script"},
    ),
    "run_script": Toolset(
        name="run_script",
        include_tags={"run_script"},
        exclude_tags=set(),
    ),
    "both": Toolset(
        name="both",
        include_tags=set(),
        exclude_tags=set(),
    ),
}


# Get a toolset by name(fixed, run_script, both)
def get_toolset(name: str) -> Toolset | None:
    return _TOOLSETS.get(name)
