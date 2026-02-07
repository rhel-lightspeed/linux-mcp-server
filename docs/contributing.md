# Contributing to Linux MCP Server

Thank you for your interest in contributing! This guide will help you set up your development environment and understand our workflow.

## Quick Start (TL;DR)

Experienced developers can get started in 60 seconds:

```bash
git clone https://github.com/rhel-lightspeed/linux-mcp-server.git
cd linux-mcp-server
uv sync                    # Install dependencies
uv run pytest              # Verify everything works
uv run linux-mcp-server    # Run the server
```

Read on for detailed setup and contribution guidelines.

---

## Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | 3.10+ | Check with `python3 --version` |
| git | Any | For cloning and version control |
| uv | Latest | [Installation guide](https://github.com/astral-sh/uv#installation) (recommended) |

---

## Development Setup

### Option 1: Using uv (Recommended)

[uv](https://github.com/astral-sh/uv) is the fastest way to set up your environment.

```bash
# Clone the repository
git clone https://github.com/rhel-lightspeed/linux-mcp-server.git
cd linux-mcp-server

# Create virtual environment and install all dependencies (dev + lint + test)
uv sync

# Verify installation
uv run linux-mcp-server --help

# Run tests
uv run pytest
```

### Option 2: Using pip

```bash
# Clone the repository
git clone https://github.com/rhel-lightspeed/linux-mcp-server.git
cd linux-mcp-server

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# Verify installation
python -m linux_mcp_server --help

# Run tests
pytest
```

---

## Project Structure

```text
linux-mcp-server/
├── src/linux_mcp_server/
│   ├── tools/              # MCP tool implementations
│   │   ├── dnf.py           # DNF package manager tools
│   │   ├── logs.py         # Log reading tools
│   │   ├── network.py      # Network diagnostic tools
│   │   ├── processes.py    # Process management tools
│   │   ├── services.py     # Systemd service tools
│   │   ├── storage.py      # Storage/disk tools
│   │   └── system_info.py  # System information tools
│   ├── connection/         # SSH connection handling
│   ├── utils/              # Shared utilities
│   ├── audit.py            # Audit logging
│   ├── commands.py         # Command definitions
│   ├── config.py           # Configuration management
│   ├── formatters.py       # Output formatting
│   ├── parsers.py          # Command output parsing
│   └── server.py           # FastMCP server setup
├── tests/                  # Test suite (mirrors src structure)
├── docs/                   # Documentation
└── pyproject.toml          # Project configuration
```

---

## Development Workflow

We follow Test-Driven Development (TDD):

### 1. RED: Write a Failing Test

```python
# tests/tools/test_my_feature.py
import pytest

async def test_my_feature_returns_expected_format():
    from linux_mcp_server.tools import my_module
    result = await my_module.my_function()
    assert "expected" in result
```

### 2. GREEN: Write Minimal Code to Pass

```python
# src/linux_mcp_server/tools/my_module.py
async def my_function() -> str:
    return "expected result"
```

### 3. REFACTOR: Improve Without Breaking Tests

- Clean up code structure
- Remove duplication
- Ensure all tests still pass

---

## Adding New Tools

Tools are the core functionality of the MCP server. Here's how to add a new diagnostic tool:

### 1. Create the Tool

```python
# src/linux_mcp_server/tools/my_tool.py
import typing as t

from mcp.types import ToolAnnotations
from pydantic import Field

from linux_mcp_server.audit import log_tool_call
from linux_mcp_server.commands import get_command
from linux_mcp_server.server import mcp
from linux_mcp_server.utils.decorators import disallow_local_execution_in_containers
from linux_mcp_server.utils.types import Host


@mcp.tool(
    title="My Tool Title",
    description="Brief description for LLM to understand when to use this tool.",
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def my_tool_name(
    param1: t.Annotated[str, Field(description="Parameter description")],
    host: Host | None = None,
) -> str:
    """Extended documentation if needed."""
    cmd = get_command("my_command")
    returncode, stdout, stderr = await cmd.run(host=host)

    if returncode != 0:
        return f"Error: {stderr}"

    return stdout
```

### 2. Register the Command

Add the command definition to `src/linux_mcp_server/commands.py`:

```python
"my_command": Command(cmd=["my-binary", "--option"], sudo=False),
```

### 3. Write Tests

```python
# tests/tools/test_my_tool.py
import pytest
from unittest.mock import AsyncMock, patch

async def test_my_tool_returns_output():
    with patch("linux_mcp_server.tools.my_tool.get_command") as mock_cmd:
        mock_cmd.return_value.run = AsyncMock(return_value=(0, "output", ""))

        from linux_mcp_server.tools.my_tool import my_tool_name
        result = await my_tool_name(param1="value")

        assert "output" in result

async def test_server_exposes_my_tool():
    from linux_mcp_server.server import mcp
    tools = await mcp.list_tools()
    tool_names = [t.name for t in tools]
    assert "my_tool_name" in tool_names
```

### 4. Update Documentation

- Add tool description to the [Usage Guide](usage.md)
- Update the README if it's a significant feature

---

## Code Quality

### Linting and Type Checking

We use **ruff** for linting and **pyright** for type checking:

```bash
# Run linter
uv run ruff check src tests

# Auto-fix lint issues
uv run ruff check --fix src tests

# Run type checker
uv run pyright
```

### Style Guidelines

- **PEP 8** compliance (enforced by ruff)
- **Type hints** for all function parameters and return values
- **async/await** for I/O operations
- **120 character** max line length
- **Docstrings** for public functions

### Testing Requirements

- Write tests for all new features
- **Patch coverage**: 100% for new code
- **Project coverage**: Maintain above 70%
- Use descriptive test names explaining what's being tested

```bash
# Run all tests with coverage
uv run pytest

# Run specific test file
uv run pytest tests/tools/test_processes.py

# Run with verbose output
uv run pytest -v

# Skip coverage (faster iteration)
uv run pytest --no-cov
```

Coverage reports are generated in `coverage/htmlcov/index.html`.

---

## Security Guidelines

### Read-Only Operations Only

All tools **must** be read-only. This project is designed for safe diagnostics:

- Never implement functions that modify system state
- Use subprocess with validated inputs only
- Always include `readOnlyHint=True` in tool annotations

### Input Validation

- Validate all user-provided input
- Use allowlists for file paths (see `read_log_file` implementation)
- Sanitize parameters before passing to shell commands

### Error Handling

- Never expose sensitive information in error messages
- Use try/except at the function level
- Return user-friendly error messages

---

## Commit Messages

We use [Conventional Commits](https://www.conventionalcommits.org/):

```text
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

| Type | Description |
|------|-------------|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation changes |
| `test` | Adding or updating tests |
| `refactor` | Code change that doesn't fix a bug or add a feature |
| `perf` | Performance improvement |
| `chore` | Build process or tooling changes |

### Examples

```text
feat(tools): add disk SMART status tool

- Implement SMART status checking via smartctl
- Add tests for SMART data parsing
- Update documentation

Closes #123
```

```text
fix(network): handle missing network interfaces gracefully

Previously crashed when a network interface disappeared during
enumeration. Now catches the exception and continues with
remaining interfaces.
```

---

## Pull Request Process

### 1. Create a Feature Branch

```bash
git checkout -b feature/my-new-feature
```

### 2. Develop Using TDD

- Write tests first
- Implement the feature
- Ensure all tests pass
- Run linting: `uv run ruff check src tests`
- Run type checking: `uv run pyright`

### 3. Commit Your Changes

```bash
git add .
git commit -m "feat(tools): add my new feature"
```

### 4. Push and Create PR

```bash
git push origin feature/my-new-feature
```

### 5. PR Description Checklist

Your PR should include:

- [ ] What the change does
- [ ] Why it's needed
- [ ] How to test it
- [ ] Screenshots/examples (if applicable)

### Code Review Checklist

- [ ] Tests added and passing
- [ ] Code follows style guidelines
- [ ] Documentation updated
- [ ] Commit messages follow conventional format
- [ ] No security vulnerabilities introduced
- [ ] All operations are read-only
- [ ] Error handling is appropriate
- [ ] Input validation is present

---

## Related Documentation

- **[Installation Guide](install.md)**: Setting up the server for end users
- **[Usage Guide](usage.md)**: Available tools and examples
- **[Architecture](architecture.md)**: System design overview
- **[API Reference](api/index.md)**: Detailed API documentation
- **[Troubleshooting](troubleshooting.md)**: Common issues and solutions

---

## Getting Help

- **Search existing issues** before opening a new one
- **Open an issue** on [GitHub](https://github.com/rhel-lightspeed/linux-mcp-server/issues) with:
  - System information (OS, Python version)
  - Steps to reproduce
  - Expected vs actual behavior
  - Relevant logs or error messages

---

## License

By contributing, you agree that your contributions will be licensed under the Apache 2.0 License.
