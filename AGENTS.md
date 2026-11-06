# Linux MCP Server

MCP server for Linux system diagnostics. Two operating modes, selected by the
`LINUX_MCP_TOOLSET` env var:

- `fixed` (default) — a fixed set of **read-only** diagnostic tools.
- `run_script` / `both` — additionally exposes **guarded command execution**
  (`run_script`), which may modify the system. Writes there are permitted only
  because the gatekeeper, user confirmation, and sandbox guard that path — no
  other tool has that backstop.

## Commands

```bash
uv sync                      # Install dependencies
uv run pytest                # Run tests
uv run ruff check src tests  # Lint
uv run pyright               # Type check
make verify                  # All checks (required before commit)
```

## Project Layout

- `src/linux_mcp_server/tools/` - MCP tools (logs, network, pcp, processes, services, storage, system_info, run_script)
- `src/linux_mcp_server/commands.py` - Command definitions (the `COMMANDS` registry)
- `src/linux_mcp_server/formatters.py` / `parsers.py` - Output formatting and parsing
- `src/linux_mcp_server/gatekeeper/` - LLM-based safety validation of `run_script` scripts
- `src/linux_mcp_server/auth.py` / `auth_policy.py` - Authentication and authorization policy
- `src/linux_mcp_server/audit.py` - Audit logging of executed operations
- `src/linux_mcp_server/redaction/` - Credential redaction of tool output and error messages
- `src/linux_mcp_server/tool_result.py` - `ToolResult` for tools whose text differs from their structured content
- `src/linux_mcp_server/connection/ssh.py` - Remote execution over SSH
- `src/linux_mcp_server/config.py` / `execution_context.py` / `toolset.py` - Config, per-call context, toolset selection
- `tests/` - Mirrors src structure

## Rules

**Code:** PEP 8, type hints required, async/await for I/O, 120 char max, prefer Pydantic over dataclasses

- Tools take `host: Host` - `localhost` runs locally, anything else over SSH
- All network/SSH operations must have timeouts; prefer asyncssh-native timeouts over `asyncio.wait_for`
- SSH uses key-based auth only (no plaintext passwords); connection and command errors must include the host for debugging
- Validate config and env vars at startup (Pydantic `model_validator`), not lazily; use secure defaults
- Error messages must be clear enough for an LLM to understand and act on

**Testing:**
- Run `make verify` before committing
- Tests should verify behavior, not just chase coverage — a test that asserts nothing meaningful is worse than none
- Use parameterized tests and fixtures (shared fixtures go in `conftest.py`)
- Use pytest-mock (`mocker` fixture) for mocking instead of `unittest.mock` imports
- Use `autospec=True` when patching; `spec=<object>` with Mock
- 100% patch coverage for new code
- Do not use `@pytest.mark.asyncio` for tests. It's not necessary because the project uses `asyncio_mode = "auto"`

**Security (Critical):**
- Fixed-mode tools (tagged `fixed`; everything outside `run_script.py`) must be **strictly read-only**
  (`readOnlyHint=True`) and self-sufficient: no gatekeeper, confirmation, or sandbox
  protects them. Never interpolate untrusted input (args, hostnames, file contents)
  into a shell command — pass argument vectors and validate/escape inputs.
- Validate all input; use allowlists for file paths.
- `run_script` may modify the system, but only behind the gatekeeper + user
  confirmation + sandbox. Those guardrails must stay intact and fail closed — a
  script must never reach execution having bypassed validation or confirmation.
- The gatekeeper and auth policy must **fail closed**: any validation error,
  timeout, or missing/invalid policy denies rather than allows.

## Adding Tools

1. Create tool in `src/linux_mcp_server/tools/` using the `@mcp.tool()` decorator, with `tags` that include its
   toolset (`fixed` or `run_script`). With a few exceptions, each tool must have a `host: Host` parameter.
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

Read `docs/development/ci-hardening.md` before adding or changing anything under `.github/workflows/`.

Tool docs under `docs/tools/` are auto-generated — run `uv run python scripts/generate_tool_docs.py` after adding or modifying tools.
