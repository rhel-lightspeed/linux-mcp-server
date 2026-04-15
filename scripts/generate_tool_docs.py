#!/usr/bin/env python3
"""Generate tools documentation from MCP server metadata.

Produces one markdown file per tool category under docs/tools/ by
introspecting the registered tools at runtime so the documentation
exactly matches the JSON schema and descriptions advertised by the
server.

Usage:
    uv run python scripts/generate_tool_docs.py
"""

import asyncio
import shutil
import textwrap

from collections import defaultdict
from pathlib import Path


# Module name → (display order, heading, filename slug, description)
MODULE_CATEGORIES: dict[str, tuple[int, str, str, str]] = {
    "linux_mcp_server.tools.system_info": (
        0,
        "System Information",
        "system-information",
        "Tools for retrieving system, CPU, memory, disk, and hardware information.",
    ),
    "linux_mcp_server.tools.services": (
        1,
        "Services",
        "services",
        "Tools for inspecting systemd services.",
    ),
    "linux_mcp_server.tools.processes": (
        2,
        "Processes",
        "processes",
        "Tools for listing and inspecting running processes.",
    ),
    "linux_mcp_server.tools.logs": (
        3,
        "Logs",
        "logs",
        "Tools for reading systemd journal logs and log files.",
    ),
    "linux_mcp_server.tools.network": (
        4,
        "Network",
        "network",
        "Tools for inspecting network interfaces, connections, and listening ports.",
    ),
    "linux_mcp_server.tools.storage": (
        5,
        "Storage",
        "storage",
        "Tools for inspecting block devices, directories, files, and file contents.",
    ),
    "linux_mcp_server.tools.run_script": (
        6,
        "Script Execution",
        "script-execution",
        "Tools for running scripts on the target system. "
        "These tools are only available when the server is started with "
        "`--toolset run-script` or `--toolset both`. "
        "See [Guarded Command Execution](../guarded-command-execution.md) for details.",
    ),
}

# Tags that indicate internal/hidden tools
HIDDEN_TAGS = {"hidden_from_model"}

# Parameters to skip (documented once in the page header)
SKIP_PARAMS = {"host"}

HOST_NOTE = textwrap.dedent("""\
    !!! note "Remote execution"
        All tools on this page accept an optional **`host`** parameter (string)
        to execute the command on a remote machine via SSH instead of locally.
        See [SSH Configuration](../ssh.md) for details.
""")


def resolve_ref(schema: dict, defs: dict) -> dict:
    """Resolve a $ref in a JSON Schema, merging with sibling keys."""
    if "$ref" not in schema:
        return schema
    ref_path = schema["$ref"]  # e.g. "#/$defs/Transport"
    ref_name = ref_path.rsplit("/", 1)[-1]
    resolved = defs.get(ref_name, {})
    # Sibling keys (default, description) override the ref target
    merged = {**resolved, **{k: v for k, v in schema.items() if k != "$ref"}}
    return merged


def format_type(schema: dict, defs: dict | None = None) -> str:
    """Format a JSON Schema type into a readable string."""
    if defs is None:
        defs = {}

    # Resolve $ref first
    schema = resolve_ref(schema, defs)

    if "anyOf" in schema:
        # Union type — filter out null for optional display
        types = []
        nullable = False
        for variant in schema["anyOf"]:
            resolved = resolve_ref(variant, defs)
            if resolved.get("type") == "null":
                nullable = True
            else:
                types.append(format_type(resolved, defs))
        result = " | ".join(types)
        if nullable and len(types) == 1:
            return types[0]
        return result

    if "enum" in schema:
        values = ", ".join(f'`"{v}"`' for v in schema["enum"])
        return values

    if "const" in schema:
        return f'`"{schema["const"]}"`'

    type_name = schema.get("type", "any")

    if type_name == "integer":
        return "integer"
    if type_name == "number":
        return "number"
    if type_name == "boolean":
        return "boolean"
    if type_name == "string":
        return "string"
    if type_name == "array":
        items = schema.get("items", {})
        return f"array of {format_type(items)}"
    if type_name == "object":
        return "object"

    return type_name


def format_default(value) -> str:
    """Format a default value for display."""
    if value is None:
        return "none"
    if isinstance(value, bool):
        return f"`{str(value).lower()}`"
    if isinstance(value, str):
        if value == "":
            return '`""`'
        return f'`"{value}"`'
    return f"`{value}`"


def format_param(name: str, schema: dict, required: bool, defs: dict | None = None) -> str:
    """Format a single parameter as a markdown bullet point."""
    type_str = format_type(schema, defs)
    desc = schema.get("description", "")

    parts = [f"**`{name}`**"]

    # Build the parenthetical: (type, default: X) or (type, required)
    qualifiers = [type_str]
    if not required:
        if "default" in schema:
            qualifiers.append(f"default: {format_default(schema['default'])}")
    else:
        qualifiers.append("**required**")

    parts.append(f"({', '.join(qualifiers)})")

    # Constraints
    constraints = []
    if "minimum" in schema:
        constraints.append(f"min: {schema['minimum']}")
    if "exclusiveMinimum" in schema:
        constraints.append(f"min: >{schema['exclusiveMinimum']}")
    if "maximum" in schema:
        constraints.append(f"max: {schema['maximum']}")
    if "exclusiveMaximum" in schema:
        constraints.append(f"max: <{schema['exclusiveMaximum']}")

    line = " ".join(parts)
    if desc:
        line += f": {desc}"
    if constraints:
        line += f" [{', '.join(constraints)}]"

    return f"- {line}"


def format_return_field(name: str, schema: dict, defs: dict, indent: int = 0, seen: set | None = None) -> list[str]:
    """Format a single return field as markdown bullet(s), expanding nested objects."""
    if seen is None:
        seen = set()

    prefix = "    " * indent
    resolved = resolve_ref(schema, defs)
    type_str = format_type_for_return(resolved, defs)
    desc = resolved.get("description", "")

    line = f"{prefix}- **`{name}`** ({type_str})"
    if desc:
        line += f": {desc}"

    lines = [line]

    # Expand nested object properties as indented sub-list
    nested_props = get_nested_properties(resolved, defs, seen)
    if nested_props is not None:
        props, nested_defs = nested_props
        for field_name, field_schema in props.items():
            lines.extend(format_return_field(field_name, field_schema, nested_defs, indent + 1, seen.copy()))

    return lines


def get_nested_properties(schema: dict, defs: dict, seen: set) -> tuple[dict, dict] | None:
    """If schema represents an object (directly or via array items), return its properties.

    Returns (properties_dict, defs_dict) or None.  Tracks seen $ref names
    to break recursive types.
    """
    # Direct object with properties
    if schema.get("type") == "object" and "properties" in schema:
        return schema["properties"], defs

    # Array of objects — expand the item type
    if schema.get("type") == "array":
        items = schema.get("items", {})
        items_resolved = resolve_ref(items, defs)
        # Track ref name to detect recursion
        ref_name = items.get("$ref", "").rsplit("/", 1)[-1] if "$ref" in items else None
        if ref_name:
            if ref_name in seen:
                return None  # Recursive — don't expand again
            seen.add(ref_name)
        if items_resolved.get("type") == "object" and "properties" in items_resolved:
            return items_resolved["properties"], defs

    # anyOf — find the non-null object variant
    if "anyOf" in schema:
        for variant in schema["anyOf"]:
            resolved = resolve_ref(variant, defs)
            if resolved.get("type") == "null":
                continue
            ref_name = variant.get("$ref", "").rsplit("/", 1)[-1] if "$ref" in variant else None
            if ref_name:
                if ref_name in seen:
                    return None
                seen.add(ref_name)
            result = get_nested_properties(resolved, defs, seen)
            if result is not None:
                return result

    return None


def format_type_for_return(schema: dict, defs: dict) -> str:
    """Format type for return fields — like format_type but says 'object' for named objects."""
    schema = resolve_ref(schema, defs)

    if "anyOf" in schema:
        types = []
        nullable = False
        for variant in schema["anyOf"]:
            resolved = resolve_ref(variant, defs)
            if resolved.get("type") == "null":
                nullable = True
            else:
                types.append(format_type_for_return(resolved, defs))
        result = " | ".join(types)
        if nullable:
            result += " or null"
        return result

    if schema.get("type") == "array":
        items = resolve_ref(schema.get("items", {}), defs)
        return f"array of {format_type_for_return(items, defs)}"

    return format_type(schema, defs)


def format_return_schema(tool) -> list[str]:
    """Format the return type section for a tool, if it has a structured output schema."""
    schema = tool.output_schema
    if not schema or schema.get("x-fastmcp-wrap-result"):
        return []

    props = schema.get("properties", {})
    if not props:
        return []

    defs = schema.get("$defs", {})

    lines = ["**Returns:**", ""]
    for field_name, field_schema in props.items():
        lines.extend(format_return_field(field_name, field_schema, defs))
    lines.append("")
    return lines


def format_tool(tool) -> str:
    """Format a single tool as markdown."""
    lines = []

    # Heading with tool name
    lines.append(f"## {tool.name}")
    lines.append("")

    # Description
    if tool.description:
        lines.append(tool.description.strip())
        lines.append("")

    # Annotations
    notes = []
    if tool.annotations:
        if tool.annotations.destructiveHint:
            notes.append("This tool may modify system state.")
    if tool.tags:
        if "mcp_apps_only" in tool.tags:
            notes.append("Only available with clients that support MCP apps (e.g. RHEL Lightspeed).")
        if "mcp_apps_exclude" in tool.tags:
            notes.append("Not available with clients that support MCP apps; use the interactive variant instead.")
    if notes:
        for note in notes:
            lines.append("!!! note")
            lines.append(f"    {note}")
            lines.append("")

    # Parameters
    params = tool.parameters.get("properties", {})
    defs = tool.parameters.get("$defs", {})
    required = set(tool.parameters.get("required", []))

    # Filter out skipped params and resolve $refs
    visible_params = {k: resolve_ref(v, defs) for k, v in params.items() if k not in SKIP_PARAMS}

    if visible_params:
        lines.append("**Parameters:**")
        lines.append("")
        for param_name, param_schema in visible_params.items():
            lines.append(format_param(param_name, param_schema, param_name in required, defs))
        lines.append("")

    # Return type
    lines.extend(format_return_schema(tool))

    return "\n".join(lines)


def generate_page(heading: str, description: str, tools: list) -> str:
    """Generate a complete markdown page for a tool category."""
    lines = []

    lines.append(f"# {heading}")
    lines.append("")
    if description:
        lines.append(description)
        lines.append("")
    lines.append(HOST_NOTE)

    for tool in sorted(tools, key=lambda t: t.name):
        lines.append(format_tool(tool))

    return "\n".join(lines)


async def get_tools():
    """Import the server and retrieve all registered tools."""
    from linux_mcp_server.server import mcp

    return await mcp.get_tools()


async def main():
    tools = await get_tools()

    # Group tools by module, filtering out hidden ones
    groups: dict[str, list] = defaultdict(list)
    for tool in tools.values():
        if tool.tags & HIDDEN_TAGS:
            continue

        module = getattr(tool.fn, "__module__", "unknown")
        groups[module].append(tool)

    # Sort groups by defined order
    sorted_groups = sorted(
        groups.items(),
        key=lambda item: MODULE_CATEGORIES.get(item[0], (99, "", "", ""))[0],
    )

    # Write output
    output_dir = Path(__file__).resolve().parent.parent / "docs" / "tools"
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    for module, module_tools in sorted_groups:
        _, heading, slug, description = MODULE_CATEGORIES.get(module, (99, module, module, ""))
        content = generate_page(heading, description, module_tools)
        output_file = output_dir / f"{slug}.md"
        output_file.write_text(content)
        print(f"Generated {output_file}")


if __name__ == "__main__":
    asyncio.run(main())
