# Linux MCP Server

## Development Guidelines

- Always run tests, linters, and type checkers before committing code with `make verify`.
- Extend existing tests using parameterized tests rather than adding new test cases.
- Use fixtures to deduplicate setup code across tests.
- If a fixture could be used in multiple test modules, place it in `conftest.py`.
- Use mocks sparingly and try to pass objects to the code under test instead.
- Use `autospec=True` when patching to verify arguments match the real function signature.
- Use `spec=<object>` with MagicMock to restrict attributes to those of the real object.
- Prefer Pydantic models over dataclasses.
