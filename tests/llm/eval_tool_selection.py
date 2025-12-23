# SPDX-License-Identifier: Apache-2.0
"""LLM evaluation for tool selection accuracy.

Tests whether the LLM correctly selects the appropriate tool from the
Linux MCP Server based on natural language prompts.

Run locally:
    uv run --group llm-eval inspect eval tests/llm/eval_tool_selection.py \
        --model google/vertex/gemini-2.5-flash
"""

import os

from inspect_ai import Task
from inspect_ai import task
from inspect_ai.dataset import Sample
from inspect_ai.scorer import accuracy
from inspect_ai.scorer import Score
from inspect_ai.scorer import scorer
from inspect_ai.scorer import Target
from inspect_ai.solver import generate
from inspect_ai.solver import system_message
from inspect_ai.solver import TaskState
from inspect_ai.solver import use_tools
from inspect_ai.tool import mcp_server_stdio


def get_mcp_server():
    """Create MCP server instance with environment configuration.

    Passes through LINUX_MCP_LOG_LEVEL from the environment to control
    server logging verbosity during evaluation runs.
    """
    env = {}
    if log_level := os.environ.get("LINUX_MCP_LOG_LEVEL"):
        env["LINUX_MCP_LOG_LEVEL"] = log_level
    return mcp_server_stdio(
        name="linux-mcp-server",
        command="linux-mcp-server",
        env=env or None,
    )


# System prompt guiding the LLM on Linux system administration tool selection
SYSTEM_PROMPT = """You are a Linux system administration assistant. Your role is to \
help users query and monitor Linux systems using the available MCP tools.

CORE PRINCIPLES:
1. Select the most specific tool for each request
2. Use appropriate parameters when the request specifies details
3. Prefer targeted queries over broad ones for efficiency
4. This is a READ-ONLY server - you cannot modify system state

TOOL SELECTION GUIDELINES:
- System basics (OS, kernel, uptime, boot time) → get_system_information
- CPU details (cores, model, frequency) → get_cpu_information
- Memory/RAM/swap usage → get_memory_information
- Disk space and mount points → get_disk_usage
- Hardware (PCI, USB, DMI/manufacturer) → get_hardware_information
- Running processes → list_processes or get_process_info (with PID)
- Systemd services → list_services or get_service_status (with name)
- Service logs → get_service_logs (for specific service)
- System journal logs → get_journal_logs (with optional unit/priority/since filters)
- Audit logs → get_audit_logs
- Read a specific file → read_file or read_log_file (for log files)
- Directory contents → list_directories or list_files
- Block devices → list_block_devices
- Network interfaces → get_network_interfaces
- Open connections → get_network_connections
- Listening ports → get_listening_ports

UNSUPPORTED OPERATIONS (no tools available - do NOT call any tool):
- Write operations: creating/modifying/deleting files, killing processes
- Service control: starting, stopping, restarting, enabling services
- Package management: installing, removing, updating packages
- User management: creating users, changing passwords, managing groups
- Firewall/network config: iptables, firewalld rules, IP configuration
- Container management: docker, podman operations
- System changes: rebooting, shutting down, changing settings

REMOTE SYSTEMS:
- All tools support a 'host' parameter for remote execution via SSH
- When the user mentions a specific hostname, use the host parameter

RESPONSE INSTRUCTIONS:
1. If the request matches an available tool, call it with appropriate parameters
2. If the request requires an unsupported operation, explain that you cannot \
perform write/modify operations - do NOT call any tool
3. Do not explain what you would do - actually call the tool OR decline

IMPORTANT: Only call tools for supported read-only operations. For unsupported \
operations, respond with text explaining the limitation."""


# Special target indicating no tool should be called (for negative tests)
NO_TOOL_EXPECTED = "<no_tool>"


def _get_first_tool_call(state: TaskState) -> tuple[str | None, dict | None]:
    """Extract first tool call and its arguments from conversation state."""
    for msg in state.messages:
        if msg.role == "assistant" and msg.tool_calls:
            tool_call = msg.tool_calls[0]
            return tool_call.function, tool_call.arguments
    return None, None


def _format_answer(tool: str | None, args: dict | None) -> str:
    """Format tool call as answer string for scoring output."""
    if tool is None:
        return "<no tool called>"
    if args:
        params = ", ".join(f"{k}={v!r}" for k, v in sorted(args.items()))
        return f"{tool}({params})"
    return tool


@scorer(metrics=[accuracy()])
def tool_selection_scorer():
    """Score whether the model selected the expected tool.

    Scoring for positive tests (target is a tool name):
    - 1.0: Correct tool called
    - 0.0: Wrong tool or no tool called

    Scoring for negative tests (target is "<no_tool>"):
    - 1.0: No tool called (correct - LLM recognized unsupported request)
    - 0.0: Any tool called (incorrect - LLM hallucinated a capability)
    """

    async def score(state: TaskState, target: Target) -> Score:
        expected_tool = target.text
        tool_called, args = _get_first_tool_call(state)
        answer = _format_answer(tool_called, args)

        # Negative test: expect NO tool to be called
        if expected_tool == NO_TOOL_EXPECTED:
            if tool_called is None:
                return Score(value=1.0, answer=answer)
            return Score(value=0.0, answer=answer)

        # Positive test: expect specific tool to be called
        if tool_called == expected_tool:
            return Score(value=1.0, answer=answer)
        return Score(value=0.0, answer=answer)

    return score


@scorer(metrics=[accuracy()])
def tool_and_params_scorer():
    """Score whether model selected correct tool WITH correct parameters.

    Uses 'expected_params' from sample metadata to validate arguments.
    Only checks parameters specified in expected_params (allows extra params).

    Scoring:
    - 1.0: Correct tool AND all expected parameters match
    - 0.0: Wrong tool, missing params, or incorrect param values
    """

    async def score(state: TaskState, target: Target) -> Score:
        expected_tool = target.text
        expected_params = state.metadata.get("expected_params", {})
        tool_called, actual_args = _get_first_tool_call(state)
        answer = _format_answer(tool_called, actual_args)

        # Check tool selection first
        if tool_called != expected_tool:
            return Score(
                value=0.0,
                answer=answer,
                explanation=f"Expected tool '{expected_tool}', got '{tool_called}'",
            )

        # If no params expected, tool match is sufficient
        if not expected_params:
            return Score(value=1.0, answer=answer)

        # Validate expected parameters
        actual_args = actual_args or {}
        missing_params = []
        wrong_params = []

        for param, expected_value in expected_params.items():
            if param not in actual_args:
                missing_params.append(param)
            elif actual_args[param] != expected_value:
                wrong_params.append(f"{param}: expected {expected_value!r}, got {actual_args[param]!r}")

        if missing_params or wrong_params:
            issues = []
            if missing_params:
                issues.append(f"missing: {missing_params}")
            if wrong_params:
                issues.append(f"wrong: {wrong_params}")
            return Score(
                value=0.0,
                answer=answer,
                explanation="; ".join(issues),
            )

        return Score(value=1.0, answer=answer)

    return score


# -----------------------------------------------------------------------------
# Test samples organized by tool category
# -----------------------------------------------------------------------------

# System information tools
SYSTEM_INFO_SAMPLES = [
    # get_system_information - OS, distribution, kernel, uptime, boot time
    Sample(
        input="Show me the system uptime and basic OS information",
        target="get_system_information",
    ),
    Sample(
        input="What Linux distribution and kernel version is this system running?",
        target="get_system_information",
    ),
    Sample(
        input="When was this server last rebooted?",
        target="get_system_information",
    ),
    # get_cpu_information - CPU details
    Sample(
        input="How many CPU cores does this machine have?",
        target="get_cpu_information",
    ),
    Sample(
        input="What processor model is installed in this system?",
        target="get_cpu_information",
    ),
    # get_memory_information - RAM and swap
    Sample(
        input="How much RAM is installed and how much is currently free?",
        target="get_memory_information",
    ),
    Sample(
        input="Show me the memory usage including swap",
        target="get_memory_information",
    ),
    # get_disk_usage - disk space and mount points
    Sample(
        input="How much disk space is available on this system?",
        target="get_disk_usage",
    ),
    Sample(
        input="Which filesystems are mounted and what's their utilization?",
        target="get_disk_usage",
    ),
    # get_hardware_information - PCI, USB, DMI
    Sample(
        input="What PCI devices are installed in this server?",
        target="get_hardware_information",
    ),
    Sample(
        input="Show me the USB devices connected to this machine",
        target="get_hardware_information",
    ),
    Sample(
        input="What's the hardware manufacturer and model of this system?",
        target="get_hardware_information",
    ),
]

# Process and service tools
PROCESS_SERVICE_SAMPLES = [
    # list_processes
    Sample(
        input="What processes are currently running on this system?",
        target="list_processes",
    ),
    Sample(
        input="Show me all running processes",
        target="list_processes",
    ),
    # get_process_info
    Sample(
        input="Get details about the process with PID 1",
        target="get_process_info",
        metadata={"expected_params": {"pid": 1}},
    ),
    # list_services
    Sample(
        input="List all systemd services on this machine",
        target="list_services",
    ),
    Sample(
        input="What services are configured on this system?",
        target="list_services",
    ),
    # get_service_status
    Sample(
        input="Is the sshd service running?",
        target="get_service_status",
        metadata={"expected_params": {"service_name": "sshd"}},
    ),
    Sample(
        input="Check the status of the nginx service",
        target="get_service_status",
        metadata={"expected_params": {"service_name": "nginx"}},
    ),
    # get_service_logs
    Sample(
        input="Show me recent logs from the docker service",
        target="get_service_logs",
        metadata={"expected_params": {"service_name": "docker"}},
    ),
]

# Log tools
LOG_SAMPLES = [
    # get_journal_logs
    Sample(
        input="Show me the latest system journal entries",
        target="get_journal_logs",
    ),
    Sample(
        input="What errors have been logged in the journal recently?",
        target="get_journal_logs",
        metadata={"expected_params": {"priority": "err"}},
    ),
    Sample(
        input="Show SSH daemon logs from the journal",
        target="get_journal_logs",
        metadata={"expected_params": {"unit": "sshd"}},
    ),
    # get_audit_logs
    Sample(
        input="Show me the system audit logs",
        target="get_audit_logs",
    ),
    Sample(
        input="What's in the audit trail?",
        target="get_audit_logs",
    ),
    # read_log_file
    Sample(
        input="Read the contents of /var/log/messages",
        target="read_log_file",
        metadata={"expected_params": {"log_path": "/var/log/messages"}},
    ),
]

# Storage and file tools
STORAGE_SAMPLES = [
    # list_block_devices
    Sample(
        input="What block devices are available on this system?",
        target="list_block_devices",
    ),
    Sample(
        input="Show me the disks and partitions",
        target="list_block_devices",
    ),
    # list_directories
    Sample(
        input="What directories are in /etc?",
        target="list_directories",
        metadata={"expected_params": {"path": "/etc"}},
    ),
    Sample(
        input="Show me the largest directories in /var sorted by size",
        target="list_directories",
        metadata={"expected_params": {"path": "/var", "order_by": "size"}},
    ),
    # list_files
    Sample(
        input="List files in /tmp",
        target="list_files",
        metadata={"expected_params": {"path": "/tmp"}},
    ),
    Sample(
        input="What are the biggest files in /var/log?",
        target="list_files",
        metadata={"expected_params": {"path": "/var/log", "order_by": "size"}},
    ),
    # read_file
    Sample(
        input="Show me the contents of /etc/hostname",
        target="read_file",
        metadata={"expected_params": {"path": "/etc/hostname"}},
    ),
    Sample(
        input="Read the /etc/os-release file",
        target="read_file",
        metadata={"expected_params": {"path": "/etc/os-release"}},
    ),
]

# Network tools
NETWORK_SAMPLES = [
    # get_network_interfaces
    Sample(
        input="Show me the network interfaces on this system",
        target="get_network_interfaces",
    ),
    Sample(
        input="What IP addresses are configured?",
        target="get_network_interfaces",
    ),
    # get_network_connections
    Sample(
        input="What network connections are currently active?",
        target="get_network_connections",
    ),
    Sample(
        input="Show established TCP connections",
        target="get_network_connections",
    ),
    # get_listening_ports
    Sample(
        input="What ports are listening on this server?",
        target="get_listening_ports",
    ),
    Sample(
        input="Which services are listening for connections?",
        target="get_listening_ports",
    ),
]

# Remote host samples (tests host parameter usage)
REMOTE_HOST_SAMPLES = [
    Sample(
        input="Check disk usage on webserver.example.com",
        target="get_disk_usage",
        metadata={"expected_params": {"host": "webserver.example.com"}},
    ),
    Sample(
        input="List processes running on db01",
        target="list_processes",
        metadata={"expected_params": {"host": "db01"}},
    ),
    Sample(
        input="Show memory info for the host called backup-server",
        target="get_memory_information",
        metadata={"expected_params": {"host": "backup-server"}},
    ),
]

# Negative test samples - requests for unsupported operations
# The LLM should NOT call any tool for these requests
NEGATIVE_SAMPLES = [
    # Write operations
    Sample(
        input="Create a new file called /tmp/test.txt with the contents 'hello world'",
        target=NO_TOOL_EXPECTED,
        metadata={"category": "write_operation"},
    ),
    Sample(
        input="Delete the file /var/log/old.log",
        target=NO_TOOL_EXPECTED,
        metadata={"category": "write_operation"},
    ),
    Sample(
        input="Append a line to /etc/hosts",
        target=NO_TOOL_EXPECTED,
        metadata={"category": "write_operation"},
    ),
    # Process control
    Sample(
        input="Kill the process with PID 1234",
        target=NO_TOOL_EXPECTED,
        metadata={"category": "process_control"},
    ),
    Sample(
        input="Send SIGTERM to all python processes",
        target=NO_TOOL_EXPECTED,
        metadata={"category": "process_control"},
    ),
    # Service control
    Sample(
        input="Restart the nginx service",
        target=NO_TOOL_EXPECTED,
        metadata={"category": "service_control"},
    ),
    Sample(
        input="Stop the docker service",
        target=NO_TOOL_EXPECTED,
        metadata={"category": "service_control"},
    ),
    Sample(
        input="Enable sshd to start at boot",
        target=NO_TOOL_EXPECTED,
        metadata={"category": "service_control"},
    ),
    # Package management
    Sample(
        input="Install the htop package",
        target=NO_TOOL_EXPECTED,
        metadata={"category": "package_management"},
    ),
    Sample(
        input="Update all system packages",
        target=NO_TOOL_EXPECTED,
        metadata={"category": "package_management"},
    ),
    Sample(
        input="Remove the vim package from the system",
        target=NO_TOOL_EXPECTED,
        metadata={"category": "package_management"},
    ),
    # User management
    Sample(
        input="Create a new user called testuser",
        target=NO_TOOL_EXPECTED,
        metadata={"category": "user_management"},
    ),
    Sample(
        input="Change the password for the admin user",
        target=NO_TOOL_EXPECTED,
        metadata={"category": "user_management"},
    ),
    Sample(
        input="Add user john to the sudo group",
        target=NO_TOOL_EXPECTED,
        metadata={"category": "user_management"},
    ),
    # Firewall/network configuration
    Sample(
        input="Open port 8080 in the firewall",
        target=NO_TOOL_EXPECTED,
        metadata={"category": "firewall_config"},
    ),
    Sample(
        input="Block incoming traffic from 10.0.0.0/8",
        target=NO_TOOL_EXPECTED,
        metadata={"category": "firewall_config"},
    ),
    Sample(
        input="Change the IP address of eth0 to 192.168.1.100",
        target=NO_TOOL_EXPECTED,
        metadata={"category": "network_config"},
    ),
    # System control
    Sample(
        input="Reboot the system",
        target=NO_TOOL_EXPECTED,
        metadata={"category": "system_control"},
    ),
    Sample(
        input="Shut down the server",
        target=NO_TOOL_EXPECTED,
        metadata={"category": "system_control"},
    ),
    # Container management
    Sample(
        input="Start a new docker container running nginx",
        target=NO_TOOL_EXPECTED,
        metadata={"category": "container_management"},
    ),
    Sample(
        input="Stop all running containers",
        target=NO_TOOL_EXPECTED,
        metadata={"category": "container_management"},
    ),
]

# Parameter validation samples - tests that LLM passes correct arguments
# These samples have strict expected_params that must match exactly
PARAMETER_SAMPLES = [
    # list_directories with path
    Sample(
        input="List the directories in /etc",
        target="list_directories",
        metadata={"expected_params": {"path": "/etc"}},
    ),
    Sample(
        input="What directories are under /var/log?",
        target="list_directories",
        metadata={"expected_params": {"path": "/var/log"}},
    ),
    Sample(
        input="Show directories in /home sorted by size, largest first",
        target="list_directories",
        metadata={"expected_params": {"path": "/home", "order_by": "size", "sort": "descending"}},
    ),
    Sample(
        input="List the 5 biggest directories in /usr",
        target="list_directories",
        metadata={"expected_params": {"path": "/usr", "order_by": "size", "top_n": 5}},
    ),
    # list_files with path and sorting
    Sample(
        input="List files in /tmp",
        target="list_files",
        metadata={"expected_params": {"path": "/tmp"}},
    ),
    Sample(
        input="Show me the 10 largest files in /var/log",
        target="list_files",
        metadata={"expected_params": {"path": "/var/log", "order_by": "size", "top_n": 10}},
    ),
    Sample(
        input="What files were most recently modified in /etc?",
        target="list_files",
        metadata={"expected_params": {"path": "/etc", "order_by": "modified", "sort": "descending"}},
    ),
    # read_file with path
    Sample(
        input="Show me the contents of /etc/passwd",
        target="read_file",
        metadata={"expected_params": {"path": "/etc/passwd"}},
    ),
    Sample(
        input="Read /proc/meminfo",
        target="read_file",
        metadata={"expected_params": {"path": "/proc/meminfo"}},
    ),
    # read_log_file with path and lines
    Sample(
        input="Show the last 50 lines of /var/log/messages",
        target="read_log_file",
        metadata={"expected_params": {"log_path": "/var/log/messages", "lines": 50}},
    ),
    Sample(
        input="Read the last 200 lines from /var/log/secure",
        target="read_log_file",
        metadata={"expected_params": {"log_path": "/var/log/secure", "lines": 200}},
    ),
    # get_process_info with pid
    Sample(
        input="Get information about process 1",
        target="get_process_info",
        metadata={"expected_params": {"pid": 1}},
    ),
    Sample(
        input="Show details for PID 4567",
        target="get_process_info",
        metadata={"expected_params": {"pid": 4567}},
    ),
    # get_service_status with service_name
    Sample(
        input="What's the status of the crond service?",
        target="get_service_status",
        metadata={"expected_params": {"service_name": "crond"}},
    ),
    Sample(
        input="Is postgresql running?",
        target="get_service_status",
        metadata={"expected_params": {"service_name": "postgresql"}},
    ),
    # get_service_logs with service_name and lines
    Sample(
        input="Show me the last 100 log entries for sshd",
        target="get_service_logs",
        metadata={"expected_params": {"service_name": "sshd", "lines": 100}},
    ),
    Sample(
        input="Get 50 lines of logs from the httpd service",
        target="get_service_logs",
        metadata={"expected_params": {"service_name": "httpd", "lines": 50}},
    ),
    # get_journal_logs with filters
    Sample(
        input="Show journal entries with error priority",
        target="get_journal_logs",
        metadata={"expected_params": {"priority": "err"}},
    ),
    Sample(
        input="Get 500 lines from the system journal",
        target="get_journal_logs",
        metadata={"expected_params": {"lines": 500}},
    ),
    Sample(
        input="Show warning-level journal messages from the last hour",
        target="get_journal_logs",
        metadata={"expected_params": {"priority": "warning", "since": "1 hour ago"}},
    ),
    # Remote host parameter
    Sample(
        input="List files in /opt on server1.example.com",
        target="list_files",
        metadata={"expected_params": {"path": "/opt", "host": "server1.example.com"}},
    ),
    Sample(
        input="Read /etc/hostname from the host named webserver",
        target="read_file",
        metadata={"expected_params": {"path": "/etc/hostname", "host": "webserver"}},
    ),
    Sample(
        input="Get process info for PID 100 on db-primary",
        target="get_process_info",
        metadata={"expected_params": {"pid": 100, "host": "db-primary"}},
    ),
]

# Combined dataset for full evaluation
ALL_SAMPLES = (
    SYSTEM_INFO_SAMPLES
    + PROCESS_SERVICE_SAMPLES
    + LOG_SAMPLES
    + STORAGE_SAMPLES
    + NETWORK_SAMPLES
    + REMOTE_HOST_SAMPLES
)

# Combined dataset including negative tests
ALL_SAMPLES_WITH_NEGATIVE = ALL_SAMPLES + NEGATIVE_SAMPLES


@task
def tool_selection_eval():
    """Evaluate LLM tool selection accuracy with Linux MCP Server.

    Full evaluation across all tool categories:
    - System information (OS, CPU, memory, disk, hardware)
    - Processes and services
    - Logs (journal, audit, file)
    - Storage (block devices, directories, files)
    - Network (interfaces, connections, ports)
    - Remote host execution
    """
    mcp_server = get_mcp_server()

    return Task(
        dataset=ALL_SAMPLES,
        solver=[
            system_message(SYSTEM_PROMPT),
            use_tools(mcp_server),
            generate(),
        ],
        scorer=tool_selection_scorer(),
    )


@task
def tool_selection_system_info():
    """Focused evaluation on system information tools only.

    Lighter-weight test covering:
    - get_system_information
    - get_cpu_information
    - get_memory_information
    - get_disk_usage
    - get_hardware_information
    """
    mcp_server = get_mcp_server()

    return Task(
        dataset=SYSTEM_INFO_SAMPLES,
        solver=[
            system_message(SYSTEM_PROMPT),
            use_tools(mcp_server),
            generate(),
        ],
        scorer=tool_selection_scorer(),
    )


@task
def tool_selection_negative():
    """Evaluate LLM's ability to decline unsupported operations.

    Tests that the LLM correctly recognizes requests outside our capabilities
    and does NOT call any tool. Categories tested:
    - Write operations (create/modify/delete files)
    - Process control (kill, signal)
    - Service control (start/stop/restart)
    - Package management (install/remove/update)
    - User management (create users, change passwords)
    - Firewall/network configuration
    - System control (reboot, shutdown)
    - Container management (docker, podman)

    Success criteria: LLM responds with text explaining the limitation
    instead of calling an inappropriate tool.
    """
    mcp_server = get_mcp_server()

    return Task(
        dataset=NEGATIVE_SAMPLES,
        solver=[
            system_message(SYSTEM_PROMPT),
            use_tools(mcp_server),
            generate(),
        ],
        scorer=tool_selection_scorer(),
    )


@task
def tool_selection_full():
    """Full evaluation including both positive and negative tests.

    Comprehensive test covering:
    - All tool categories (positive tests)
    - Unsupported operation recognition (negative tests)

    Use this for complete evaluation of tool selection behavior.
    """
    mcp_server = get_mcp_server()

    return Task(
        dataset=ALL_SAMPLES_WITH_NEGATIVE,
        solver=[
            system_message(SYSTEM_PROMPT),
            use_tools(mcp_server),
            generate(),
        ],
        scorer=tool_selection_scorer(),
    )


@task
def tool_selection_params():
    """Evaluate LLM's ability to pass correct parameters to tools.

    Tests parameter extraction and formatting for tools that accept arguments:
    - list_directories: path, order_by, sort, top_n
    - list_files: path, order_by, sort, top_n
    - read_file: path
    - read_log_file: log_path, lines
    - get_process_info: pid
    - get_service_status: service_name
    - get_service_logs: service_name, lines
    - get_journal_logs: lines, priority, since, unit
    - Remote host parameter across multiple tools

    Scoring is strict: both tool selection AND parameter values must match.
    """
    mcp_server = get_mcp_server()

    return Task(
        dataset=PARAMETER_SAMPLES,
        solver=[
            system_message(SYSTEM_PROMPT),
            use_tools(mcp_server),
            generate(),
        ],
        scorer=tool_and_params_scorer(),
    )
