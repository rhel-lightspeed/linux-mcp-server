#!/usr/bin/env python3

import json
import os
import sys

from pathlib import Path
from typing import Annotated
from typing import Literal

import typer
import yaml

from utils import BlockStyleDumper

from linux_mcp_server.gatekeeper import check_run_script


app = typer.Typer()


def run_test_file(test_case_file: str, label: str | None = None) -> tuple[list[dict], list[dict]]:
    """Run a single test case file through the gatekeeper.

    Returns (test_cases, results) where test_cases are the inputs and results
    are the corresponding output dicts.
    """
    if label is None:
        label = test_case_file
    with open(test_case_file, "r") as f:
        data = yaml.safe_load(f)

    if isinstance(data, dict) and "cases" in data:
        test_cases = data["cases"]
    else:
        test_cases = None

    if not test_cases:
        typer.echo(f"No test cases found in {test_case_file}")
        raise typer.Exit(code=1)

    results = []

    with typer.progressbar(test_cases, label=f"Running {label}") as progress:
        for test_case in progress:
            id = test_case["id"]
            description = test_case["description"]
            script_type = test_case["script_type"]
            script = test_case["script"]
            readonly = test_case.get("readonly", False)

            result = {
                "id": id,
                "description": description,
                "script_type": script_type,
                "script": script,
                "readonly": readonly,
            }

            try:
                gatekeeper_result = check_run_script(
                    description=description,
                    script_type=script_type,
                    script=script,
                    readonly=readonly,
                )

                result_data = {"status": gatekeeper_result.status.value}
                if gatekeeper_result.detail:
                    result_data["detail"] = gatekeeper_result.detail
                result["result"] = result_data
            except Exception as e:
                result["result"] = {"exception": str(e)}

            results.append(result)

    return test_cases, results


def build_output_cases(test_cases: list[dict], results: list[dict], *, output_all: bool = False) -> list[dict]:
    """Build output cases, filtering to only non-same results and adding expected_result."""
    output_cases = []
    for test_case, result in zip(test_cases, results):
        expected = test_case.get("result")
        actual = result.get("result")

        if not output_all:
            # Skip cases where actual matches expected
            if (
                expected is not None
                and actual is not None
                and "exception" not in actual
                and expected.get("status") == actual.get("status")
            ):
                continue

        output = {
            "id": result["id"],
            "description": result["description"],
            "script_type": result["script_type"],
            "script": result["script"],
            "readonly": result["readonly"],
            "result": actual,
        }
        if expected is not None:
            output["expected_result"] = expected

        output_cases.append(output)

    return output_cases


def compute_summary(test_cases: list[dict], results: list[dict]) -> dict[str, int]:
    """Build summary comparing actual results against expected results from input."""
    summary = {"same": 0, "ok_to_forbidden": 0, "forbidden_to_ok": 0, "other_mismatch": 0, "exception": 0}
    for test_case, result in zip(test_cases, results):
        actual = result.get("result")
        if actual is not None and "exception" in actual:
            summary["exception"] += 1
            continue

        expected = test_case.get("result")
        if expected is None or actual is None:
            continue

        expected_status = expected.get("status")
        actual_status = actual.get("status")

        if expected_status == actual_status:
            summary["same"] += 1
        elif expected_status == "OK":
            summary["ok_to_forbidden"] += 1
        elif actual_status == "OK":
            summary["forbidden_to_ok"] += 1
        else:
            summary["other_mismatch"] += 1

    return summary


def print_summary_table(file_summaries: list[tuple[str, dict[str, int]]], file=sys.stdout):
    """Print a formatted summary table of results across multiple files."""
    columns = ["same", "ok_to_forbidden", "forbidden_to_ok", "other_mismatch", "exception"]
    headers = ["file"] + columns

    # Compute column widths
    col_widths = [len(h) for h in headers]
    rows = []
    for path, summary in file_summaries:
        row = [path] + [str(summary.get(c, 0)) for c in columns]
        rows.append(row)
        for i, val in enumerate(row):
            col_widths[i] = max(col_widths[i], len(val))

    # Print header
    header_line = "  ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers))
    print(header_line, file=file)
    print("  ".join("-" * w for w in col_widths), file=file)

    # Print rows
    for row in rows:
        print("  ".join(val.ljust(col_widths[i]) for i, val in enumerate(row)), file=file)

    # Print totals
    if len(rows) > 1:
        totals = ["TOTAL"] + [str(sum(int(row[i]) for row in rows)) for i in range(1, len(headers))]
        for i, val in enumerate(totals):
            col_widths[i] = max(col_widths[i], len(val))
        print("  ".join("-" * w for w in col_widths), file=file)
        print("  ".join(val.ljust(col_widths[i]) for i, val in enumerate(totals)), file=file)


@app.command()
def main(
    test_case_file: Annotated[
        str | None, typer.Argument(help="Path to the Gatekeeper test case file to process.")
    ] = None,
    all_files: Annotated[
        bool, typer.Option("--all", help="Discover and run all test case files in testcases/.")
    ] = False,
    output_file: Annotated[
        str | None, typer.Option("--output-file", "-o", help="Path to the output file to write results.")
    ] = None,
    output_all: Annotated[
        bool,
        typer.Option(
            "--output-all",
            help="Output all the test results including the case that the actual result matches the expected result.",
        ),
    ] = False,
    output_format: Annotated[
        Literal["json", "yaml"],
        typer.Option(
            "--output-format",
            "-f",
            help="Format for exported data: 'json' or 'yaml' (default: yaml).",
        ),
    ] = "yaml",
):
    """
    Run a set of test cases through the gatekeeper, and report results.

    Each test case in the input YAML should have:
    - description: What the script does
    - script_type: Type of script (e.g., "bash")
    - script: The script content
    - readonly: Whether the script is readonly (optional, defaults to False)

    The output will include the original test case fields plus a "result" field with:
    - status: GatekeeperStatus value (OK, BAD_DESCRIPTION, POLICY, etc.)
    - detail: Details if status is not OK
    """

    if test_case_file and all_files:
        typer.echo("Cannot specify both a test case file and --all.", err=True)
        raise typer.Exit(code=1)

    if not test_case_file and not all_files:
        typer.echo("Must specify either a test case file or --all.", err=True)
        raise typer.Exit(code=1)

    if "LINUX_MCP_GATEKEEPER_MODEL" not in os.environ:
        typer.echo(
            "Please set the LINUX_MCP_GATEKEEPER_MODEL environment variable to specify the Gatekeeper model to use."
        )
        raise typer.Exit(code=1)

    if all_files:
        testcases_dir = Path(__file__).parent / "testcases"
        files = sorted(testcases_dir.glob("**/*.yaml"))
        if not files:
            typer.echo(f"No test case files found in {testcases_dir}")
            raise typer.Exit(code=1)

        all_output_cases = []
        file_summaries = []
        for tc_file in files:
            rel_path = str(tc_file.relative_to(testcases_dir))
            test_cases, results = run_test_file(str(tc_file), label=rel_path)
            summary = compute_summary(test_cases, results)
            file_summaries.append((rel_path, summary))
            all_output_cases.extend(build_output_cases(test_cases, results, output_all=output_all))

        # Build combined summary
        combined_summary = {"same": 0, "ok_to_forbidden": 0, "forbidden_to_ok": 0, "other_mismatch": 0, "exception": 0}
        for _, s in file_summaries:
            for k in combined_summary:
                combined_summary[k] += s[k]

        output = {"summary": combined_summary, "cases": all_output_cases}

        if output_format == "json":
            output_string = json.dumps(output, indent=2)
        else:
            output_string = yaml.dump(output, indent=2, sort_keys=False, Dumper=BlockStyleDumper)

        if output_file:
            with open(output_file, "w") as f:
                f.write(output_string)
            typer.echo(f"Wrote {len(all_output_cases)} results to {output_file}")
            print_summary_table(file_summaries, file=sys.stdout)
        else:
            sys.stdout.write(output_string)
            print_summary_table(file_summaries, file=sys.stderr)
    else:
        assert test_case_file is not None

        test_cases, results = run_test_file(test_case_file)
        summary = compute_summary(test_cases, results)
        output_cases = build_output_cases(test_cases, results, output_all=output_all)

        output = {"summary": summary, "cases": output_cases}

        if output_format == "json":
            output_string = json.dumps(output, indent=2)
        else:
            output_string = yaml.dump(output, indent=2, sort_keys=False, Dumper=BlockStyleDumper)

        if output_file:
            with open(output_file, "w") as f:
                f.write(output_string)
            typer.echo(f"Wrote {len(output_cases)} results to {output_file}")
        else:
            sys.stdout.write(output_string)


if __name__ == "__main__":
    app()
