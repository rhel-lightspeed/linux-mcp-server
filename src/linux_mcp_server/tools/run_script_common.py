import shlex
import typing as t


ScriptType = t.Literal["python", "bash"]
SCRIPT_TYPE_PYTHON = "python"
SCRIPT_TYPE_BASH = "bash"

BASH_STRICT_PREAMBLE = "set -euo pipefail; "

SYSTEMD_RUN_ARGS = [
    "--quiet",
    "--pipe",
    "--collect",
    "--wait",
    "--property=WorkingDirectory=/tmp",
    "--property=PrivateTmp=true",
    "--property=NoNewPrivileges=true",
]
SYSTEMD_RUN_READONLY_ARGS = [
    "--property=ReadOnlyPaths=/",
    "--property=RestrictAddressFamilies=AF_UNIX",
]
SYSTEMD_RUN_COMMAND = "/usr/bin/sudo /usr/bin/systemd-run {args}"

WRAPPER_TEMPLATE = """\
set -euo pipefail
SCRIPT={script}
if command -v sudo >/dev/null 2>&1 && command -v systemd-run >/dev/null 2>&1 && sudo -l whoami >/dev/null 2>&1; then
  exec {systemd_run_command} {script_type} -c "$SCRIPT"
else
  exec {script_type} -c "$SCRIPT"
fi
"""

RUN_SCRIPT_COMMON_DESCRIPTION = """\
A bash script should be used for simple operations that can be expressed cleanly
as a few shell commands, but a Python script should be used if complex processing
is needed. Bash scripts are run with strict mode (set -euo pipefail) applied by
the invocation, so handle expected non-zero exit codes in the script (e.g. with
`|| true`) where needed.

Write short, simple scripts that are easy to review - do not include unnecessary
complexity such as elaborate logging or handling unlikely corner cases.
"""


def _wrap_script(script_type: ScriptType, script: str) -> list[str]:
    """Wrap a script in a wrapper script that uses sudo+systemd-run when available, else run script directly."""
    wrapper_script = WRAPPER_TEMPLATE.format(
        systemd_run_command=SYSTEMD_RUN_COMMAND.format(args=" ".join(SYSTEMD_RUN_ARGS)),
        script_type=script_type,
        script=shlex.quote((BASH_STRICT_PREAMBLE + script) if script_type == SCRIPT_TYPE_BASH else script),
    )
    return ["bash", "-c", wrapper_script]
