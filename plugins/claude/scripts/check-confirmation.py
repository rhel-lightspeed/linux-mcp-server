#!/usr/bin/env python3
"""PreToolUse command hook for run_script confirmation decisions.

Runs in parallel with the prompt hook. Returns permissionDecision "ask" when
the script requires user confirmation (non-readonly or always_confirm policy).
Otherwise exits silently, letting the prompt hook's allow/deny decision stand.

The hook precedence rule (deny > ask > allow) ensures correct composition:
- prompt=allow + this=ask  → ask (user confirms non-readonly scripts)
- prompt=allow + this=silent → allow (readonly scripts run without prompting)
- prompt=deny + either → deny (unsafe scripts are always blocked)
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

    if not readonly or always_confirm:
        if not readonly:
            reason = f"""
  \033[1mScript modifies system:\033[0m

  \033[1;34mHost\033[0m: {tool_input.get('host', "")}
  \033[1;34mDescription\033[0m: {tool_input.get('description', "")}

"""
        else:
            reason = f"""Script requires confirmation:

\033[1mHost\033[0m: {tool_input.get('host', "")}
\033[1mDescription\033[0m: {tool_input.get('description', "")}
"""

        json.dump(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "ask",
                    "permissionDecisionReason": reason,
                }
            },
            sys.stdout,
        )


if __name__ == "__main__":
    main()
