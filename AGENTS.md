# Linux MCP Server

Read-only [Model Context Protocol](https://modelcontextprotocol.io/) server for Linux system administration, diagnostics, and troubleshooting. Targets RHEL-based systems. All tools are read-only by default; an optional guarded command execution feature allows validated script execution with LLM-based safety checks and human approval.

## Quick Reference

```bash
uv sync                      # Install dependencies
uv run pytest                # Run tests
uv run ruff check src tests  # Lint
uv run pyright               # Type check
make verify                  # All checks (sync + lint + types + tests)
```

## Architecture

### Fixed Toolset (`LINUX_MCP_TOOLSET=fixed`)

```
MCP Client (Claude Desktop, etc.)
    |  MCP Protocol (stdio / http / streamable-http)
FastMCP Server (server.py - tool discovery, transport, middleware)
    |
Tool Modules (tools/*.py - read-only tools)
    |
Command Registry (commands.py - immutable command definitions with fallbacks)
    |
SSH Executor (connection/ssh.py)  /  Local Executor
    |
Target Linux System (local or remote via SSH)
```

### Guarded Command Execution (`LINUX_MCP_TOOLSET=run_script`)

```
MCP Client (Claude Desktop, etc.)
    |  MCP Protocol (stdio / http / streamable-http)
FastMCP Server (server.py - tool discovery, transport, middleware)
    |
run_script tools (tools/run_script.py)
    |
validate_script ──> Gatekeeper (gatekeeper/check_run_script.py)
    |                    |
    |                LLM Safety Check (via LiteLLM)
    |                    |
    |                Risk Assessment (approve / reject / needs-confirmation)
    |
SSH Executor (connection/ssh.py)  /  Local Executor
    |
Target Linux System (local or remote via SSH)
```

## Project Layout

```
src/linux_mcp_server/
  server.py              # FastMCP setup, middleware, transport config
  config.py              # Pydantic-based config from LINUX_MCP_* env vars
  commands.py            # Centralized command registry (MappingProxyType)
  models.py              # Data models (SystemInfo, CpuInfo, MemoryInfo, etc.)
  parsers.py             # Output parsing (ps, free, lsblk, ss, etc.)
  formatters.py          # Human-readable output formatting
  audit.py               # Audit logging with sensitive field redaction
  mcp_app.py             # MCP app UI constants
  logging_config.py      # Structured logging setup
  __main__.py            # CLI entry point

  tools/                 # MCP tool definitions
    system_info.py       # get_system/cpu/memory/disk/hardware_information
    services.py          # list_services, get_service_status, get_service_logs
    network.py           # get_network_interfaces/connections, get_listening_ports
    processes.py         # list_processes, get_process_info
    storage.py           # list_block_devices/directories/files, read_file
    logs.py              # get_journal_logs, read_log_file
    run_script.py        # validate_script, run_script, run_script_with_confirmation, etc.

  connection/
    ssh.py               # Singleton SSH connection manager with pooling

  gatekeeper/
    check_run_script.py  # LLM-based script safety validation

  utils/
    decorators.py        # Container detection, tool call logging
    validation.py        # Input validation helpers
    format.py            # Output formatting utilities
    types.py             # Type hint definitions
    enum.py              # Custom StrEnum

tests/                   # Mirrors src structure
  conftest.py            # Shared fixtures (mock SSHExecutor, MCP client)
  tools/                 # Tool-specific tests
  parsers/               # Parser tests
  connection/            # SSH tests
  gatekeeper/            # Gatekeeper tests
  functional/            # Integration tests

mcp-app/                 # React TypeScript UI for interactive script approval
docs/                    # MkDocs documentation site
scripts/                 # Utility scripts (tool doc generation, etc.)
```

## Tools Overview

### Fixed Tools (read-only, always available)

| Category | Tools |
|----------|-------|
| System   | `get_system_information`, `get_cpu_information`, `get_memory_information`, `get_disk_usage`, `get_hardware_information` |
| Services | `list_services`, `get_service_status`, `get_service_logs` |
| Network  | `get_network_interfaces`, `get_network_connections`, `get_listening_ports` |
| Processes| `list_processes`, `get_process_info` |
| Storage  | `list_block_devices`, `list_directories`, `list_files`, `read_file` |
| Logs     | `get_journal_logs`, `read_log_file` |

### Guarded Command Execution (optional, `LINUX_MCP_TOOLSET=run_script|both`)

`validate_script`, `run_script`, `run_script_with_confirmation`, `run_script_interactive`, `get_execution_state`, `reject_script`

Every tool accepts an optional `host` parameter for remote execution via SSH.

## Key Configuration (`LINUX_MCP_` prefix)

| Variable | Purpose | Default |
|----------|---------|---------|
| `TOOLSET` | `fixed`, `run_script`, or `both` | `fixed` |
| `TRANSPORT` | `stdio`, `http`, or `streamable-http` | `stdio` |
| `GATEKEEPER_MODEL` | LLM model for script validation | required for `run_script` |
| `USER` | Default SSH username | - |
| `SSH_KEY_PATH` | Path to SSH private key | - |
| `VERIFY_HOST_KEYS` | SSH host key verification | `true` |
| `COMMAND_TIMEOUT` | Command timeout (seconds) | `30` |
| `ALLOWED_LOG_PATHS` | Comma-separated allowlist for `read_log_file` | none |
| `MAX_FILE_READ_BYTES` | Max file size for `read_file` | 1MB |
| `LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING` | `INFO` |

Full reference: `docs/config-reference.md`

## Tech Stack

- **Python 3.10+** with async/await throughout
- **FastMCP** (^2.14.4) - MCP server framework (currently on 2.x; upgrade to 3.x planned)
- **asyncssh** - SSH with key-based auth, connection pooling
- **Pydantic** - Config and data validation
- **LiteLLM** - Gatekeeper model inference
- **ruff** / **pyright** / **pytest** - Lint, types, tests
- **uv** - Package manager

## Rules

**Code:** PEP 8, type hints required, async/await for I/O, 120 char max, prefer Pydantic over dataclasses

**Testing:**
- Run `make verify` before committing
- Use parameterized tests and fixtures (shared fixtures go in `conftest.py`)
- Use pytest-mock (`mocker` fixture) for mocking instead of `unittest.mock` imports
- Use `autospec=True` when patching; `spec=<object>` with Mock
- 100% patch coverage for new code

**Security (Critical):**
- All tools must be read-only with `readOnlyHint=True`
- Validate all input, use allowlists for file paths, sanitize shell params
- SSH key-based auth only (no passwords)
- Host key verification enabled by default
- Sensitive fields redacted in audit logs

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

Full details: `docs/contributing.md` | Architecture: `docs/architecture.md` | Security: `docs/security.md`

Tool docs under `docs/tools/` are auto-generated — run `uv run python scripts/generate_tool_docs.py` after adding or modifying tools.
