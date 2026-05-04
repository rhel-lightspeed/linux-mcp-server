#!/usr/bin/env python3
"""PermissionRequest hook for run_script permission decisions.

Fires when Claude Code is about to show a permission dialog for run_script.
For readonly scripts (already safety-evaluated by the PreToolUse prompt hook),
returns "allow" to skip the redundant dialog. For non-readonly scripts, exits
silently so the dialog shows and the user can confirm.

This eliminates the need for users to manually add an "allow" permission rule.
The PreToolUse command hook's "ask" decision still guarantees confirmation for
non-readonly scripts even if the user has an explicit "allow" rule.
"""

import json
import os
import sys


def main():
    data = json.load(sys.stdin)
    tool_input = data.get("tool_input", {})
    readonly = tool_input.get("readonly", True)
    always_confirm = os.environ.get(
        "LINUX_MCP_ALWAYS_CONFIRM_SCRIPTS", ""
    ).lower() in ("true", "1", "yes")

    if readonly and not always_confirm:
        json.dump(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PermissionRequest",
                    "decision": {
                        "behavior": "allow",
                        "updatedPermissions": [
                            {
                                "type": "addRules",
                                "rules": [
                                    {"toolName": "mcp__plugin_linux-mcp-server_linux-mcp-server__run_script"}
                                ],
                                "behavior": "allow",
                                "destination": "session",
                            }
                        ],
                    },
                }
            },
            sys.stdout,
        )


if __name__ == "__main__":
    main()
