# Installation Guide - Linux MCP Server

This guide provides comprehensive installation instructions for both end users and developers.

## Table of Contents

- [For End Users](#for-end-users)
- [For Developers](#for-developers)
- [Claude Desktop Integration](#claude-desktop-integration)
- [Platform-Specific Notes](#platform-specific-notes)
- [Troubleshooting](#troubleshooting)

---

## For End Users

If you just want to use the Linux MCP Server with Claude Desktop or other MCP clients, follow these instructions.

### Prerequisites

- **Python 3.10 or higher** - See [Platform-Specific Notes](#platform-specific-notes) for installation instructions
- **pip** (usually included with Python)

### Method 1: Install with pip (Recommended)

This method installs the MCP server permanently on your system.

**Step 1: Install the package from PyPI**

```bash
pip install linux-mcp-server
```

**Step 2: Verify the installation**

```bash
linux-mcp-server --version
```

You should see the version number displayed.

**Step 3: Test the server**

```bash
linux-mcp-server
```

The server should start and display initialization messages. Press `Ctrl+C` to stop it.

### Method 2: Run with uvx (No Installation)

This method runs the server without permanently installing it - useful for trying it out or occasional use.

**Prerequisites:**
- Install `uv` first: https://github.com/astral-sh/uv#installation

**Run the server:**

```bash
uvx linux-mcp-server
```

The first run will download and set up the package automatically.

### Next Steps

After installation, configure the server for use with Claude Desktop. See [Claude Desktop Integration](#claude-desktop-integration).

---

## For Developers

If you want to contribute to the project or modify the code, follow these instructions.

### Prerequisites

- **Python 3.10 or higher**
- **Git**
- **uv** (recommended) - https://github.com/astral-sh/uv#installation
  - OR **pip** and **venv** (alternative)

### Method 1: Setup with uv (Recommended)

**Step 1: Clone the repository**

```bash
git clone https://github.com/rhel-lightspeed/linux-mcp-server.git
cd linux-mcp-server
```

**Step 2: Create virtual environment and install dependencies**

```bash
uv venv
source .venv/bin/activate  # On Linux/macOS
# OR
.venv\Scripts\activate     # On Windows
```

**Step 3: Install the package in editable mode with dev dependencies**

```bash
uv sync --group dev
```

**Step 4: Verify the installation**

```bash
python -m linux_mcp_server --version
```

**Step 5: Run the tests**

```bash
pytest
```

All tests should pass.

### Method 2: Setup with pip and venv (Alternative)

**Step 1: Clone the repository**

```bash
git clone https://github.com/rhel-lightspeed/linux-mcp-server.git
cd linux-mcp-server
```

**Step 2: Create and activate virtual environment**

```bash
python -m venv .venv
source .venv/bin/activate  # On Linux/macOS
# OR
.venv\Scripts\activate     # On Windows
```

**Step 3: Install the package in editable mode with dev dependencies**

```bash
pip install -e ".[dev]"
```

Note: On some shells (like zsh), you may need to escape the brackets:
```bash
pip install -e .\[dev\]
```

**Step 4: Verify the installation**

```bash
python -m linux_mcp_server --version
```

**Step 5: Run the tests**

```bash
pytest
```

All tests should pass.

### Running the Server in Development

There are multiple ways to run the server during development:

**Option 1: Using uv run (recommended for development)**

```bash
uv run linux-mcp-server
```

**Option 2: Using the installed entry point**

```bash
linux-mcp-server
```

**Option 3: As a Python module**

```bash
python -m linux_mcp_server
```

### Development Workflow

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed information about:
- Test-Driven Development (TDD) workflow
- Code standards and style guidelines
- Adding new tools
- Commit message format
- Pull request process

---

## Claude Desktop Integration

After installing the Linux MCP Server, configure Claude Desktop to use it.

### Configuration File Locations

**Linux:**
```
~/.config/Claude/claude_desktop_config.json
```

**macOS:**
```
~/Library/Application Support/Claude/claude_desktop_config.json
```

**Windows:**
```
%APPDATA%\Claude\claude_desktop_config.json
```

### Configuration for pip-installed version

If you installed with `pip install linux-mcp-server`:

```json
{
  "mcpServers": {
    "linux-diagnostics": {
      "command": "linux-mcp-server",
      "args": [],
      "env": {
        "LINUX_MCP_ALLOWED_LOG_PATHS": "/var/log/messages,/var/log/secure,/var/log/audit/audit.log",
        "LINUX_MCP_LOG_LEVEL": "INFO"
      }
    }
  }
}
```

### Configuration for uvx

If you prefer to run with `uvx`:

```json
{
  "mcpServers": {
    "linux-diagnostics": {
      "command": "uvx",
      "args": ["linux-mcp-server"],
      "env": {
        "LINUX_MCP_ALLOWED_LOG_PATHS": "/var/log/messages,/var/log/secure,/var/log/audit/audit.log",
        "LINUX_MCP_LOG_LEVEL": "INFO"
      }
    }
  }
}
```

### Configuration for development version

If you're developing and want to use your local clone:

```json
{
  "mcpServers": {
    "linux-diagnostics": {
      "command": "uv",
      "args": [
        "--directory",
        "/absolute/path/to/linux-mcp-server",
        "run",
        "linux-mcp-server"
      ],
      "env": {
        "LINUX_MCP_ALLOWED_LOG_PATHS": "/var/log/messages,/var/log/secure,/var/log/audit/audit.log",
        "LINUX_MCP_LOG_LEVEL": "INFO",
        "LINUX_MCP_SSH_KEY_PATH": "/home/user/.ssh/id_ed25519"
      }
    }
  }
}
```

Replace `/absolute/path/to/linux-mcp-server` with your actual repository path.

### Environment Variables

Configure these environment variables in the `env` section:

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `LINUX_MCP_ALLOWED_LOG_PATHS` | Yes* | Comma-separated list of log files that `read_log_file` can access | `/var/log/messages,/var/log/secure` |
| `LINUX_MCP_LOG_LEVEL` | No | Logging level for the MCP server | `INFO`, `DEBUG`, `WARNING` |
| `LINUX_MCP_LOG_DIR` | No | Custom directory for MCP server logs | `/var/log/linux-mcp-server` |
| `LINUX_MCP_LOG_RETENTION_DAYS` | No | Days to retain log files (default: 10) | `30` |
| `LINUX_MCP_SSH_KEY_PATH` | No | Path to SSH private key for remote execution | `~/.ssh/id_ed25519` |

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
- Use `python3` and `pip3` commands instead of `python` and `pip` on most Linux distributions
- The MCP server requires systemd, so it's designed for modern Linux distributions

### macOS

**Installing Python:**

**Option 1: Homebrew (Recommended)**
```bash
brew install python@3.12
```

**Option 2: Official Installer**

Download from https://www.python.org/downloads/macos/

**Option 3: System Python**

macOS comes with Python, but it may be an older version. Check:
```bash
python3 --version
```

**Notes:**
- Claude Desktop config location: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Use forward slashes in paths
- The MCP server works on macOS but is optimized for Linux systems (some tools may have limited functionality)

### Windows

**Installing Python:**

**Option 1: Microsoft Store (Recommended for most users)**

1. Open Microsoft Store
2. Search for "Python 3.12" (or latest version)
3. Click "Get" or "Install"
4. Python will be added to your PATH automatically

**Option 2: Official Installer**

1. Download from https://www.python.org/downloads/windows/
2. Run the installer
3. **Important:** Check "Add Python to PATH" during installation
4. Complete the installation

**Verifying Installation:**

Open Command Prompt or PowerShell and run:
```cmd
python --version
```

**Notes:**
- Claude Desktop config location: `%APPDATA%\Claude\claude_desktop_config.json`
  - Typically: `C:\Users\YourUsername\AppData\Roaming\Claude\claude_desktop_config.json`
- Use backslashes in Windows paths, and escape them in JSON: `C:\\logs\\app.log`
- **Important:** This MCP server is designed for Linux systems and relies on Linux-specific tools (systemd, journalctl, etc.). On Windows, it will have **limited functionality** - mainly useful for remote SSH execution to manage Linux servers
- For managing Windows systems, consider using a Windows-specific MCP server instead

---

## Troubleshooting

### Using MCP Inspector for Debugging

The [MCP Inspector](https://github.com/modelcontextprotocol/inspector) is an official tool for testing and debugging MCP servers.

**Install MCP Inspector:**

NOTE: You will new Nodejs to be installed in your system.

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
>>> result = asyncio.run(system_info.get_system_info())
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
    result = await system_info.get_system_info()
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

#### "Permission denied" when reading logs

**Cause:** The user running the MCP server doesn't have permission to read system logs.

**Solutions:**
1. Add user to `adm` or `systemd-journal` group:
   ```bash
   sudo usermod -a -G adm $USER
   sudo usermod -a -G systemd-journal $USER
   ```
2. Log out and log back in for group changes to take effect
3. Only whitelist log files that the user can read in `LINUX_MCP_ALLOWED_LOG_PATHS`

#### Claude Desktop doesn't show the MCP server

**Causes and Solutions:**

1. **Configuration file syntax error**
   - Validate your JSON: https://jsonlint.com/
   - Check for missing commas, quotes, or brackets

2. **Wrong configuration file location**
   - Verify you're editing the correct file (see [Configuration File Locations](#configuration-file-locations))

3. **Command not found in PATH**
   - Use full path to the executable in the `command` field
   - Or ensure the command is in your PATH

4. **Server fails to start**
   - Test the command manually in terminal
   - Check Claude Desktop logs:
     - **macOS:** `~/Library/Logs/Claude/`
     - **Linux:** `~/.config/Claude/logs/`
     - **Windows:** `%APPDATA%\Claude\logs\`

5. **Restart required**
   - Completely quit and restart Claude Desktop after configuration changes

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

**Solution:** This MCP server requires systemd to be available on the target system.
- Consider upgrading to a modern Linux distribution (RHEL 7+, Fedora, etc.).

#### macOS: Limited functionality warnings

**Cause:** Some Linux-specific commands don't exist or behave differently on macOS.

**Note:** This is expected. The MCP server is optimized for Linux systems. Some tools may work on macOS, but some may have reduced functionality or don't work at all.

#### Windows: Most tools not working

**Cause:** The MCP server relies on Linux-specific tools (systemd, journalctl, etc.) that don't exist on Windows.

**Solution:** This is expected behavior. On Windows, use the MCP server primarily for:
- Remote SSH execution to manage Linux servers
- Testing and development
- For local Windows management, use a Windows-specific MCP server

### Getting Additional Help

If you encounter issues not covered here:

1. **Check the logs:**
   - Server logs: `~/.local/share/linux-mcp-server/logs/`
   - Claude Desktop logs: See locations above

2. **Enable debug logging:**
   - Set `"LINUX_MCP_LOG_LEVEL": "DEBUG"` in your configuration
   - Restart Claude Desktop
   - Check the server logs for detailed information

3. **Test with MCP Inspector:**
   - Use the inspector to isolate whether the issue is with the server or Claude Desktop

4. **Open an issue:**
   - GitHub Issues: https://github.com/rhel-lightspeed/linux-mcp-server/issues
   - Include:
     - Your OS and version
     - Python version
     - Installation method used
     - Error messages and logs
     - Steps to reproduce

---

## Additional Resources

- **Usage Guide:** [USAGE.md](USAGE.md) - Detailed guide on using all available tools
- **Contributing:** [CONTRIBUTING.md](CONTRIBUTING.md) - Development workflow and guidelines
- **Main README:** [README.md](README.md) - Project overview and architecture
- **MCP Documentation:** https://modelcontextprotocol.io/
- **MCP Inspector:** https://github.com/modelcontextprotocol/inspector

