# Contributing to Linux MCP Server

Thank you for your interest in contributing! This document provides guidelines for contributing to the Linux MCP Server project.

### Prerequisites

- **Python 3.10 or higher**
- **git**
- **pip**
- **uv** - https://github.com/astral-sh/uv#installation

### Method 1: Setup with pip and a virtual environment

**Step 1: Clone the repository**

```bash
git clone https://github.com/rhel-lightspeed/linux-mcp-server.git
cd linux-mcp-server
```

**Step 2: Create and activate virtual environment**

```bash
python -m venv .venv
source .venv/bin/activate  # On Linux/macOS
# OR
.venv\Scripts\activate     # On Windows
```

**Step 3: Install the package in editable mode with dev dependencies**

```bash
pip install -e . --group dev
```

**Step 4: Verify the installation**

```bash
python -m linux_mcp_server
```

**Step 5: Run the tests**

```bash
pytest
```

All tests should pass.

### Method 2: Setup with uv

**Step 1: Clone the repository**

```bash
git clone https://github.com/rhel-lightspeed/linux-mcp-server.git
cd linux-mcp-server
```

**Step 2: Create virtual environment and install dev dependencies**

Note that by default `uv` creates an editable install as well as installs all packages in the `dev` dependency group.

```bash
uv sync
```

**Step 3: Verify the installation**

```bash
uv run linux_mcp_server
```

**Step 5: Run the tests**

```bash
uv run pytest
```

All tests should pass.


## Development Workflow

We follow Test-Driven Development (TDD) principles:

### 1. RED - Write a Failing Test
```python
# tests/test_new_feature.py
import pytest
from linux_mcp_server.tools import new_module

async def test_new_feature():
    result = await new_module.new_function()
    assert "expected" in result
```

### 2. GREEN - Implement Minimal Code to Pass
```python
# src/linux_mcp_server/tools/new_module.py
async def new_function():
    return "expected result"
```

### 3. REFACTOR - Improve Code Quality
- Improve readability
- Remove duplication
- Ensure all tests still pass

### 4. Commit
```bash
git add .
git commit -m "feat: add new feature

- Detailed description of what was added
- Tests included
- All tests passing"
```

## Code Standards

### Style Guidelines
- Follow PEP 8 for Python code
- Use type hints for function parameters and return values
- Use async/await for I/O operations
- Maximum line length: 120 characters

### Documentation
- Add docstrings to all public functions
- Use clear, descriptive variable names
- Comment complex logic

### Testing
- Write tests for all new features
- Maintain project test coverage above 70%, patch test coverage must be 100%.
- Use descriptive test names that explain what is being tested

## Adding New Tools

When adding a new diagnostic tool:

1. **Create the tool function in appropriate module:**
   ```python
    # src/linux_mcp_server/tools/my_tool.py
    import typing as t

    @mcp.tool(
      title="Useful Tool",
      description="Description for LLM to understand the tool.",
      annotations=ToolAnnotations(readOnlyHint=True),
    )
    @log_tool_call
    async def my_tool_name(
        param1: str,
    ) -> str:
        """Documentation string further describing the tool if necessary.
        """
        returncode, stdout, _ = await execute_command(["ps", "aux", "--sort=-%cpu"], host=host, username=username)
        if returncode != 0:
          raise ToolError

        return stdout
    ```

2. **Write tests:**
   ```python
   # tests/test_my_tool.py
   import pytest
   from linux_mcp_server.tools import my_tool

   async def test_my_tool():
       result = await my_tool.my_diagnostic_function()
       assert isinstance(result, str)
       assert "expected content" in result.lower()

   # Test server integration
   async def test_server_has_my_tool():
       from linux_mcp_server.server import mcp
       tools = await mcp.list_tools()
       tool_names = [t.name for t in tools]
       assert "my_tool_name" in tool_names
   ```

3. **Update documentation:**
   - Add tool description to README.md
   - Add usage examples to USAGE.md

## Commit Message Format

We use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only changes
- `test`: Adding missing tests
- `refactor`: Code change that neither fixes a bug nor adds a feature
- `perf`: Performance improvement
- `chore`: Changes to build process or auxiliary tools

### Examples:
```
feat(tools): add disk smart status tool

- Implement smart status checking
- Add tests for SMART data parsing
- Update documentation

Closes #123
```

```
fix(network): handle missing network interfaces gracefully

Previously crashed when network interface disappeared
during enumeration. Now catches exception and continues.
```

## Security Guidelines

### Read-Only Operations
- All tools MUST be read-only
- Never implement any function that modifies system state
- Use subprocess with caution; validate all inputs

### Input Validation
- Always validate user input
- Use whitelists for file paths (see `read_log_file`)
- Sanitize parameters passed to shell commands

### Error Handling
- Never expose sensitive information in error messages
- Catch broad exceptions at the function level
- Return user-friendly error messages

## Testing Guidelines

### Unit Tests
Test individual functions in isolation:
```python
async def test_function_returns_correct_format():
    result = await module.function()
    assert isinstance(result, str)
    assert "expected" in result
```

### Integration Tests
Test that tools work with the MCP server:
```python
async def test_server_has_tool():
    from linux_mcp_server.server import mcp
    tools = await mcp.list_tools()
    tool_names = [t.name for t in tools]
    assert "tool_name" in tool_names

async def test_server_calls_tool():
    from linux_mcp_server.server import mcp
    result = await mcp.call_tool("tool_name", {})
    assert isinstance(result, str)
```

### Running Tests
Coverage is enabled by default. Coverage reports can be found in `coverage/html/index.html`.

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_services.py

# Run with verbose output
pytest -v

# Run tests without coverage
pytest --no-cov
```

## Documentation

### Code Documentation
- Use docstrings for all public functions
- Include parameter descriptions
- Document return values
- Add usage examples for complex functions

### User Documentation
- Update README.md for new features
- Add examples to USAGE.md
- Document configuration options
- Include troubleshooting tips

## Pull Request Process

1. **Create a feature branch:**
   ```bash
   git checkout -b feature/my-new-feature
   ```

2. **Make changes following TDD:**
   - Write tests first
   - Implement feature
   - Ensure all tests pass

3. **Update documentation:**
   - Update README.md if needed
   - Update USAGE.md with examples
   - Update CONTRIBUTING.md if changing development process

4. **Run all tests:**
   ```bash
   pytest
   ```

5. **Commit with conventional commit messages:**
   ```bash
   git commit -m "feat: add new diagnostic tool"
   ```

6. **Push and create pull request:**
   ```bash
   git push origin feature/my-new-feature
   ```

7. **PR Description should include:**
   - What the change does
   - Why it's needed
   - How to test it
   - Screenshots/examples if applicable

## Code Review Checklist

- [ ] Tests added and passing
- [ ] Code follows style guidelines
- [ ] Documentation updated
- [ ] Commit messages follow conventional format
- [ ] No security vulnerabilities introduced
- [ ] All operations are read-only
- [ ] Error handling is appropriate
- [ ] Input validation is present

## Questions or Issues?

- Open an issue on GitHub
- Check existing issues first
- Provide detailed information:
  - System information (OS, version)
  - Steps to reproduce
  - Expected vs actual behavior
  - Relevant logs

## License

By contributing, you agree that your contributions will be licensed under the Apache 2.0 License.

