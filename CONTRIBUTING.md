# Contributing to Linux MCP Server

Thank you for your interest in contributing! This document provides guidelines for contributing to the Linux MCP Server project.

## Development Setup

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd linux-mcp-server
   ```

2. **Set up development environment:**
   ```bash
   uv venv
   source .venv/bin/activate
   uv sync --editable --group dev
   ```

3. **Verify setup:**
   ```bash
   pytest
   ```

## Development Workflow

We follow Test-Driven Development (TDD) principles:

### 1. RED - Write a Failing Test
```python
# tests/test_new_feature.py
import pytest
from linux_mcp_server.tools import new_module

@pytest.mark.asyncio
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
- Maximum line length: 100 characters

### Documentation
- Add docstrings to all public functions
- Use clear, descriptive variable names
- Comment complex logic

### Testing
- Write tests for all new features
- Maintain test coverage above 80%
- Use descriptive test names that explain what is being tested

## Adding New Tools

When adding a new diagnostic tool:

1. **Create the tool function in appropriate module:**
   ```python
   # src/linux_mcp_server/tools/my_tool.py
   import typing as t Optional
   from .ssh_executor import execute_command

   async def my_diagnostic_function(
       host: Optional[str] = None,
       username: Optional[str] = None
   ) -> str:
       """
       Brief description of what this tool does.

       Args:
           host: Optional remote host to connect to via SSH
           username: Optional SSH username (required if host is provided)

       Returns:
           Formatted string with diagnostic information
       """
       try:
           # Implementation using execute_command for local/remote execution
           returncode, stdout, stderr = await execute_command(
               ["your", "command"],
               host=host,
               username=username
           )

           if returncode != 0:
               return f"Error: {stderr}"

           return stdout
       except Exception as e:
           return f"Error: {str(e)}"
   ```

2. **Register the tool in server.py using FastMCP decorator:**
   ```python
   # Import your tool module at the top
   from .tools import my_tool

   # Add decorated function
   @mcp.tool()
   async def my_tool_name(
       param1: str,
       host: Optional[str] = None,
       username: Optional[str] = None
   ) -> str:
       """Description for LLM to understand the tool.

       Args:
           param1: Description of the parameter
           host: Remote host to connect to via SSH (optional)
           username: SSH username for remote host (required if host is provided)
       """
       return await _execute_tool(
           "my_tool_name",
           my_tool.my_diagnostic_function,
           param1=param1,
           host=host,
           username=username
       )
   ```

3. **Write tests:**
   ```python
   # tests/test_my_tool.py
   import pytest
   from linux_mcp_server.tools import my_tool

   @pytest.mark.asyncio
   async def test_my_tool():
       result = await my_tool.my_diagnostic_function()
       assert isinstance(result, str)
       assert "expected content" in result.lower()

   # Test server integration
   @pytest.mark.asyncio
   async def test_server_has_my_tool():
       from linux_mcp_server.server import mcp
       tools = await mcp.list_tools()
       tool_names = [t.name for t in tools]
       assert "my_tool_name" in tool_names
   ```

4. **Update documentation:**
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
@pytest.mark.asyncio
async def test_function_returns_correct_format():
    result = await module.function()
    assert isinstance(result, str)
    assert "expected" in result
```

### Integration Tests
Test that tools work with the MCP server:
```python
@pytest.mark.asyncio
async def test_server_has_tool():
    from linux_mcp_server.server import mcp
    tools = await mcp.list_tools()
    tool_names = [t.name for t in tools]
    assert "tool_name" in tool_names

@pytest.mark.asyncio
async def test_server_calls_tool():
    from linux_mcp_server.server import mcp
    result = await mcp.call_tool("tool_name", {})
    assert isinstance(result, str)
```

### Running Tests
```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_services.py

# Run with coverage
pytest --cov=src --cov-report=html

# Run with verbose output
pytest -v
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

By contributing, you agree that your contributions will be licensed under the MIT License.

