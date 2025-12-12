"""Ansible executor for remote command execution.

This module provides functionality to execute Ansible modules on remote systems,
offering structured output and distribution abstraction as an alternative to raw
SSH commands.
"""

import asyncio
import atexit
import logging
import os
import tempfile

from concurrent.futures import ThreadPoolExecutor
from typing import Any

import ansible_runner

from linux_mcp_server.config import CONFIG
from linux_mcp_server.connection.ssh import discover_ssh_key


logger = logging.getLogger("linux-mcp-server")


class AnsibleExecutionError(Exception):
    """Raised when Ansible module execution fails."""


class AnsibleExecutor:
    """Execute Ansible modules asynchronously with connection pooling.

    This class wraps ansible-runner to provide async execution of Ansible modules
    while maintaining compatibility with the FastMCP async event loop. It uses a
    thread pool to run synchronous ansible-runner operations without blocking.

    Features:
    - Automatic SSH connection pooling via Ansible's ControlPersist
    - Structured JSON output from Ansible modules (no text parsing)
    - Distribution abstraction (RHEL/Fedora/CentOS handled automatically)
    - Comprehensive error handling with audit logging

    Example:
        executor = AnsibleExecutor()
        result = await executor.run_module(
            module="setup",
            module_args={"gather_subset": ["!all", "!min", "devices"]},
            host="server.example.com",
            username="admin"
        )
        devices = result["ansible_facts"]["ansible_devices"]
    """

    def __init__(self, max_workers: int = 4):
        """Initialize Ansible executor with thread pool.

        Args:
            max_workers: Number of threads for concurrent Ansible executions
        """
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._ssh_key = discover_ssh_key()
        self._shutdown = False
        atexit.register(self.shutdown)
        logger.debug(
            f"AnsibleExecutor initialized | workers={max_workers} | key={'<configured>' if self._ssh_key else 'none'}"
        )

    @staticmethod
    def _format_module_args(module_args: dict[str, Any] | str | None) -> str:
        """Convert module arguments to Ansible string format.

        ansible-runner expects module_args as a string in key=value format.
        This method converts dict arguments to the appropriate string format.

        Args:
            module_args: Dict, string, or None

        Returns:
            String in Ansible key=value format
        """
        if module_args is None:
            return ""
        if isinstance(module_args, str):
            return module_args

        parts = []
        for key, value in module_args.items():
            if isinstance(value, list):
                # Convert list to comma-separated string
                formatted_value = ",".join(str(v) for v in value)
            elif isinstance(value, bool):
                formatted_value = str(value).lower()
            else:
                formatted_value = str(value)
            parts.append(f"{key}='{formatted_value}'")

        return " ".join(parts)

    async def run_module(
        self,
        module: str,
        module_args: dict[str, Any] | str | None = None,
        host: str = "localhost",
        username: str = CONFIG.user,
        timeout: int = CONFIG.command_timeout,
    ) -> dict[str, Any]:
        """Execute an Ansible module on a remote host.

        Args:
            module: Ansible module name (e.g., "setup", "command", "systemd")
            module_args: Module arguments as dict or string
            host: Target host address
            username: SSH username
            timeout: Execution timeout in seconds

        Returns:
            Module result as dictionary (structured Ansible output)

        Raises:
            AnsibleExecutionError: If Ansible execution fails or host unreachable
            TimeoutError: If execution exceeds timeout

        Example:
            # Get systemd service facts
            result = await executor.run_module(
                module="service_facts",
                host="server.example.com"
            )
            services = result["ansible_facts"]["services"]
        """
        loop = asyncio.get_running_loop()

        logger.debug(f"ANSIBLE_EXEC: {module} | host={host} | args={module_args}")

        try:
            result = await asyncio.wait_for(
                loop.run_in_executor(
                    self._executor,
                    self._run_ansible_module,
                    module,
                    module_args,
                    host,
                    username,
                ),
                timeout=timeout,
            )

            logger.debug(f"ANSIBLE_OK: {module} | host={host}")
            return result

        except asyncio.TimeoutError:
            error_msg = f"Ansible module '{module}' timed out after {timeout}s on {host}"
            logger.error(error_msg)
            raise TimeoutError(error_msg) from None
        except AnsibleExecutionError:
            raise
        except Exception as e:
            logger.error(f"Ansible execution failed: {e}", extra={"ansible_module": module, "host": host})
            raise AnsibleExecutionError(f"Failed to execute Ansible module '{module}' on {host}: {e}") from e

    def _run_ansible_module(
        self,
        module: str,
        module_args: dict[str, Any] | str | None,
        host: str,
        username: str,
    ) -> dict[str, Any]:
        """Synchronous Ansible execution (runs in thread pool).

        This method runs in a separate thread to avoid blocking the async event loop.
        It uses ansible-runner to execute a single module on a single host.

        Args:
            module: Ansible module name
            module_args: Module arguments
            host: Target host
            username: SSH username

        Returns:
            Ansible module result dictionary

        Raises:
            AnsibleExecutionError: If execution fails or host unreachable
        """
        # Create temporary directory for ansible-runner artifacts
        with tempfile.TemporaryDirectory(prefix="ansible-mcp-") as tmpdir:
            # Harden permissions - Ansible writes sensitive data here
            os.chmod(tmpdir, 0o700)

            extravars = {
                "ansible_user": username,
                "ansible_host_key_checking": str(CONFIG.verify_host_keys).lower(),
                # Enable SSH connection multiplexing for performance
                "ansible_ssh_common_args": "-o ControlMaster=auto -o ControlPersist=60s",
            }

            # Add SSH key if available
            if self._ssh_key:
                extravars["ansible_ssh_private_key_file"] = self._ssh_key

            # Convert dict args to string format for ansible-runner
            args_str = self._format_module_args(module_args)

            # Execute Ansible module
            runner = ansible_runner.run(
                private_data_dir=tmpdir,
                host_pattern=host,
                module=module,
                module_args=args_str,
                extravars=extravars,
                quiet=True,
                json_mode=True,
            )

            # Check execution status
            # ansible_runner.run() returns Runner type, but pyright sees union types without proper stubs
            if runner.status == "failed":
                raise AnsibleExecutionError(
                    f"Ansible execution failed on {host}: {runner.stats.get('failures', {})}"  # pyright: ignore[reportOptionalMemberAccess,reportAttributeAccessIssue]
                )

            if runner.status == "unreachable":
                raise AnsibleExecutionError(f"Host unreachable: {host}")

            # Extract module result from events
            for event in runner.events:  # pyright: ignore[reportAttributeAccessIssue]
                if event.get("event") == "runner_on_ok":
                    return event["event_data"]["res"]

            # No result found in events
            raise AnsibleExecutionError(f"No result returned from Ansible module '{module}' on {host}")

    def shutdown(self) -> None:
        """Shutdown thread pool executor.

        Safe to call multiple times - subsequent calls are no-ops.
        Automatically registered with atexit for cleanup on interpreter exit.
        """
        if self._shutdown:
            return
        self._shutdown = True
        logger.debug("Shutting down Ansible executor")
        self._executor.shutdown(wait=True)


# Global executor instance (lazy initialization)
_ansible_executor: AnsibleExecutor | None = None


def get_ansible_executor() -> AnsibleExecutor:
    """Get or create the global Ansible executor instance."""
    global _ansible_executor

    if _ansible_executor is None:
        _ansible_executor = AnsibleExecutor()

    return _ansible_executor


async def execute_ansible_module(
    module: str,
    module_args: dict[str, Any] | str | None = None,
    host: str | None = None,
    username: str = CONFIG.user,
) -> dict[str, Any]:
    """Execute an Ansible module (main entry point).

    This is the primary interface for tools to execute Ansible modules. It manages
    a singleton AnsibleExecutor instance and provides a simplified API.

    Args:
        module: Ansible module name
        module_args: Module arguments
        host: Optional remote host (None = localhost)
        username: SSH username for remote connections

    Returns:
        Module result dictionary

    Raises:
        AnsibleExecutionError: If Ansible execution fails
        TimeoutError: If execution times out

    Example:
        # Get block device information using setup module
        result = await execute_ansible_module(
            module="setup",
            module_args={"gather_subset": ["!all", "!min", "devices"]},
            host="server.example.com"
        )
        devices = result["ansible_facts"]["ansible_devices"]
    """
    executor = get_ansible_executor()

    target_host = host or "localhost"
    return await executor.run_module(
        module=module,
        module_args=module_args,
        host=target_host,
        username=username,
    )
