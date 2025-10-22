#!/usr/bin/env python3
"""
Test MCP Tools - Systematically test all tools in the Linux MCP Server

This script tests all 20 MCP tools by connecting to a real RHEL instance via SSH.

Usage:
    # From project root
    LINUX_MCP_CONFIG_FILE=tests/test-hosts.yaml python tests/test_mcp_tools.py
    
    # From tests directory
    cd tests
    LINUX_MCP_CONFIG_FILE=test-hosts.yaml python test_mcp_tools.py

Requirements:
    - MCP SDK installed (pip install -e .)
    - test-hosts.yaml configured with valid RHEL host
    - SSH keys configured for accessing the test host
"""
import asyncio
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from contextlib import AsyncExitStack

# Test configuration
TEST_HOST = "bastion.r42dl.sandbox5417.opentlc.com"  # From test-hosts.yaml
TEST_USERNAME = "student"                              # From test-hosts.yaml

# Tool test cases with parameters
TOOL_TESTS = {
    # System Information Tools
    "get_system_info": {
        "host": TEST_HOST,
        "username": TEST_USERNAME
    },
    "get_cpu_info": {
        "host": TEST_HOST,
        "username": TEST_USERNAME
    },
    "get_memory_info": {
        "host": TEST_HOST,
        "username": TEST_USERNAME
    },
    "get_disk_usage": {
        "host": TEST_HOST,
        "username": TEST_USERNAME
    },
    "get_hardware_info": {
        "host": TEST_HOST,
        "username": TEST_USERNAME
    },
    
    # Service Management Tools
    "list_services": {
        "host": TEST_HOST,
        "username": TEST_USERNAME,
        "state": "running"
    },
    "get_service_status": {
        "host": TEST_HOST,
        "username": TEST_USERNAME,
        "service_name": "sshd"
    },
    "get_service_logs": {
        "host": TEST_HOST,
        "username": TEST_USERNAME,
        "service_name": "sshd",
        "lines": 10
    },
    
    # Process Management Tools
    "list_processes": {
        "host": TEST_HOST,
        "username": TEST_USERNAME,
        "limit": 10
    },
    "get_process_info": {
        "host": TEST_HOST,
        "username": TEST_USERNAME,
        "pid": 1
    },
    
    # Network Tools
    "get_network_interfaces": {
        "host": TEST_HOST,
        "username": TEST_USERNAME
    },
    "get_network_connections": {
        "host": TEST_HOST,
        "username": TEST_USERNAME
    },
    "get_listening_ports": {
        "host": TEST_HOST,
        "username": TEST_USERNAME
    },
    
    # Storage & Disk Tools
    "list_block_devices": {
        "host": TEST_HOST,
        "username": TEST_USERNAME
    },
    "list_directories_by_size": {
        "host": TEST_HOST,
        "username": TEST_USERNAME,
        "path": "/var",
        "depth": 2
    },
    "list_directories_by_name": {
        "host": TEST_HOST,
        "username": TEST_USERNAME,
        "path": "/var",
        "pattern": "log*"
    },
    "list_directories_by_modified_date": {
        "host": TEST_HOST,
        "username": TEST_USERNAME,
        "path": "/var/log",
        "days": 7
    },
    
    # Logs & Journal Tools
    "get_journal_logs": {
        "host": TEST_HOST,
        "username": TEST_USERNAME,
        "lines": 10
    },
    "get_audit_logs": {
        "host": TEST_HOST,
        "username": TEST_USERNAME,
        "lines": 10
    },
    "read_log_file": {
        "host": TEST_HOST,
        "username": TEST_USERNAME,
        "file_path": "/var/log/messages",
        "lines": 10
    },
}

async def test_tool(session: ClientSession, tool_name: str, arguments: dict):
    """Test a single tool"""
    try:
        result = await session.call_tool(tool_name, arguments)
        
        # Check if result has content
        if hasattr(result, 'content') and result.content:
            # Get first content item
            content = result.content[0]
            if hasattr(content, 'text'):
                text = content.text
                # Show first 200 chars of output
                preview = text[:200] + "..." if len(text) > 200 else text
                return True, preview
            else:
                return True, "Success (no text content)"
        else:
            return True, "Success (empty result)"
            
    except Exception as e:
        return False, str(e)

async def main():
    """Main test function"""
    print("=" * 80)
    print("MCP Tools Test Suite")
    print("=" * 80)
    print(f"\nTest Configuration:")
    print(f"  Host: {TEST_HOST}")
    print(f"  Username: {TEST_USERNAME}")
    print(f"  Total Tools: {len(TOOL_TESTS)}")
    print("=" * 80)
    print()
    
    # Connect via local MCP server (stdio)
    server_params = StdioServerParameters(
        command="python",
        args=["-m", "linux_mcp_server"],
        env=None
    )
    
    results = {
        "passed": [],
        "failed": [],
        "total": len(TOOL_TESTS)
    }
    
    async with AsyncExitStack() as stack:
        try:
            # Connect to MCP server via stdio
            stdio_transport = await stack.enter_async_context(stdio_client(server_params))
            stdio, write = stdio_transport
            session = await stack.enter_async_context(ClientSession(stdio, write))
            
            # Initialize
            await session.initialize()
            
            # List available tools
            tools_response = await session.list_tools()
            available_tools = {tool.name for tool in tools_response.tools}
            
            print(f"✓ Connected to MCP Server")
            print(f"✓ Found {len(available_tools)} available tools")
            print()
            
            # Test each tool
            for idx, (tool_name, arguments) in enumerate(TOOL_TESTS.items(), 1):
                print(f"[{idx}/{len(TOOL_TESTS)}] Testing: {tool_name}")
                
                if tool_name not in available_tools:
                    print(f"  ❌ SKIP: Tool not found in server")
                    results["failed"].append((tool_name, "Tool not available"))
                    continue
                
                success, message = await test_tool(session, tool_name, arguments)
                
                if success:
                    print(f"  ✅ PASS")
                    # print(f"     Preview: {message[:100]}")
                    results["passed"].append(tool_name)
                else:
                    print(f"  ❌ FAIL: {message}")
                    results["failed"].append((tool_name, message))
                
                print()
                
        except Exception as e:
            print(f"\n❌ Failed to connect to MCP server: {e}")
            print(f"\nMake sure the server is running:")
            print(f"  python -m linux_mcp_server")
            return 1
    
    # Print summary
    print("=" * 80)
    print("Test Summary")
    print("=" * 80)
    print(f"Total Tools:  {results['total']}")
    print(f"✅ Passed:     {len(results['passed'])}")
    print(f"❌ Failed:     {len(results['failed'])}")
    print(f"Success Rate: {len(results['passed']) / results['total'] * 100:.1f}%")
    print()
    
    if results['failed']:
        print("Failed Tools:")
        for tool_name, error in results['failed']:
            print(f"  • {tool_name}")
            print(f"    Error: {error[:100]}")
        print()
    
    return 0 if len(results['failed']) == 0 else 1

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)

