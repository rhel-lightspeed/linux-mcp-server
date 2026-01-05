# Troubleshooting

Solutions for common issues when installing and using the Linux MCP Server.

**Quick Links**

- [Using MCP Inspector](#using-mcp-inspector-for-debugging)
- [Common Installation Issues](#common-installation-issues)
- [SSH Connection Issues](#ssh-connection-issues)
- [Platform-Specific Issues](#platform-specific-issues)
- [Getting Additional Help](#getting-additional-help)

---

## Using MCP Inspector for Debugging

The [MCP Inspector](https://github.com/modelcontextprotocol/inspector) is an official tool for testing and debugging MCP servers.

**Install MCP Inspector:**

!!! note
    Requires Node.js to be installed on your system.

```bash
npm install -g @modelcontextprotocol/inspector
```

**Run the inspector with your MCP server:**

```bash
# For pip-installed version
mcp-inspector linux-mcp-server

# For uvx version
mcp-inspector uvx linux-mcp-server

# For development version
cd /path/to/linux-mcp-server
mcp-inspector uv run linux-mcp-server
```

The inspector provides a web UI where you can:

- View all available tools
- Test tool calls with different parameters
- See real-time request/response data
- Debug connection issues
- Inspect server capabilities

---

## Local Debugging of Tool Calls

You can test MCP server tools locally without Claude Desktop or the inspector.

### Method 1: Interactive Python Session

```bash
# Activate your virtual environment first
source .venv/bin/activate  # Linux/macOS
# OR
.venv\Scripts\activate     # Windows

# Start Python
python

# Import and test tools
>>> from linux_mcp_server.tools import system_info
>>> import asyncio
>>> result = asyncio.run(system_info.get_system_information())
>>> print(result)
```

### Method 2: Create a Test Script

Create a file `test_tool.py`:

```python
import asyncio
from linux_mcp_server.tools import system_info, services

async def main():
    # Test system info tool
    print("=== System Info ===")
    result = await system_info.get_system_information()
    print(result)

    # Test service listing
    print("\n=== Services ===")
    result = await services.list_services()
    print(result)

if __name__ == "__main__":
    asyncio.run(main())
```

Run it:
```bash
python test_tool.py
```

### Method 3: Run pytest in verbose mode

```bash
# Run specific test
pytest tests/test_system_info.py -v

# Run with output showing
pytest tests/test_system_info.py -v -s

# Run all tests for a module
pytest tests/ -k "system_info" -v
```

---

## Common Installation Issues

### "command not found: linux-mcp-server"

**Cause:** The package isn't installed or the installation directory isn't in your PATH.

**Solutions:**

1. Verify installation: `pip show linux-mcp-server`
2. Try running as module: `python -m linux_mcp_server`
3. Check if pip install location is in PATH:
   ```bash
   pip show linux-mcp-server | grep Location
   ```
4. Add pip's bin directory to PATH, or use a virtual environment

### "No module named 'linux_mcp_server'"

**Cause:** The package isn't installed in the current Python environment.

**Solutions:**

1. Ensure you're using the correct Python: `which python` or `where python`
2. Install the package: `pip install linux-mcp-server`
3. If using virtual environment, make sure it's activated

### "Permission denied" when reading system logs

**Cause:** The user running the MCP server doesn't have permission to read system logs.

**Solutions:**

1. Add user to `adm` or `systemd-journal` group:
   ```bash
   sudo usermod -a -G adm $USER
   sudo usermod -a -G systemd-journal $USER
   ```
2. Log out and log back in for group changes to take effect
3. Only whitelist log files that the user can read in `LINUX_MCP_ALLOWED_LOG_PATHS`

### "Permission denied" when reading a local application log file

**Cause:** If the server throws an error when starting (e.g., PermissionError: [Errno 13] Permission denied: '.../server.log'), it's usually because the log file or its parent directory is owned by a different user (often root due to a previous sudo run).

**Solutions:**

1. Verify the current user is the owner of the log directory:
   ```bash
   ls -ld /home/$USER/.local/share/linux-mcp-server/logs
   ```
2. If the owner is not $USER (e.g., if it shows root or a different User ID), reclaim the folder ownership:
   ```bash
   sudo chown -R $USER:$USER /home/$USER/.local/share/linux-mcp-server/logs
   ```

### Claude Desktop doesn't show the MCP server

Common causes:

- **Syntax error:** Validate JSON at https://jsonlint.com/
- **Wrong file location:** See [Client Configuration](clients.md#claude-desktop)
- **Command not in PATH:** Use full path in `command` field or ensure command is in PATH
- **Server won't start:** Test command manually; check Claude Desktop logs (`~/Library/Logs/Claude/` on macOS, `~/.config/Claude/logs/` on Linux, `%APPDATA%\Claude\logs\` on Windows)
- **Config not reloaded:** Completely quit and restart Claude Desktop

### ImportError or ModuleNotFoundError during development

**Cause:** Dependencies aren't installed or virtual environment isn't activated.

**Solutions:**

1. Ensure virtual environment is activated:
   ```bash
   source .venv/bin/activate  # Linux/macOS
   .venv\Scripts\activate     # Windows
   ```
2. Reinstall dependencies:
   ```bash
   uv sync --group dev
   # OR
   pip install -e ".[dev]"
   ```

---

## SSH Connection Issues

### "Permission denied (publickey)"

**Cause:** SSH key authentication failed.

**Solutions:**

1. **Verify key exists and is readable:**
   ```bash
   ls -la ~/.ssh/id_*
   ```

2. **Test SSH directly with verbose output:**
   ```bash
   ssh -v user@hostname "echo test"
   ```
   The `-v` flag shows detailed connection info to identify the failure point.

3. **Ensure key is loaded in ssh-agent:**
   ```bash
   ssh-add -l           # List loaded keys
   ssh-add ~/.ssh/id_ed25519  # Add if missing
   ```

4. **For containers, verify key ownership:**
   ```bash
   ls -la ~/.local/share/linux-mcp-server/id_*
   # Should be owned by UID 1001
   sudo chown 1001:1001 ~/.local/share/linux-mcp-server/id_ed25519
   ```

### "Host key verification failed"

**Cause:** Remote host is not in your known_hosts file.

**Solutions:**

1. **Connect manually first to accept the key:**
   ```bash
   ssh user@hostname
   # Type "yes" when prompted to accept the host key
   ```

2. **Or disable host key verification (less secure):**
   ```json
   "env": {
     "LINUX_MCP_VERIFY_HOST_KEYS": "False"
   }
   ```

### Connection timeouts

**Cause:** Network issues, firewall blocking SSH, or incorrect hostname.

**Solutions:**

1. **Test basic connectivity:**
   ```bash
   ping hostname
   ssh -o ConnectTimeout=5 user@hostname "echo test"
   ```

2. **Increase timeout in client config:**
   ```json
   "env": {
     "LINUX_MCP_COMMAND_TIMEOUT": "60"
   }
   ```

3. **Check firewall rules** on both local and remote systems for port 22 (or custom SSH port).

### "No such file or directory" for SSH key

**Cause:** The SSH key path is incorrect or key doesn't exist.

**Solutions:**

1. **Check if the key exists:**
   ```bash
   ls -la ~/.ssh/
   ```

2. **Generate a new key if needed:**
   ```bash
   ssh-keygen -t ed25519 -C "your_email@example.com"
   ```

3. **Verify `LINUX_MCP_SSH_KEY_PATH` points to correct file.**

---

## Platform-Specific Issues

This section explains issues that may be present when using the MCP server to interact with a system that is not compatible.

### Linux: "systemctl: command not found"

**Cause:** System doesn't use systemd (very old distributions or non-standard systems).

**Solution:** This MCP server requires systemd to be available on the target system for certain tools to function properly.

- The main use case is to troubleshoot modern RHEL-alike Linux systems (e.g. RHEL 9.x, 10.x, Fedora 40 and above, etc.)
- Consider upgrading to a modern Linux distribution (RHEL 7+, Fedora, etc.).

### macOS: Limited functionality warnings

**Cause:** Some Linux-specific commands don't exist or behave differently on macOS.

**Note:** This is expected. The MCP server is designed to diagnose Linux systems (see above).

- Some tools may work on macOS, but some may have reduced functionality or not work at all.

### Windows: Most or all tools not working

**Cause:** The MCP server relies on Linux-specific tools (systemd, journalctl, etc.) that don't exist on Windows.

**Solution:** This is expected behavior. The MCP server is not designed to diagnose Windows systems.

- On Windows, use the MCP server primarily for:
  - Remote SSH execution to manage Linux servers
  - Testing and development
- For local Windows management, use a Windows-specific MCP server

---

## Getting Additional Help

1. **Check logs:** Server logs in `~/.local/share/linux-mcp-server/logs/`, Claude Desktop logs (see above)
2. **Enable debug:** Set `"LINUX_MCP_LOG_LEVEL": "DEBUG"` in config, restart your AI Agent (e.g. Claude Desktop)
3. **Test with MCP Inspector:** Isolate whether issue is with server or client
4. **Run the MCP server manually:** Make sure the MCP server does not crash upon start and is able to receive messages.
5. **Open an issue:** https://github.com/rhel-lightspeed/linux-mcp-server/issues
   - Include:
     - Your OS and version
     - Python version
     - Installation method used
     - Error messages and logs
     - Steps to reproduce
