#!/usr/bin/env python3
"""Turn `uv audit` findings into one security update per vulnerable package and branch.

Renovate's pep621 manager only extracts direct dependencies, so a vulnerability
in an indirect dependency sits unfixed until the weekly lock file maintenance
run (renovatebot/renovate#46377). The security-updates workflow closes that gap
by auditing uv.lock daily; this script is its parsing and bookkeeping half.

Security updates land on every maintained branch - `main`, the stable
`release-*` branches, and the `post-release-*` branch paired with each - so the
audit is per branch, and so is everything downstream of it.

Subcommands, in the order the workflow calls them:

    select           group each branch's `uv audit` JSON into one update per vulnerable package
    bypass-cooldown  waive the `exclude-newer` cooldown for one package
    verify           assert a package is no longer reported as vulnerable
    commit-message   render the Conventional Commit for one package's update
"""

import argparse
import json
import os
import re
import sys
import tomllib

from pathlib import Path
from typing import Any


ZERO_COOLDOWN = "0 days"
COOLDOWN_SECTION = "[tool.uv.exclude-newer-package]"
COOLDOWN_SECTION_HEADER = f"""
# Packages whose `exclude-newer` cooldown has been waived to land a security
# fix immediately. Maintained by .github/workflows/security-updates.yml; an
# entry stops mattering once the fixed release is older than the global
# cooldown above, so stale entries are harmless.
{COOLDOWN_SECTION}
"""
BARE_KEY = re.compile(r"^[A-Za-z0-9_-]+$")
# The branch names this workflow deals with are flat by construction - see the
# naming note in docs/development/releasing.md - and are used as file names, so
# require that rather than trusting the caller.
BRANCH_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def normalize(name: str) -> str:
    """Normalize a package name per the PyPA spec, as uv does."""
    return re.sub(r"[-_.]+", "-", name).lower()


def slugify(name: str) -> str:
    """Make a package name safe to use in a git ref and an artifact name."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        sys.exit(f"Error: could not read JSON from {path}: {error}")


def load_toml(path: Path) -> dict[str, Any]:
    try:
        return tomllib.loads(path.read_text())
    except (OSError, tomllib.TOMLDecodeError) as error:
        sys.exit(f"Error: could not read TOML from {path}: {error}")


def advisory_identity(entry: dict[str, Any]) -> str:
    """Group OSV entries that describe the same underlying vulnerability.

    OSV reports an issue once per namespace -- pyjwt 2.14.0 comes back as both
    GHSA-42vr-xj54-vc7v and PYSEC-2026-4141 -- with each entry listing the
    others in `aliases`. The shared CVE is the stable identity; advisories with
    no CVE assigned stand alone under their own id.
    """
    ids = [entry["id"], *entry.get("aliases", [])]
    cves = sorted(i for i in ids if i.startswith("CVE-"))
    return cves[0] if cves else entry["id"]


def preferred_id(ids: list[str]) -> str:
    """Pick the id to show for an advisory: GHSA reads best, then CVE."""
    for prefix in ("GHSA-", "CVE-", "PYSEC-"):
        matching = sorted(i for i in ids if i.startswith(prefix))
        if matching:
            return matching[0]
    return sorted(ids)[0]


def collect_updates(audit: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Fold audit findings into one entry per package, dropping unfixable ones."""
    updates: dict[str, Any] = {}
    unfixable: list[str] = []

    for entry in audit.get("vulnerabilities", []):
        dependency = entry["dependency"]
        name = dependency["name"]

        # Nothing to upgrade to yet. Report it so the run is still visible in
        # the job summary, but don't open a PR that cannot fix anything.
        if not entry.get("fix_versions"):
            unfixable.append(f"{name} {dependency['version']}: {entry['id']} has no fixed version published")
            continue

        update = updates.setdefault(
            name,
            {"package": name, "slug": slugify(name), "version": dependency["version"], "advisories": {}},
        )
        advisory = update["advisories"].setdefault(
            advisory_identity(entry),
            {"ids": [], "summary": "", "link": "", "fix_versions": []},
        )
        advisory["ids"] = sorted({*advisory["ids"], entry["id"], *entry.get("aliases", [])})
        advisory["fix_versions"] = sorted({*advisory["fix_versions"], *entry["fix_versions"]})
        # Namespaces summarize the same advisory with varying detail (PYSEC
        # entries are often "No summary provided"); keep the longest.
        if len(entry.get("summary") or "") > len(advisory["summary"]):
            advisory["summary"] = entry["summary"]
        if entry.get("link") and not advisory["link"]:
            advisory["link"] = entry["link"]

    for update in updates.values():
        advisories = sorted(update["advisories"].values(), key=lambda a: preferred_id(a["ids"]))
        for advisory in advisories:
            advisory["id"] = preferred_id(advisory["ids"])
            advisory["cves"] = sorted(i for i in advisory["ids"] if i.startswith("CVE-"))
        update["advisories"] = advisories

    return updates, unfixable


def write_github_output(**values: str) -> None:
    output = os.environ.get("GITHUB_OUTPUT")
    if not output:
        return
    with open(output, "a") as handle:
        for key, value in values.items():
            handle.write(f"{key}={value}\n")


def write_github_summary(text: str) -> None:
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary:
        return
    with open(summary, "a") as handle:
        handle.write(text + "\n")


def read_branches(path: Path) -> list[tuple[str, str]]:
    """Read the `<branch> <commit>` lines the audit job writes as it walks the branches.

    The commit is pinned here rather than re-resolved later so that the audit,
    the lock file update and the pull request all describe the same tree, even
    if the branch moves while the run is in flight.
    """
    try:
        lines = path.read_text().splitlines()
    except OSError as error:
        sys.exit(f"Error: could not read {path}: {error}")

    branches = []
    for line in lines:
        if not line.strip():
            continue
        branch, _, sha = line.partition(" ")
        if not BRANCH_NAME.match(branch) or not sha.strip():
            sys.exit(f"Error: {path}: malformed line {line!r}")
        branches.append((branch, sha.strip()))

    if not branches:
        sys.exit(f"Error: {path} lists no branches")
    return branches


def cmd_select(args: argparse.Namespace) -> int:
    selected: dict[str, Any] = {}
    # The matrix only needs identifiers; the fix job reads the rest back out of
    # the uploaded JSON, which keeps package summaries out of the job names.
    matrix: list[dict[str, str]] = []
    summary: list[str] = []

    for branch, sha in read_branches(args.branches):
        updates, unfixable = collect_updates(load_json(args.audits / f"{branch}.json"))
        selected[branch] = {"sha": sha, "updates": updates}
        matrix += [{"branch": branch, "sha": sha, "package": u["package"], "slug": u["slug"]} for u in updates.values()]

        for note in unfixable:
            print(f"{branch}: no fix available: {note}")
        for update in updates.values():
            ids = ", ".join(advisory["id"] for advisory in update["advisories"])
            print(f"{branch}: will update {update['package']} {update['version']}: {ids}")
        if not updates:
            print(f"{branch}: no fixable vulnerabilities found in uv.lock.")

        lines = [
            f"- `{u['package']}` {u['version']} -> {u['advisories'][0]['fix_versions'][0]}" for u in updates.values()
        ]
        lines += [f"- :warning: {note}" for note in unfixable]
        summary += [f"### {branch}", "", *(lines or ["No fixable vulnerabilities found."]), ""]

    args.output.write_text(json.dumps(selected, indent=2, sort_keys=True) + "\n")
    write_github_output(found=str(bool(matrix)).lower(), updates=json.dumps(matrix))
    write_github_summary("## uv audit\n\n" + "\n".join(summary))
    return 0


def insert_cooldown_waiver(text: str, package: str) -> str:
    """Add `package = "0 days"` to [tool.uv.exclude-newer-package], in order."""
    key = package if BARE_KEY.match(package) else json.dumps(package)
    entry = f'{key} = "{ZERO_COOLDOWN}"'
    lines = text.splitlines()

    try:
        start = lines.index(COOLDOWN_SECTION) + 1
    except ValueError:
        return text.rstrip("\n") + "\n" + COOLDOWN_SECTION_HEADER + entry + "\n"

    end = start
    while end < len(lines) and not lines[end].startswith("["):
        end += 1

    # Keep the table sorted so the diff for a new entry is a single line and
    # the list stays readable as it grows.
    insert_at = end
    for index in range(start, end):
        existing = lines[index].split("=")[0].strip().strip('"')
        if existing and existing > package:
            insert_at = index
            break

    lines.insert(insert_at, entry)
    return "\n".join(lines) + "\n"


def cmd_bypass_cooldown(args: argparse.Namespace) -> int:
    pyproject = load_toml(args.pyproject)
    waived = pyproject.get("tool", {}).get("uv", {}).get("exclude-newer-package", {})
    if any(normalize(name) == normalize(args.package) for name in waived):
        print(f"{args.package} already has a cooldown waiver.")
        return 0

    args.pyproject.write_text(insert_cooldown_waiver(args.pyproject.read_text(), args.package))
    print(f'Waived the exclude-newer cooldown for {args.package} ("{ZERO_COOLDOWN}").')
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    audit = load_json(args.audit)
    target = normalize(args.package)
    remaining = [v for v in audit.get("vulnerabilities", []) if normalize(v["dependency"]["name"]) == target]
    if not remaining:
        print(f"{args.package} is no longer reported as vulnerable.")
        return 0

    ids = ", ".join(sorted({v["id"] for v in remaining}))
    fixes = sorted({f for v in remaining for f in v.get("fix_versions", [])})
    print(
        f"::error::{args.package} is still vulnerable ({ids}) after upgrading it. "
        f"The fix ({', '.join(fixes) or 'none published'}) is most likely outside the version range "
        f"declared for {args.package} in pyproject.toml -- widen it by hand.",
    )
    return 1


def locked_version(lock: Path, package: str) -> str:
    target = normalize(package)
    for entry in load_toml(lock).get("package", []):
        if normalize(entry["name"]) == target:
            return entry["version"]
    sys.exit(f"Error: {package} is not present in {lock}")


def global_cooldown(pyproject: Path) -> str:
    value = load_toml(pyproject).get("tool", {}).get("uv", {}).get("exclude-newer")
    return f'`exclude-newer = "{value}"`' if value else "`exclude-newer`"


def cmd_commit_message(args: argparse.Namespace) -> int:
    selected = load_json(args.updates)
    update = selected.get(args.branch, {}).get("updates", {}).get(args.package)
    if update is None:
        sys.exit(f"Error: no pending security update for {args.package} on {args.branch} in {args.updates}")

    package = update["package"]
    old_version = update["version"]
    new_version = locked_version(args.lock, package)
    advisories = update["advisories"]

    # Prefer CVE ids in the subject: that is what downstream RPM rebuilds are
    # tracked by. Fall back to the advisory ids when no CVE is assigned.
    ids = sorted({cve for advisory in advisories for cve in advisory["cves"]})
    if not ids:
        ids = [advisory["id"] for advisory in advisories]
    shown = ", ".join(ids[:2]) + (f" and {len(ids) - 2} more" if len(ids) > 2 else "")
    # The same advisory is usually fixed on several branches at once, and a
    # pull request list shows neither the base branch nor the head branch - so
    # name the branch in the subject, as Renovate does when it has more than
    # one base branch. `main` is the unmarked case.
    where = "" if args.branch == "main" else f" ({args.branch})"
    subject = f"fix(deps): update {package} to {new_version} for {shown}{where}"

    details = []
    for advisory in advisories:
        aliases = f" ({', '.join(advisory['cves'])})" if advisory["cves"] else ""
        details.append(f"- {advisory['id']}{aliases}: {advisory['summary'] or 'no summary provided'}")
        if advisory["link"]:
            details.append(f"  {advisory['link']}")

    advisory_list = "\n".join(details)
    body = f"""\
`uv audit` reports the following against {package} {old_version} in uv.lock:

{advisory_list}

{package} {old_version} -> {new_version}

Renovate's pep621 manager only tracks direct dependencies, so these updates are
filed by the daily security-updates workflow rather than by Renovate.

The `{COOLDOWN_SECTION}` entry waives the {global_cooldown(args.pyproject)}
cooldown for {package} so the fix can be locked without waiting it out. It has
no further effect once the fixed release is older than that window.
"""
    print(f"{subject}\n\n{body}", end="")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    subparsers = parser.add_subparsers(dest="command", required=True)

    select = subparsers.add_parser("select", help="group uv audit JSON into one update per package and branch")
    select.add_argument("--branches", type=Path, required=True, help="`<branch> <commit>` lines, one per branch")
    select.add_argument(
        "--audits",
        type=Path,
        required=True,
        help="directory of `<branch>.json` files, each `uv audit --output-format=json` output",
    )
    select.add_argument("--output", type=Path, required=True, help="where to write the grouped updates")
    select.set_defaults(func=cmd_select)

    bypass = subparsers.add_parser("bypass-cooldown", help="waive the exclude-newer cooldown for a package")
    bypass.add_argument("--package", required=True)
    bypass.add_argument("--pyproject", type=Path, default=Path("pyproject.toml"))
    bypass.set_defaults(func=cmd_bypass_cooldown)

    verify = subparsers.add_parser("verify", help="assert a package is no longer reported as vulnerable")
    verify.add_argument("--package", required=True)
    verify.add_argument("--audit", type=Path, required=True, help="a fresh audit, taken after the lock file update")
    verify.set_defaults(func=cmd_verify)

    message = subparsers.add_parser("commit-message", help="render the commit message for one package's update")
    message.add_argument("--package", required=True)
    message.add_argument("--branch", required=True, help="the branch the update is being filed against")
    message.add_argument("--updates", type=Path, required=True, help="the JSON written by `select`")
    message.add_argument("--lock", type=Path, default=Path("uv.lock"))
    message.add_argument("--pyproject", type=Path, default=Path("pyproject.toml"))
    message.set_defaults(func=cmd_commit_message)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
