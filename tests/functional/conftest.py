# Copyright Red Hat
import asyncio
import contextlib
import os

import pytest
import pytest_asyncio
import yaml
from mcp import StdioServerParameters
from mcp.client.session import ClientSession as MCPClientSession
from mcp.client.stdio import stdio_client
from utils.shell import shell

# --- Default configuration ---
SERVER_COMMAND = "linux-mcp-server"
SERVER_ARGS = []
DEFAULT_SERVER_ENV = {"LINUX_MCP_LOG_LEVEL": "DEBUG"}


@contextlib.asynccontextmanager
async def mcp_server_lifecycle(env_overrides=None):
    """
    Starts the MCP server in a dedicated background task to maintain
    Task identity for 'anyio' context managers.
    """
    # Merge default env with overrides
    current_env = DEFAULT_SERVER_ENV.copy()
    if env_overrides:
        current_env.update(env_overrides)

    server_params = StdioServerParameters(
        command=SERVER_COMMAND, args=SERVER_ARGS, env=current_env
    )

    print("\n--- [SESSION START] MCP Server ---")

    # 1. Mechanism to pass the session object back to the main test thread
    session_future = asyncio.Future()
    # 2. Mechanism to signal the background task to shut down
    shutdown_event = asyncio.Event()

    async def run_server_inner():
        """
        This function runs in a SINGLE persistent Task.
        It handles both opening and closing the connection.
        """
        try:
            async with stdio_client(server_params) as (reader, writer):
                async with MCPClientSession(reader, writer) as session:
                    # Initialize
                    capabilities = await session.initialize()

                    print(f"MCP Server Name: **{capabilities.serverInfo.name}**")
                    print(
                        f"\nServer started with these environment variables:\n{current_env}"
                    )

                    # Pass the active session to the fixture
                    session_future.set_result(session)

                    # WAIT here until the tests are done
                    await shutdown_event.wait()

                    # When shutdown_event is set, this block exits naturally,
                    # triggering the __aexit__ logic within THIS SAME TASK.
        except Exception as e:
            # If something goes wrong during startup, let the fixture know
            if not session_future.done():
                session_future.set_exception(e)
            raise

    # 3. Start the server lifecycle in a background task
    server_task = asyncio.create_task(run_server_inner())

    try:
        # 4. Wait for the session to be ready
        session = await session_future

        yield session
    finally:
        print("\n--- [SESSION END] Stopping Server ---")
        # 5. Teardown: Signal the background task to exit
        shutdown_event.set()
        try:
            await server_task
        except asyncio.CancelledError:
            pass


@pytest.fixture(autouse=True)
def auto_log_test_boundaries(request):
    # Print the test name before each test
    test_name = request.node.name
    print(f"\n\n=== [START] Executing '{test_name}' ===")

    yield  # The test runs here

    # Teardown: Runs after the test (only if it didn't crash)
    # Note: If an assertion fails, pytest handles the error log,
    # but the below line will be printed anyway.
    print(f"=== [END] Finished '{test_name}' ===\n")


# 1. Define a Wrapper Class for logging the MCP session calls
class LoggingMCPSession:
    def __init__(self, original_session):
        self._session = original_session

    async def call_tool(self, name, arguments=None):
        print(f"\n--- [AUTO-LOG] Calling tool: '{name}' with args: {arguments}")

        # Call the actual method
        response = await self._session.call_tool(name, arguments)

        # Log the result automatically
        text_content = response.content[0].text if response.content else "No content"
        print(f"--- [AUTO-LOG] Server returned answer:\n{text_content}")

        return response

    # Delegate all other attributes to the original session
    def __getattr__(self, name):
        return getattr(self._session, name)


# Wrap the MCP session to a fixture with logging enabled
# scope="session" to have the MCP session enabled for all the tests with the same environment variables
@pytest_asyncio.fixture(scope="session")
async def mcp_session(request):
    # 1. Capture the parameters from the test
    # If no param is passed (non-parametrized test), default to None
    params = getattr(request, "param", None)

    # 2. Create the actual session using the helper
    async with mcp_server_lifecycle(env_overrides=params) as raw_session:
        # 3. Wrap it immediately
        logging_session = LoggingMCPSession(raw_session)

        # 4. Yield the wrapper to the test
        yield logging_session


@pytest.fixture(scope="session")
def client_hostname():
    """
    This is for multihost execution. Returns the client hostname.
    """
    if (
        os.getenv("MCP_TESTS_MULTIHOST")
        and os.getenv("MCP_TESTS_MULTIHOST").lower() == "true"
    ):
        path = shell("realpath $TMT_TOPOLOGY_YAML", silent=True).stdout.strip()
        with open(path, "r") as f:
            data = yaml.full_load(f)

        hostname = data["guests"]["client"]["hostname"]

        return hostname
    return None
