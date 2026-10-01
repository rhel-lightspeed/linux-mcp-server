#!/usr/bin/python3

# This script generates tests/data/pcp-metrics-rhel10.jsonl.
#
# Run on a RHEL 10 host with pcp installed and pmcd and plogger enabled

import json
import re
import socket
import subprocess
import sys


# Get the location of the primary PCP archive for this host
def get_pcp_archive_location() -> str:
    result = subprocess.run(
        ["/usr/libexec/pcp/bin/pmconfig", "PCP_ARCHIVE_DIR"], capture_output=True, text=True, check=True
    )
    archive_dir = result.stdout.strip().split("=")[1]

    hostname = socket.gethostname()

    return f"{archive_dir}/{hostname}"


def parse_entry(entry_text: str) -> dict[str, str | bool]:
    # Entries look like:
    #
    # hotproc.psinfo.start_stack [address of the stack segment for the process]
    #    Data Type: 31-bit unsigned int  InDom: 3.39 0xc00027
    #    Semantics: discrete  Units: nonea
    #
    # The help message and the description fields may be missing
    lines = entry_text.strip().split("\n")
    name_rest = lines[0].strip().split(maxsplit=1)
    entry: dict[str, str | bool] = {"name": name_rest[0]}

    if len(name_rest) > 1:
        rest = name_rest[1].strip()
        if rest.startswith("[") and rest.endswith("]"):
            entry["help"] = rest[1:-1]

    # Details
    description = {
        parts[0]: parts[1]
        for piece in re.split(r"\s{2,}", "\n".join(lines[1::]))
        if len(parts := re.split(r"\s*:\s*", piece.strip(), maxsplit=1)) == 2
    }

    entry.update(description)

    # Whether the metric has instances, which is what pcp_query_metrics turns into
    # one "metric-instance" column apiece and the guide marks [per-device] and the
    # like. Which instance domain is not interesting, only that there is one, so
    # keep a flag and drop the InDom itself to save space/clutter. A singular metric
    # reads "InDom: PM_INDOM_NULL 0xffffffff", so match the name and not the whole
    # field.
    indom = entry.pop("InDom", None)
    if isinstance(indom, str) and not indom.startswith("PM_INDOM_NULL"):
        entry["instanced"] = True

    return entry


def run_pminfo(*, archive: bool = False, descriptions: bool = False, help: bool = False) -> list[dict[str, str | bool]]:
    args = ["pminfo", "-t"]
    if archive:
        args += ["-a", get_pcp_archive_location()]
    if descriptions:
        args += ["-d"]
    if help:
        args += ["-t"]

    result = subprocess.run(args, capture_output=True, text=True, check=True)

    if descriptions:
        entries = result.stdout.strip().split("\n\n")
    else:
        entries = result.stdout.strip().split("\n")

    return [parse_entry(stripped) for e in entries if (stripped := e.strip()) != ""]


# First load the definitions of all the available metrics on the system
all_metrics = {e["name"]: e for e in run_pminfo(descriptions=True, help=True)}

# Now print only the ones that are logged, supplementing with information from the
# availables - this sometimes has the description/help when the logge metric doesn't
for metric in run_pminfo(archive=True, help=True):
    metric.update(all_metrics.get(metric["name"], {}))
    json.dump(metric, sys.stdout)
    sys.stdout.write("\n")
