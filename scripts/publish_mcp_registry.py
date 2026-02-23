#!/usr/bin/env python3
"""
Script to publish the MCP server to the Model Context Protocol registry.
This script is designed to run in GitHub Actions but can be tested locally.
"""

import io
import os
import platform
import subprocess
import sys
import tarfile
import urllib.request

from pathlib import Path


def get_platform_info():
    system = platform.system().lower()
    machine = platform.machine().lower()

    archs = {
        "x86_64": "amd64",
        "aarch64": "arm64",
    }

    arch = archs.get(machine, machine)

    return system, arch


def download_publisher(url, dest_path):
    print(f"Downloading mcp-publisher from {url}")

    try:
        with urllib.request.urlopen(url) as response:
            data = response.read()

        mcp_publisher_tar = io.BytesIO(data)

        with tarfile.open(fileobj=mcp_publisher_tar, mode="r:gz") as tar:
            member = tar.getmember("mcp-publisher")
            member.name = dest_path.name
            tar.extract(member, path=dest_path.parent, filter="data")

        if not dest_path.exists():
            sys.exit("Error: mcp-publisher binary not found after extraction")

        dest_path.chmod(0o755)

    except Exception as e:
        message = f"Error: Failed to download or extract mcp-publisher\nURL: {url}\nDetails: {e}\n"
        sys.exit(message)


def run_command(args, error_message):
    try:
        result = subprocess.run(args, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        message = f"Error: {error_message}"
        if e.stderr:
            message = f"{message}\n{e.stderr}"

        sys.exit(message)

    return result


def update_server_json(version):
    print("Updating version in server.json")

    server_json_path = Path("server.json")
    data = server_json_path.read_text()
    data = data.replace("$version", version)
    server_json_path.write_text(data)


def main():
    mcp_publisher_version = os.environ.get("MCP_PUBLISHER_VERSION", "v1.4.0")

    github_ref = os.environ.get("GITHUB_REF", "")
    if not github_ref:
        message = (
            "Error: GITHUB_REF environment variable is required\n"
            "This should be set automatically in GitHub Actions or manually for local testing"
        )
        sys.exit(message)

    version = github_ref.removeprefix("refs/tags/v")
    if not version:
        sys.exit("Error: Could not extract version from GITHUB_REF")

    print(f"Publishing version: {version}")

    system, arch = get_platform_info()
    download_url = f"https://github.com/modelcontextprotocol/registry/releases/download/{mcp_publisher_version}/mcp-publisher_{system}_{arch}.tar.gz"

    publisher_path = Path("mcp-publisher").absolute()
    download_publisher(download_url, publisher_path)

    update_server_json(version)

    print("Authenticating to MCP Registry via GitHub OIDC")
    run_command([str(publisher_path), "login", "github-oidc"], "Failed to authenticate to MCP Registry")

    print("Publishing server to MCP Registry")
    run_command([str(publisher_path), "publish"], "Failed to publish to MCP Registry")

    print(f"Successfully published version {version} to MCP Registry")


if __name__ == "__main__":
    main()
