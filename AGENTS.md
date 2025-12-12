# Linux MCP Server

## Development Guidelines

- Always run tests, linters, and type checkers before committing code with `make verify`.
- Extend existing tests using parameterized tests rather than adding new test cases.
- Use fixtures to deduplicate setup code across tests.
- If a fixture could be used in multiple test modules, place it in `conftest.py`.
- Use mocks sparingly and try to pass objects to the code under test instead.
