# Installation Guide

Get the Linux MCP Server running quickly with your favorite LLM client.

**Table of Contents**

- [Quick Start](#quick-start)
- [Installation Options](#installation-options)
- [SSH Configuration](#ssh-configuration)
- [Platform Specific Notes](#platform-specific-notes)

---

## Quick Start

Get up and running in three steps:

**1. Install**
```bash
pip install --user linux-mcp-server
```

**2. Configure SSH** (for remote hosts)

Ensure SSH key-based authentication is set up for any remote hosts you want to manage. See [SSH Configuration](#ssh-configuration) for details.

**3. Configure your MCP client**

Add the server to your client configuration. See [Client Configuration](clients.md) for Claude Desktop, Goose, and other clients.

---

## Installation Options

The Linux MCP Server can be installed using pip, uv, or containers. Choose the method that best suits your environment.

### Prerequisites

- Python 3.10 or later - See [Platform Specific Notes](#platform-specific-notes) for installation instructions

### Install with pip (Recommended)

```bash
pip install --user linux-mcp-server
```

??? failure "Command not found?"

    The `~/.local/bin` directory may not be in your PATH.

    **Quick fix:** Use the full path:
    ```bash
    ~/.local/bin/linux-mcp-server
    ```

    **Permanent fix:** Add to your shell config:

    === "bash"
        ```bash
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
        source ~/.bashrc
        ```

    === "zsh"
        ```bash
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
        source ~/.zshrc
        ```

    === "fish"
        ```bash
        fish_add_path ~/.local/bin
        ```

### Install with `uv`

[Install `uv` first](https://github.com/astral-sh/uv#installation), then:

```bash
uv tool install linux-mcp-server
```

**Verify installation:**

```bash
linux-mcp-server --help
```

!!! tip
    If the command is not found, run `uv tool update-shell` to add `~/.local/bin` to your PATH, then restart your shell.

!!! note
    It is not necessary to run `linux-mcp-server` directly for normal use. The LLM client will handle starting and stopping the server.

### Install with Container (Podman)

A container runtime such as [Podman](https://podman-desktop.io) is required.

**Container image:**
```
quay.io/redhat-services-prod/rhel-lightspeed-tenant/linux-mcp-server:latest
```

#### Container Setup for SSH Keys

The container needs access to your SSH keys for remote connections. Set up the required directories and permissions:

```bash
# Create directories
mkdir -p ~/.local/share/linux-mcp-server/logs

# Copy your SSH key and set ownership
cp ~/.ssh/id_ed25519 ~/.local/share/linux-mcp-server/
sudo chown -R 1001:1001 ~/.local/share/linux-mcp-server/
```

??? info "Why UID 1001? Understanding container permissions"

    **The container runs as a non-root user** (UID 1001) for security. Files mounted from your host must be readable by this user.

    **What's happening:**

    - The container process runs as user ID `1001`, not your host user
    - Mounted SSH keys must be owned by `1001` to be readable
    - Log directory must be writable by `1001` to store logs

    **If you see permission errors:**

    ```bash
    # Check current ownership
    ls -la ~/.local/share/linux-mcp-server/

    # Fix ownership (should show 1001 as owner)
    sudo chown -R 1001:1001 ~/.local/share/linux-mcp-server/
    ```

??? warning "Docker vs Podman differences"

    **Podman** uses `--userns keep-id:uid=1001,gid=0` to map user namespaces.

    **Docker** does NOT support this flag. When using Docker:

    - Remove the `--userns` parameter from the run command
    - Ensure files are owned by UID 1001 on the host
    - Create directories beforehand (Docker won't auto-create them)

---

## SSH Configuration

### Quick Setup

1. Ensure passwordless SSH works: `ssh user@hostname "echo success"`
2. Add host aliases to `~/.ssh/config` for convenience
3. Set `LINUX_MCP_USER` environment variable if using a consistent username

??? info "SSH Key Prerequisites"

    The MCP server requires **passwordless SSH authentication** (key-based, not password).

    **Check if you have SSH keys:**
    ```bash
    ls -la ~/.ssh/id_*
    ```

    **If no keys exist, generate them:**
    ```bash
    ssh-keygen -t ed25519 -C "your_email@example.com"
    ```

    **Copy your key to a remote host:**
    ```bash
    ssh-copy-id user@hostname
    ```

    **Test the connection:**
    ```bash
    ssh user@hostname "echo 'SSH working!'"
    ```

    If prompted for a password, key-based authentication is not configured correctly.

### Specifying Remote Hosts

When using MCP tools, the `host` parameter accepts several formats:

| Format | Example | Description |
|--------|---------|-------------|
| SSH alias | `webserver` | Uses settings from `~/.ssh/config` |
| user@host | `admin@10.0.0.50` | Direct connection with username |
| hostname | `server.example.com` | Uses `LINUX_MCP_USER` for username |

### Per-Host Configuration

Use `~/.ssh/config` for per-host connection settings:

```
# ~/.ssh/config
Host webserver
  HostName 10.0.0.64
  User admin

Host dbserver
  HostName 10.0.0.128
  User postgres
  Port 2222
```

With this config, use `host="webserver"` in MCP tool calls instead of the full hostname.

!!! tip
    If `ssh-agent` is running, keys loaded into the session will be used automatically.

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

## Having Problems?

See the [Troubleshooting Guide](troubleshooting.md) for solutions to common issues.

---

## Additional Resources

- **[Client Configuration](clients.md):** Configure Claude Desktop, Goose, and other MCP clients
- **[Troubleshooting](troubleshooting.md):** Solutions for common issues
- **[Usage Guide](usage.md):** Detailed guide on using all available tools
- **[Contributing](contributing.md):** Development workflow and guidelines
- **[MCP Documentation](https://modelcontextprotocol.io/)**
- **[MCP Inspector](https://github.com/modelcontextprotocol/inspector)**

