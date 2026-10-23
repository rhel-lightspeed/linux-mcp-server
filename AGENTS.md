# Linux MCP Server

Read-only MCP server for Linux system diagnostics.

## Commands

```bash
uv sync                      # Install dependencies
uv run pytest                # Run tests
uv run ruff check src tests  # Lint
uv run pyright               # Type check
make verify                  # All checks (required before commit)
```

## Project Layout

- `src/linux_mcp_server/tools/` - MCP tools (logs, network, processes, services, storage, system_info)
- `src/linux_mcp_server/commands.py` - Command definitions
- `src/linux_mcp_server/formatters.py` / `parsers.py` - Output formatting and parsing
- `tests/` - Mirrors src structure

## Rules

**Code:** PEP 8, type hints required, async/await for I/O, 120 char max, prefer Pydantic over dataclasses

**Testing:**
- Run `make verify` before committing
- Use parameterized tests and fixtures (shared fixtures go in `conftest.py`)
- Use pytest-mock (`mocker` fixture) for mocking instead of `unittest.mock` imports
- Use `autospec=True` when patching; `spec=<object>` with Mock
- 100% patch coverage for new code
- Do not use `@pytest.mark.asyncio` for tests. It's not necessary because the project uses `asyncio_mode = "auto"`

**Security (Critical):**
- All tools must be read-only with `readOnlyHint=True`
- Validate all input, use allowlists for file paths, sanitize shell params

## Adding Tools

1. Create tool in `src/linux_mcp_server/tools/` using the `@mcp.tool()` decorator, with a required `host: Host` parameter
2. Register command in `commands.py`
3. Write tests in `tests/tools/`

See `src/linux_mcp_server/tools/processes.py` for reference.

Everything a tool returns is scanned for credentials as it is rendered, so return
ordinary Python data and let FastMCP build the text from it. A tool whose text has to
say something other than its structured content returns
`linux_mcp_server.tool_result.ToolResult` - not FastMCP's, which converts both halves
before they can be scanned.

## Commits & PRs

Use [Conventional Commits](https://www.conventionalcommits.org/): `<type>(<scope>): <subject>`

Types: `feat`, `fix`, `docs`, `test`, `refactor`, `perf`, `chore`

**PRs must be small and focused** - one logical change per PR. Split large changes into incremental PRs.

## Docs

Full details: `docs/contributing.md` | Architecture: `docs/architecture.md`

Tool docs under `docs/tools/` are auto-generated — run `uv run python scripts/generate_tool_docs.py` after adding or modifying tools.
