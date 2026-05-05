import os
from hatchling.builders.hooks.plugin.interface import BuildHookInterface

class CustomBuildHook(BuildHookInterface):
    def initialize(self, version, build_data):
        # Allow direct installation from git (without mcp-app support)
        target_dir = "mcp-app/dist"

        if os.path.exists(target_dir):
            if "force_include" not in build_data:
                build_data["force_include"] = {}

            build_data["force_include"][target_dir] = "linux_mcp_server/ui_resources"
