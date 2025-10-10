"""Core MCP server for Linux diagnostics."""

import logging
import time
from typing import Any

from mcp.server import Server
from mcp.types import Tool, TextContent

from .audit import log_tool_call, log_tool_complete
from .tools import system_info, services, processes, logs, network, storage


logger = logging.getLogger(__name__)


class LinuxMCPServer:
    """MCP Server for Linux system diagnostics and troubleshooting."""

    def __init__(self):
        """Initialize the Linux MCP server."""
        self.name = "linux-diagnostics"
        self.version = "0.1.0"
        self.server = Server(self.name)
        
        # Tool handlers mapping
        self.tool_handlers = {}
        
        # Register all tools
        self._register_tools()

    def _register_tools(self):
        """Register all available diagnostic tools."""
        # System information tools
        self._register_tool("get_system_info", system_info.get_system_info, 
                          "Get basic system information including OS version, kernel, hostname, and uptime")
        self._register_tool("get_cpu_info", system_info.get_cpu_info,
                          "Get CPU information and load averages")
        self._register_tool("get_memory_info", system_info.get_memory_info,
                          "Get memory usage including RAM and swap details")
        self._register_tool("get_disk_usage", system_info.get_disk_usage,
                          "Get filesystem usage and mount points")
        self._register_tool("get_hardware_info", system_info.get_hardware_info,
                          "Get hardware information including CPU architecture, PCI devices, USB devices, and memory hardware")
        
        # Service management tools
        self._register_tool("list_services", services.list_services,
                          "List all systemd services with their current status")
        self._register_tool("get_service_status", services.get_service_status,
                          "Get detailed status of a specific systemd service",
                          {"service_name": {"type": "string", "description": "Name of the service", "required": True}})
        self._register_tool("get_service_logs", services.get_service_logs,
                          "Get recent logs for a specific systemd service",
                          {"service_name": {"type": "string", "description": "Name of the service", "required": True},
                           "lines": {"type": "number", "description": "Number of log lines to retrieve (default: 50)", "required": False}})
        
        # Process management tools
        self._register_tool("list_processes", processes.list_processes,
                          "List running processes with CPU and memory usage")
        self._register_tool("get_process_info", processes.get_process_info,
                          "Get detailed information about a specific process",
                          {"pid": {"type": "number", "description": "Process ID", "required": True}})
        
        # Log and audit tools
        self._register_tool("get_journal_logs", logs.get_journal_logs,
                          "Query systemd journal logs with optional filters",
                          {"unit": {"type": "string", "description": "Filter by systemd unit", "required": False},
                           "priority": {"type": "string", "description": "Filter by priority (emerg, alert, crit, err, warning, notice, info, debug)", "required": False},
                           "since": {"type": "string", "description": "Show entries since specified time (e.g., '1 hour ago', '2024-01-01')", "required": False},
                           "lines": {"type": "number", "description": "Number of log lines to retrieve (default: 100)", "required": False}})
        self._register_tool("get_audit_logs", logs.get_audit_logs,
                          "Get audit logs if available",
                          {"lines": {"type": "number", "description": "Number of log lines to retrieve (default: 100)", "required": False}})
        self._register_tool("read_log_file", logs.read_log_file,
                          "Read a specific log file (whitelist-controlled via LINUX_MCP_ALLOWED_LOG_PATHS)",
                          {"log_path": {"type": "string", "description": "Path to the log file", "required": True},
                           "lines": {"type": "number", "description": "Number of lines to retrieve from the end (default: 100)", "required": False}})
        
        # Network tools
        self._register_tool("get_network_interfaces", network.get_network_interfaces,
                          "Get network interface information including IP addresses")
        self._register_tool("get_network_connections", network.get_network_connections,
                          "Get active network connections")
        self._register_tool("get_listening_ports", network.get_listening_ports,
                          "Get ports that are listening on the system")
        
        # Storage tools
        self._register_tool("list_block_devices", storage.list_block_devices,
                          "List block devices and partitions")
        self._register_tool("list_directories_by_size", storage.list_directories_by_size,
                          "List directories sorted by size (largest first). Uses efficient Linux du command.",
                          {"path": {"type": "string", "description": "Directory path to analyze", "required": True},
                           "top_n": {"type": "number", "description": "Number of top largest directories to return (1-1000)", "required": True}})
        self._register_tool("list_directories_by_name", storage.list_directories_by_name,
                          "List directories sorted alphabetically by name. Uses efficient Linux find command.",
                          {"path": {"type": "string", "description": "Directory path to analyze", "required": True},
                           "reverse": {"type": "boolean", "description": "Sort in reverse order (Z-A)", "required": False}})
        self._register_tool("list_directories_by_modified_date", storage.list_directories_by_modified_date,
                          "List directories sorted by modification date. Uses efficient Linux find command.",
                          {"path": {"type": "string", "description": "Directory path to analyze", "required": True},
                           "newest_first": {"type": "boolean", "description": "Show newest first (default: true)", "required": False}})

    def _register_tool(self, name: str, handler: callable, description: str, parameters: dict = None):
        """Register a tool with its handler."""
        self.tool_handlers[name] = handler
        
        # Build input schema
        input_schema = {
            "type": "object",
            "properties": parameters or {},
        }
        
        # Extract required parameters
        if parameters:
            required = [k for k, v in parameters.items() if v.get("required", False)]
            if required:
                input_schema["required"] = required

    async def list_tools(self) -> list[Tool]:
        """List all available tools."""
        tools = []
        
        # Common SSH parameters for remote execution
        ssh_params = {
            "host": {
                "type": "string",
                "description": "Remote host to connect to via SSH (optional, executes locally if not provided)"
            },
            "username": {
                "type": "string",
                "description": "SSH username for remote host (required if host is provided)"
            }
        }
        
        # Define all tools with their schemas
        tool_definitions = [
            ("get_system_info", "Get basic system information including OS version, kernel, hostname, and uptime", {}),
            ("get_cpu_info", "Get CPU information and load averages", {}),
            ("get_memory_info", "Get memory usage including RAM and swap details", {}),
            ("get_disk_usage", "Get filesystem usage and mount points", {}),
            ("get_hardware_info", "Get hardware information including CPU architecture, PCI devices, USB devices, and memory hardware", {}),
            ("list_services", "List all systemd services with their current status", {}),
            ("get_service_status", "Get detailed status of a specific systemd service",
             {"service_name": {"type": "string", "description": "Name of the service"}}),
            ("get_service_logs", "Get recent logs for a specific systemd service",
             {"service_name": {"type": "string", "description": "Name of the service"},
              "lines": {"type": "number", "description": "Number of log lines (default: 50)"}}),
            ("list_processes", "List running processes with CPU and memory usage", {}),
            ("get_process_info", "Get detailed information about a specific process",
             {"pid": {"type": "number", "description": "Process ID"}}),
            ("get_journal_logs", "Query systemd journal logs with optional filters",
             {"unit": {"type": "string", "description": "Filter by systemd unit"},
              "priority": {"type": "string", "description": "Filter by priority"},
              "since": {"type": "string", "description": "Show entries since specified time"},
              "lines": {"type": "number", "description": "Number of log lines (default: 100)"}}),
            ("get_audit_logs", "Get audit logs if available",
             {"lines": {"type": "number", "description": "Number of log lines (default: 100)"}}),
            ("read_log_file", "Read a specific log file (whitelist-controlled)",
             {"log_path": {"type": "string", "description": "Path to the log file"},
              "lines": {"type": "number", "description": "Number of lines from end (default: 100)"}}),
            ("get_network_interfaces", "Get network interface information including IP addresses", {}),
            ("get_network_connections", "Get active network connections", {}),
            ("get_listening_ports", "Get ports listening on the system", {}),
            ("list_block_devices", "List block devices and partitions", {}),
            ("list_directories_by_size", "List directories sorted by size (largest first). Uses efficient Linux du command.",
             {"path": {"type": "string", "description": "Directory path to analyze"},
              "top_n": {"type": "number", "description": "Number of top largest directories to return (1-1000)"}}),
            ("list_directories_by_name", "List directories sorted alphabetically by name. Uses efficient Linux find command.",
             {"path": {"type": "string", "description": "Directory path to analyze"},
              "reverse": {"type": "boolean", "description": "Sort in reverse order (Z-A)"}}),
            ("list_directories_by_modified_date", "List directories sorted by modification date. Uses efficient Linux find command.",
             {"path": {"type": "string", "description": "Directory path to analyze"},
              "newest_first": {"type": "boolean", "description": "Show newest first (default: true)"}}),
        ]
        
        for name, description, properties in tool_definitions:
            # Merge tool-specific properties with SSH parameters
            all_properties = {**properties, **ssh_params}
            
            input_schema = {
                "type": "object",
                "properties": all_properties,
            }
            
            tools.append(Tool(
                name=name,
                description=description,
                inputSchema=input_schema
            ))
        
        return tools

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> list[TextContent]:
        """Call a tool by name with the given arguments."""
        if name not in self.tool_handlers:
            logger.error(f"Unknown tool requested: {name}", extra={
                'event': 'TOOL_NOT_FOUND',
                'tool': name
            })
            raise ValueError(f"Unknown tool: {name}")
        
        # Log tool invocation with audit function
        log_tool_call(name, arguments)
        
        handler = self.tool_handlers[name]
        start_time = time.time()
        
        try:
            result = await handler(**arguments)
            
            # Calculate execution time
            duration = time.time() - start_time
            
            # Log successful completion
            log_tool_complete(name, status="success", duration=duration)
            
            return [TextContent(type="text", text=result)]
            
        except Exception as e:
            # Calculate execution time for failed execution
            duration = time.time() - start_time
            
            # Log failed completion with error details
            log_tool_complete(name, status="error", duration=duration, error=str(e))
            
            # Re-raise the exception
            raise


async def main():
    """Run the MCP server."""
    from mcp.server.stdio import stdio_server
    
    mcp_server = LinuxMCPServer()
    server = mcp_server.server
    
    logger.info(f"Initialized {mcp_server.name} v{mcp_server.version} with {len(mcp_server.tool_handlers)} tools")
    
    # Register handlers
    @server.list_tools()
    async def handle_list_tools():
        """Handle list_tools request."""
        return await mcp_server.list_tools()
    
    @server.call_tool()
    async def handle_call_tool(name: str, arguments: dict[str, Any]):
        """Handle call_tool request."""
        return await mcp_server.call_tool(name, arguments)
    
    # Run the server
    logger.info("Starting stdio server")
    async with stdio_server() as (read_stream, write_stream):
        logger.info("Server running, ready to accept requests")
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )
    
    logger.info("Server shutdown complete")

