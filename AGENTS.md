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
- Use `autospec=True` when patching; `spec=<object>` with MagicMock
- 100% patch coverage for new code

**Security (Critical):**
- All tools must be read-only with `readOnlyHint=True`
- Validate all input, use allowlists for file paths, sanitize shell params

## Adding Tools

1. Create tool in `src/linux_mcp_server/tools/` using `@mcp.tool()`, `@log_tool_call`, `@disallow_local_execution_in_containers` decorators
2. Register command in `commands.py`
3. Write tests in `tests/tools/`

See `src/linux_mcp_server/tools/processes.py` for reference.

## Commits & PRs

Use [Conventional Commits](https://www.conventionalcommits.org/): `<type>(<scope>): <subject>`

Types: `feat`, `fix`, `docs`, `test`, `refactor`, `perf`, `chore`

**PRs must be small and focused** - one logical change per PR. Split large changes into incremental PRs.

## Docs

Full details: `docs/contributing.md` | Architecture: `docs/architecture.md` | API: `docs/api/`
