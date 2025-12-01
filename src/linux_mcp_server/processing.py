"""Classes and functions for ingesting and processing data."""

import typing as t

from mcp.server.fastmcp.exceptions import ToolError

from linux_mcp_server.connection.ssh import execute_command
from linux_mcp_server.utils.types import Host


# Type aliases for the collect-parse-filter pattern
CommandKey = tuple[str, ...]
RawCommandOutput = str
ParsedData = dict[str, t.Any]
CommandList = list[list[str]]
CollectFunc = t.Callable[[CommandList, Host | None], t.Awaitable[dict[CommandKey, RawCommandOutput]]]
ParseFunc = t.Callable[[dict[CommandKey, RawCommandOutput]], t.Awaitable[ParsedData]]
FilterFunc = t.Callable[[ParsedData, list[str] | None], t.Awaitable[ParsedData]]


class Rummager:
    def __init__(
        self,
        collect_func: CollectFunc | None = None,
        parse_func: ParseFunc | None = None,
        filter_func: FilterFunc | None = None,
    ):
        if collect_func is not None:
            self._collect = collect_func  # type: ignore[method-assign]
        if parse_func is not None:
            self._parse = parse_func  # type: ignore[method-assign]
        if filter_func is not None:
            self._filter = filter_func  # type: ignore[method-assign]

    async def rummage(
        self, commands: CommandList, fields: list[str] | None = None, host: Host | None = None
    ) -> ParsedData:
        """
        Step 1: Collect raw outputs from the commands.
        Step 2: Parse the raw outputs into structured data.
        Step 3: Filter the parsed data to include only specified fields.
        """
        raw_outputs = await self._collect(commands, host)
        parsed_data = await self._parse(raw_outputs)
        filtered_data = await self._filter(parsed_data, fields)
        return filtered_data

    async def _collect(self, commands: CommandList, host: Host | None = None) -> dict[CommandKey, RawCommandOutput]:
        """
        Default collect function: Execute multiple commands and cache results.

        Returns a dictionary mapping command tuples to their stdout output.
        Commands are executed in order, and each unique command is only executed once.
        """
        cache: dict[CommandKey, RawCommandOutput] = {}

        for command in commands:
            command_key = tuple(command)
            if command_key in cache:
                continue

            try:
                returncode, stdout, _ = await execute_command(
                    command,
                    host=host,
                )
                if returncode == 0 and stdout:
                    cache[command_key] = stdout
            except (ValueError, ConnectionError) as e:
                raise ToolError(f"Error executing command {' '.join(command)}: {str(e)}") from e

        return cache

    async def _parse(self, raw_outputs: dict[CommandKey, RawCommandOutput]) -> ParsedData:
        """
        Default parse function: Return a dictionary of unmodified raw outputs.
        """
        return ParsedData(iterable=dict(raw_outputs))

    async def _filter(self, parsed_data: ParsedData, fields: list[str] | None) -> ParsedData:
        """
        Default filter function: Filter parsed data to include only specified fields.

        If fields is None, return all data. Otherwise, return only the specified fields.
        Supports nested field access using dot notation (e.g., "ram.total").
        """
        if fields is None:
            return parsed_data

        filtered: ParsedData = {}
        for field in fields:
            if "." in field:
                # Handle nested fields
                parts = field.split(".", 1)
                parent, child = parts[0], parts[1]
                if parent in parsed_data:
                    if parent not in filtered:
                        filtered[parent] = {}
                    if isinstance(parsed_data[parent], dict) and child in parsed_data[parent]:
                        if not isinstance(filtered[parent], dict):
                            filtered[parent] = {}
                        filtered[parent][child] = parsed_data[parent][child]
            elif field in parsed_data:
                filtered[field] = parsed_data[field]

        return filtered
