# Copyright Contributors to the linux-mcp-server project
# SPDX-License-Identifier: Apache-2.0
import subprocess

from collections import namedtuple
from datetime import datetime
from typing import Any


def shell(
    command,
    expect: Any = 0,
    doAssert=True,
    hint="",
    cwd=None,
    stderrInOutput=False,
    user=None,
    silent=False,
    host=None,
):
    """Run shell commands

    This function will run a command you pass to it in a string and assert whether it completed successfully
    Parameters
    ------------
        command: str
            The shell command that will be executed
        expect: int, list, range, str, Optional
            The expected return code of the command (default to 0)
        doAssert: bool, Optional
            Boolean switch to disable asserting of return code (default to True)
        hint: str, Optional
            Description or purpose of the command being called, in case it is non-trivial
        cwd: str, bytes, path-like, Optional
            The working directory in which to execute the command
        stderrInOutput: bool, Optional
            Boolean switch to control if stderr is available in output (default to False)
        user: str, Optional
            The user that will be used to execute the command
        host: str, Optional
            Remote host to execute command on. SSH connection will be used. default to None.
    Return
    -----------
        Result: namedtuple
            Tuple containing two objects, returncode and the command output.
    """
    if isinstance(expect, int):
        expect = [expect]
    elif isinstance(expect, list):
        expect = [int(x) for x in expect]
    elif isinstance(expect, range):
        expect = list(expect)
    elif isinstance(expect, str):
        # no support for parsing strings at the moment
        expect = [int(expect)]
    if user:
        command = f"su - {user} -c '{command}'"
    if not silent:
        print("\n###################################")
        print(f"--- shell.START: {hint if hint else ''}")
        print(f"--- TIMESTAMP: {datetime.now()}")
        print(f"--- COMMAND:\n# {command}")
    stderrParameter = subprocess.PIPE
    if stderrInOutput:
        stderrParameter = subprocess.STDOUT
    if host:
        cmd = [
            "ssh",
            "-o StrictHostKeyChecking=no",
            "-o UserKnownHostsFile=/dev/null",
            host,
            command,
        ]
        process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=stderrParameter, cwd=cwd)
    else:
        cmd = f"set -euo pipefail; {command}"
        process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=stderrParameter, cwd=cwd, shell=True)

    returncode = process.returncode
    stdout = process.stdout.decode() if process.stdout else ""
    stderr = process.stderr.decode() if process.stderr else ""

    if not silent:
        print(f"--- RETURNCODE:\n{returncode}")
        print(f"--- STDOUT:\n{stdout}")
        print(f"--- STDERR:\n{stderr}")

    if doAssert:
        if returncode not in expect:
            if not silent:
                print(f"--- shell.FAIL: returncode expected {expect}, got {returncode}")

            raise AssertionError(f" FAIL: returncode expected {expect}, got {returncode}")
        if not silent:
            print(f"--- shell.PASS: returncode expected {expect}, got {returncode}")
    else:
        if not silent:
            print(f"--- shell.END_WITHOUT_ASSERT, got returcode {returncode}")
    if not silent:
        print("###################################\n")

    return namedtuple("Result", ["returncode", "stdout", "stderr"])(returncode, stdout, stderr)
