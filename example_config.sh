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

# Log files that the MCP server is allowed to read
# Add or remove paths as needed for your environment
export LINUX_MCP_ALLOWED_LOG_PATHS="/var/log/messages,/var/log/secure,/var/log/audit/audit.log,/var/log/httpd/error_log,/var/log/httpd/access_log"

# Logging level for the MCP server itself
# Options: DEBUG, INFO, WARNING, ERROR, CRITICAL
export LINUX_MCP_LOG_LEVEL="INFO"

# Common log file locations on RHEL/Fedora systems:
# - /var/log/messages - General system messages
# - /var/log/secure - Authentication and security logs
# - /var/log/audit/audit.log - SELinux audit logs
# - /var/log/httpd/* - Apache web server logs
# - /var/log/nginx/* - Nginx web server logs
# - /var/log/mariadb/mariadb.log - MariaDB database logs
# - /var/log/postgresql/* - PostgreSQL database logs
# - /var/log/firewalld - Firewall logs

echo "Linux MCP Server configuration loaded"
echo "Allowed log paths: $LINUX_MCP_ALLOWED_LOG_PATHS"
echo "Log level: $LINUX_MCP_LOG_LEVEL"

