"""Core MCP server for Linux diagnostics."""

import logging
import os
from typing import Any

from mcp.server import Server
from mcp.types import Tool, TextContent

from .tools import system_info, services, processes, logs, network, storage


# Configure logging
logging.basicConfig(
    level=os.getenv("LINUX_MCP_LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
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
        
        # Storage and hardware tools
        self._register_tool("list_block_devices", storage.list_block_devices,
                          "List block devices and partitions")
        self._register_tool("get_hardware_info", storage.get_hardware_info,
                          "Get hardware information including PCI devices")

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
        
        # Define all tools with their schemas
        tool_definitions = [
            ("get_system_info", "Get basic system information including OS version, kernel, hostname, and uptime", {}),
            ("get_cpu_info", "Get CPU information and load averages", {}),
            ("get_memory_info", "Get memory usage including RAM and swap details", {}),
            ("get_disk_usage", "Get filesystem usage and mount points", {}),
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
            ("get_hardware_info", "Get hardware information including PCI devices", {}),
        ]
        
        for name, description, properties in tool_definitions:
            input_schema = {
                "type": "object",
                "properties": properties,
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
            raise ValueError(f"Unknown tool: {name}")
        
        handler = self.tool_handlers[name]
        try:
            result = await handler(**arguments)
            return [TextContent(type="text", text=result)]
        except Exception as e:
            logger.error(f"Error executing tool {name}: {e}")
            raise


async def main():
    """Run the MCP server."""
    from mcp.server.stdio import stdio_server
    
    logger.info("Starting Linux MCP Server")
    
    mcp_server = LinuxMCPServer()
    server = mcp_server.server
    
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
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )

