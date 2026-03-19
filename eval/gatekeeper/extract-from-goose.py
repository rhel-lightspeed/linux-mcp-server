#!/usr/bin/env python3

import json
import subprocess
import sys

from typing import Annotated

import typer
import yaml

from utils import BlockStyleDumper

from linux_mcp_server.gatekeeper import GatekeeperResult


app = typer.Typer()


@app.command()
def main(
    session_file: Annotated[
        str | None,
        typer.Argument(help="Path to Goose session export JSON file. If not provided, uses --session-id."),
    ] = None,
    session_id: Annotated[
        str | None,
        typer.Option(help="Goose session ID to export (goose session list). Ignored if session_file is provided."),
    ] = None,
    output_file: Annotated[
        str | None, typer.Option("--output-file", "-o", help="Path to the output file to write extracted test cases.")
    ] = None,
):
    """
    Extract Gatekeeper test cases from a goose session file and write them to an output file.

    Note: Due to a Goose bug, tool calls and responses are ordered backwards in the session export.
    This script matches them up by tool call IDs to handle this correctly.
    """
    if session_file:
        # Read from file
        with open(session_file, "r") as f:
            json_output = json.load(f)
    elif session_id:
        # Export from Goose
        raw_export = subprocess.run(
            ["goose", "session", "export", "--session-id", session_id, "--format", "json"],
            text=True,
            capture_output=True,
        )
        if raw_export.returncode != 0:
            typer.echo(f"Error calling '{' '.join(raw_export.args)}'\n{raw_export.stderr}")
            raise typer.Exit(code=1)
        json_output = json.loads(raw_export.stdout)
    else:
        typer.echo("Error: Either session_file or --session-id must be provided")
        raise typer.Exit(code=1)

    # Due to a Goose bug, tool requests and responses are ordered backwards
    # First pass: collect all tool requests
    tool_requests = {}
    for message in json_output["conversation"]:
        if message["role"] == "assistant":
            for content in message.get("content", []):
                if content.get("type") == "toolRequest":
                    request_id = content["id"]
                    tool_call = content["toolCall"]
                    value = tool_call["value"]
                    tool_name = value["name"]

                    # Handle both with and without extension prefix
                    if "__" in tool_name:
                        _, tool = tool_name.split("__", 1)
                    else:
                        tool = tool_name

                    arguments = value["arguments"]

                    if tool.startswith("run_script"):
                        tool_requests[request_id] = {
                            "description": arguments["description"],
                            "script_type": arguments["script_type"],
                            "script": clean_script(arguments["script"]),
                            "readonly": tool == "run_script_readonly",
                        }

    # Second pass: collect tool responses and match with requests
    tool_responses = {}
    for message in json_output["conversation"]:
        if message["role"] == "user":
            for content in message.get("content", []):
                if content.get("type") == "toolResponse":
                    response_id = content["id"]
                    tool_result = content.get("toolResult", {})
                    value = tool_result.get("value", {})
                    is_error = value.get("isError", False)

                    if response_id in tool_requests:
                        # Extract gatekeeper result from the response
                        if is_error:
                            # Gatekeeper rejected the call
                            error_content = value.get("content", [])
                            if error_content and len(error_content) > 0:
                                error_text = error_content[0].get("text", "")
                                # Parse the status and detail from error message
                                result_data = parse_gatekeeper_result(error_text)
                                tool_responses[response_id] = result_data
                        else:
                            # Gatekeeper approved the call
                            tool_responses[response_id] = {"status": "OK"}

    # Combine requests and responses
    result = []
    for request_id, request_data in tool_requests.items():
        item = dict(request_data)
        if request_id in tool_responses:
            item["result"] = tool_responses[request_id]
        result.append(item)

    # Build metadata from session info
    meta = {}
    if "created_at" in json_output:
        meta["timestamp"] = json_output["created_at"]
    if "provider_name" in json_output:
        meta["provider"] = json_output["provider_name"]
    model_config = json_output.get("model_config", {})
    if "model_name" in model_config:
        meta["model"] = model_config["model_name"]

    # Output results
    output = {}
    if meta:
        output["meta"] = meta
    output["cases"] = result

    modeline = "# yaml-language-server: $schema=../../testcase-schema.json\n"
    yaml_content = yaml.dump(output, indent=2, sort_keys=False, Dumper=BlockStyleDumper)

    if output_file is None:
        sys.stdout.write(modeline)
        sys.stdout.write(yaml_content)
    else:
        with open(output_file, "w") as f:
            f.write(modeline)
            f.write(yaml_content)
            typer.echo(f"Wrote {len(result)} test cases to {output_file}")


def clean_script(script: str) -> str:
    """Clean up script whitespace for readable YAML block style output.

    Strips leading/trailing newlines and trailing whitespace from each line,
    which would otherwise cause PyYAML to fall back to quoted style.
    """
    lines = script.strip("\n").split("\n")
    return "\n".join(line.rstrip() for line in lines) + "\n"


def parse_gatekeeper_result(error_text: str) -> dict:
    """
    Parse gatekeeper error message to extract status and detail.

    Error messages follow the pattern: "Status prefix: detail"
    e.g., "Policy violation: The script adds new repositories..."

    Uses GatekeeperResult.parse_from_description() to parse the result.
    """
    try:
        result = GatekeeperResult.parse_from_description(error_text)
    except ValueError:
        # Not a recognized gatekeeper status - the error happened after
        # the gatekeeper approved (e.g. timeout, connection error)
        return {"status": "OK"}

    parsed = {"status": result.status.value}
    if result.detail:
        parsed["detail"] = result.detail
    return parsed


if __name__ == "__main__":
    app()
