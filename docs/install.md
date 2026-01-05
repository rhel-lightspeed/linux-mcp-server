# Installation Guide

If you want to use the Linux MCP Server with LLM clients, follow these instructions to install the MCP server permanently on your system.

**Table of Contents**

- [Claude Desktop Integration](#claude-desktop-integration)
- [Platform Specific Notes](#platform-specific-notes)
- [Troubleshooting](#troubleshooting)

Linux MCP Server can be installed using `pip` or `uv`. Choose the installation that best suites your environment.

## Installation

### Prerequisites

- Python 3.10 or later - See [Platform Specific Notes](#platform-specific-notes) for installation instructions

### Install with pip (Recommended)

```bash
pip install --user linux-mcp-server
```

Run the server

```bash
~/.local/bin/linux-mcp-server
```

### Install with `uv`

- [Install `uv` first](https://github.com/astral-sh/uv#installation).
- Run `uv tool update-shell` or manually add `~/.local/bin/` to `PATH`.

```bash
uv tool install linux-mcp-server
```

Run the server
```
linux-mcp-server
```

The server should start and display initialization messages. Press `Ctrl+C`, then `Return` to stop it.

> [!Note]
> It is not necessary to run `linux-mcp-server` directly for normal use. The LLM client will handle starting and stopping `linux-mcp-server`.

---

## Claude Desktop Integration

### Configuration File Location

Edit your Claude Desktop configuration file:
- **Linux:** `~/.config/Claude/claude_desktop_config.json`
- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

### Configuration Example

The value for `command` will vary depending on how `linux-mcp-server` was installed.

For installion with `pip`:

```json
{
  "mcpServers": {
    "linux-diagnostics": {
      "command": "[path to venv]/bin/linux-mcp-server",
      "args": [],
      "env": {
        "LINUX_MCP_ALLOWED_LOG_PATHS": "/var/log/messages,/var/log/secure,/var/log/audit/audit.log"
      }
    }
  }
}
```

For installion with `uv`:

```json
{
  "mcpServers": {
    "linux-diagnostics": {
      "command": "~/.local/bin/linux-mcp-server",
      "args": [""],
      "env": {
        "LINUX_MCP_ALLOWED_LOG_PATHS": "/var/log/messages,/var/log/secure,/var/log/audit/audit.log"
      }
    }
  }
}
```

### Environment Variables

Configure these environment variables in the `env` section:

| Variable | Required | Default | Description | Example |
|----------|----------|---------|-------------|---------|
| `LINUX_MCP_USER` | No | `None` | User name used when making remote connections over `ssh`. | `tljones` |
| `LINUX_MCP_LOG_DIR` | No | `~/.local/share/linux-mcp-server/logs` | Custom directory for MCP server logs | `/var/log/linux-mcp-server` |
| `LINUX_MCP_LOG_LEVEL` | No | INFO | Logging level for the MCP server | `INFO`, `DEBUG`, `WARNING` |
| `LINUX_MCP_LOG_RETENTION_DAYS` | No | 10 | Days to retain log files (default: 10) | `30` |
| `LINUX_MCP_ALLOWED_LOG_PATHS` | `None` | Yes* | Comma-separated list of log files that `read_log_file` can access | `/var/log/messages,/var/log/secure` |
| `LINUX_MCP_SSH_KEY_PATH` | No | `None` | Path to SSH private key for remote execution | `~/.ssh/id_ed25519` |
| `LINUX_MCP_KEY_PASSPHRASE` | No | `None` | Passphrase used to decrypt the SSH private key, if required | `<secret>` |
| `LINUX_MCP_SEARCH_FOR_SSH_KEY` | No | `False` | Whether to look in `~/.ssh` for SSH keys | yes |
| `LINUX_MCP_VERIFY_HOST_KEYS` | No | `False` | Verify identity of remote hosts when connecting over SSH. | yes |
| `LINUX_MCP_KNOWN_HOSTS_PATH` | No | `None` | Path to SSH known_hosts file | `~/.ssh/other_known_hosts` |
| `LINUX_MCP_COMMAND_TIMEOUT` | No | 30 | Max timeout for remote SSH commands | 60 |

*Required if you want to use the `read_log_file` tool.

### Applying Configuration Changes

After editing the configuration file:

1. **Restart Claude Desktop** completely (quit and relaunch)
2. Look for the MCP server indicator in Claude Desktop
3. The server should appear in the list of available tools

---

## Platform-Specific Notes

### Linux

**Installing Python:**

Most Linux distributions come with Python pre-installed. Check your version:

```bash
python3 --version
```

If you need to install or upgrade Python:

**Debian/Ubuntu:**
```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv
```

**RHEL/CentOS/Fedora:**
```bash
sudo dnf install python3 python3-pip
```

**Arch Linux:**
```bash
sudo pacman -S python python-pip
```

**Notes:**
- You may have to use `python3` and `pip3` commands instead of `python` and `pip` on most Linux distributions

### macOS

**Installing Python:**
- **Official Installer:** https://www.python.org/downloads/macos/

**Note:** The MCP server is optimized for Linux systems. Some tools may have limited functionality on macOS and will not work on Windows.

### Windows

**Installing Python:**
- **Official Installer:** https://www.python.org/downloads/windows/ (check "Add Python to PATH")

Verify: `python --version` in Command Prompt or PowerShell

**Important:** This MCP server requires Linux-specific tools (systemd, journalctl) and has **limited functionality** on Windows. Primarily useful for remote SSH execution to manage Linux servers.

---

## Troubleshooting

### Using MCP Inspector for Debugging

The [MCP Inspector](https://github.com/modelcontextprotocol/inspector) is an official tool for testing and debugging MCP servers.

**Install MCP Inspector:**

**Note:** Requires Node.js to be installed on your system.

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

### Local Debugging of Tool Calls

You can test MCP server tools locally without Claude Desktop or the inspector.

**Method 1: Interactive Python Session**

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

**Method 2: Create a Test Script**

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

**Method 3: Run pytest in verbose mode**

```bash
# Run specific test
pytest tests/test_system_info.py -v

# Run with output showing
pytest tests/test_system_info.py -v -s

# Run all tests for a module
pytest tests/ -k "system_info" -v
```

### Common Installation Issues

#### "command not found: linux-mcp-server"

**Cause:** The package isn't installed or the installation directory isn't in your PATH.

**Solutions:**
1. Verify installation: `pip show linux-mcp-server`
2. Try running as module: `python -m linux_mcp_server`
3. Check if pip install location is in PATH:
   ```bash
   pip show linux-mcp-server | grep Location
   ```
4. Add pip's bin directory to PATH, or use a virtual environment

#### "No module named 'linux_mcp_server'"

**Cause:** The package isn't installed in the current Python environment.

**Solutions:**
1. Ensure you're using the correct Python: `which python` or `where python`
2. Install the package: `pip install linux-mcp-server`
3. If using virtual environment, make sure it's activated

#### "Permission denied" when reading system logs

**Cause:** The user running the MCP server doesn't have permission to read system logs.

**Solutions:**
1. Add user to `adm` or `systemd-journal` group:
   ```bash
   sudo usermod -a -G adm $USER
   sudo usermod -a -G systemd-journal $USER
   ```
2. Log out and log back in for group changes to take effect
3. Only whitelist log files that the user can read in `LINUX_MCP_ALLOWED_LOG_PATHS`

#### "Permission denied" when reading a local application log file

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

#### Claude Desktop doesn't show the MCP server

Common causes:
- **Syntax error:** Validate JSON at https://jsonlint.com/
- **Wrong file location:** See [Configuration File Location](#configuration-file-location)
- **Command not in PATH:** Use full path in `command` field or ensure command is in PATH
- **Server won't start:** Test command manually; check Claude Desktop logs (`~/Library/Logs/Claude/` on macOS, `~/.config/Claude/logs/` on Linux, `%APPDATA%\Claude\logs\` on Windows)
- **Config not reloaded:** Completely quit and restart Claude Desktop

#### ImportError or ModuleNotFoundError during development

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

### Platform-Specific Issues

This section explains issues that may be present when using the MCP server to interact with a system that is not compatible.

#### Linux: "systemctl: command not found"

**Cause:** System doesn't use systemd (very old distributions or non-standard systems).

**Solution:** This MCP server requires systemd to be available on the target system for cetain tools to function properly.
- The main use case is to troubleshoot modern RHEL-alike Linux systems (e.g. RHEL 9.x, 10.x, Fedora 40 and above, etc.)
- Consider upgrading to a modern Linux distribution (RHEL 7+, Fedora, etc.).

#### macOS: Limited functionality warnings

**Cause:** Some Linux-specific commands don't exist or behave differently on macOS.

**Note:** This is expected. The MCP server is designed to diagnose Linux systems (see above).
- Some tools may work on macOS, but some may have reduced functionality or not work at all.

#### Windows: Most or all tools not working

**Cause:** The MCP server relies on Linux-specific tools (systemd, journalctl, etc.) that don't exist on Windows.

**Solution:** This is expected behavior. The MCP server is not designed to diagnose Windows systems.
- On Windows, use the MCP server primarily for:
  - Remote SSH execution to manage Linux servers
  - Testing and development
- For local Windows management, use a Windows-specific MCP server

### Getting Additional Help

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

---

## Additional Resources

- **[Usage Guide](usage.md):** Detailed guide on using all available tools
- **[Contributing](contributing.md):** Development workflow and guidelines
- **[Debugging](debugging.md):** Information for debugging and fixing common problems
- **[MCP Documentation](https://modelcontextprotocol.io/)**
- **[MCP Inspector](https://github.com/modelcontextprotocol/inspector)**

