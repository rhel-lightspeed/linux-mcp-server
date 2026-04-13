# Tools

The Linux MCP Server provides read-only diagnostic tools organized into the following categories. The AI model automatically selects the appropriate tool based on your natural language query.

## System Information

Tools for checking OS version, kernel, CPU, memory, disk usage, and hardware information.

- `get_system_information` - OS, kernel, hostname, uptime
- `get_cpu_information` - CPU cores, frequency, usage, load averages
- `get_memory_information` - RAM and swap usage
- `get_disk_usage` - Filesystem usage and mount points
- `get_hardware_information` - PCI devices, USB devices, memory hardware

## Services

Tools for inspecting systemd services.

- `list_services` - List all systemd services with status
- `get_service_status` - Detailed status for a specific service
- `get_service_logs` - Recent logs for a specific service

## Processes

Tools for inspecting running processes.

- `list_processes` - List processes sorted by CPU usage
- `get_process_info` - Detailed information about a specific process

## Logs & Audit

Tools for reading system and application logs.

- `get_journal_logs` - Query systemd journal with filters (unit, priority, time range)
- `read_log_file` - Read a specific log file (must be in the allowed list)

## Network

Tools for network diagnostics.

- `get_network_interfaces` - Network interfaces, IP addresses, and statistics
- `get_network_connections` - Active network connections
- `get_listening_ports` - Ports listening on the system

## Storage

Tools for disk and storage analysis.

- `list_block_devices` - Block devices, partitions, and disk I/O statistics
- `list_directories` - List subdirectories with sorting by size, name, or modification time

## Script Execution (Experimental)

When [Guarded Command Execution](guarded-command-execution.md) is enabled, additional tools allow the model to run custom scripts on target systems with safety guardrails.

- `validate_script` - Check a script before running it
- `run_script` - Run a validated script (no confirmation needed)
- `run_script_with_confirmation` - Run a validated script (requires user approval)
- `run_script_interactive` - Run a validated script with embedded approval UI
