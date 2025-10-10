#!/bin/bash
# Example configuration for Linux MCP Server
#
# Usage:
#   1. Copy this file: cp example_config.sh config.sh
#   2. Customize the settings below
#   3. Source it before running: source config.sh
#   4. Run the server using one of:
#      - uv run linux-mcp-server (recommended)
#      - uvx --from /path/to/linux-mcp-server linux-mcp-server
#      - python -m linux_mcp_server

# ========================================
# Audit Logging Configuration
# ========================================

# Logging level for the MCP server audit logs
# Options: DEBUG, INFO, WARNING, ERROR, CRITICAL
# - DEBUG: Detailed diagnostics (connection reuse, timing, function flow)
# - INFO: Operation logging (tool calls, SSH connections, command execution)
# - WARNING: Authentication failures, retryable errors
# - ERROR: Failed operations, connection failures
# - CRITICAL: Server failures, unrecoverable errors
export LINUX_MCP_LOG_LEVEL="INFO"

# Custom directory for audit logs
# Default: ~/.local/share/linux-mcp-server/logs/
# Logs are written in both human-readable text and JSON formats
# export LINUX_MCP_LOG_DIR="/var/log/linux-mcp-server"

# Number of days to retain rotated log files
# Default: 10 days
# Logs are rotated daily at midnight
export LINUX_MCP_LOG_RETENTION_DAYS="10"

# ========================================
# Log File Access Control
# ========================================

# Log files that the MCP server is allowed to read
# Add or remove paths as needed for your environment
export LINUX_MCP_ALLOWED_LOG_PATHS="/var/log/messages,/var/log/secure,/var/log/audit/audit.log,/var/log/httpd/error_log,/var/log/httpd/access_log"

# Common log file locations on RHEL/Fedora systems:
# - /var/log/messages - General system messages
# - /var/log/secure - Authentication and security logs
# - /var/log/audit/audit.log - SELinux audit logs
# - /var/log/httpd/* - Apache web server logs
# - /var/log/nginx/* - Nginx web server logs
# - /var/log/mariadb/mariadb.log - MariaDB database logs
# - /var/log/postgresql/* - PostgreSQL database logs
# - /var/log/firewalld - Firewall logs

echo "================================"
echo "Linux MCP Server Configuration"
echo "================================"
echo "Audit Log Level: $LINUX_MCP_LOG_LEVEL"
if [ -n "$LINUX_MCP_LOG_DIR" ]; then
    echo "Audit Log Directory: $LINUX_MCP_LOG_DIR"
else
    echo "Audit Log Directory: ~/.local/share/linux-mcp-server/logs/ (default)"
fi
echo "Log Retention: $LINUX_MCP_LOG_RETENTION_DAYS days"
echo "Allowed Log Paths: $LINUX_MCP_ALLOWED_LOG_PATHS"
echo "================================"

