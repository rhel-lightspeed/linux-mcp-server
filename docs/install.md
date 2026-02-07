# Installation Guide

Get the Linux MCP Server running quickly with your favorite LLM client.

!!! note "Architecture Requirement"
    This setup requires a **Control VM**, where the MCP server and AI assistant run—this can be your local machine, and a **Target VM** - the Linux system you wish to troubleshoot, which can be a local or remote host.

**Table of Contents**

- [Installation Options](#installation-options)
- [SSH Configuration](#ssh-configuration)
- [Platform Specific Notes](#platform-specific-notes)

---

## Installation Options

The Linux MCP Server can be installed using `pip`, `uv`, or run in a container. Choose the method that best suits your environment.

### Prerequisites

Python 3.10 or later.

See [Platform Specific Notes](#platform-specific-notes) for installation instructions

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
linux-mcp-server
```

!!! tip
    If the command is not found, run `uv tool update-shell` to add `~/.local/bin` to your PATH, then restart your shell.

!!! note
    It is not necessary to run `linux-mcp-server` directly for normal use. The LLM client will handle starting and stopping the server.

!!! note
    The `gssapi` package is needed for the server to connect via SSH authentication to Kerberos registered systems. It may be installed as an optional dependency with `linux_mcp_server[gssapi]`.

### Run in a container (Podman)

A container runtime such as [Podman](https://podman-desktop.io) is required.

**Container image:**
```
quay.io/redhat-services-prod/rhel-lightspeed-tenant/linux-mcp-server:latest
```

See [client configuration](clients.md) for examples of how to run the container using stdio transport.

When using an HTTP transport, `http` or `streamable-http`, the container must be started before launching the LLM client.

```bash
podman run --rm --interactive \
  --userns "keep-id:uid=1001,gid=0"
  --port 8000:8000 \
  -e LINUX_MCP_KEY_PASSPHRASE  # Only needed if the SSH key is protected by a passphrase
  -e LINUX_MCP_TRANSPORT=streamable-http \
  -e LINUX_MCP_HOST=0.0.0.0 \  # bind to all interfaces inside the container
  -v /home/YOUR_USER/.ssh/id_ed25519:/var/lib/mcp/.ssh/id_ed25519:ro \
  -v /home/YOUR_USER/.ssh/config:/var/lib/mcp/.ssh/config:ro,Z \
  -v /home/YOUR_USER/.local/share/linux-mcp-server/logs:/var/lib/mcp/.local/share/linux-mcp-server/logs:rw \
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


Once the SSH keys are configured, configure your [LLM client](clients.md) to run the container image. It is not necessary to run the container manually since the LLM client will do that.

---

## SSH Configuration

### Setup

1. Verify passwordless SSH access to the target system: `ssh user@hostname "echo success"`.
1. Add host aliases to the `~/.ssh/config` file for easier access.
1. (Optional) Set the `LINUX_MCP_USER` environment variable if the remote user name is the same on all hosts and not using `~/.ssh/config`.

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

When using MCP tools, the `host` parameter may be a fully qualified domain name (FQDN), an alias from `~/.ssh/config`, or an IP address.

### Per-Host Configuration

If per-host connection settings are required, use `~/.ssh/config` and **do not** set `LINUX_MCP_USER`.

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

#### Installing Python

=== "Official Python Installer (Recommended)"

    Download from [python.org/downloads/macos](https://www.python.org/downloads/macos/) and run the installer.

=== "pyenv"

    For managing multiple Python versions:

    ```bash
    brew install pyenv
    echo 'eval "$(pyenv init -)"' >> ~/.zshrc
    source ~/.zshrc
    pyenv install 3.12
    pyenv global 3.12
    ```


#### Installing linux-mcp-server

=== "pip"

    ```bash
    pip3 install --user linux-mcp-server
    ```

=== "uv"

    Install [uv](https://docs.astral.sh/uv/#installation).

    Install `linux-mcp-server`.

    ```bash
    uv tool install linux-mcp-server
    ```

??? failure "Command not found after installation?"

    On macOS (which uses `zsh` by default), add the install location to your `PATH`:

    ```bash
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
    source ~/.zshrc
    ```

    For uv installations, also run:
    ```bash
    uv tool update-shell
    ```

#### SSH Setup on macOS

macOS includes OpenSSH by default. To set up key-based authentication:

```bash
# Generate a key (if you don't have one)
ssh-keygen -t ed25519 -C "your_email@example.com"

# Copy to remote host
ssh-copy-id user@hostname
```

??? tip "Using macOS Keychain for SSH keys"

    macOS can store your SSH key passphrase in the system Keychain, so you don't need to enter it repeatedly:

    ```bash
    # Add your key to the ssh-agent with Keychain storage
    ssh-add --apple-use-keychain ~/.ssh/id_ed25519
    ```

    Add this to `~/.ssh/config` to automatically load keys:

    ```
    Host *
      AddKeysToAgent yes
      UseKeychain yes
      IdentityFile ~/.ssh/id_ed25519
    ```

#### macOS Limitations

!!! warning "Local vs Remote Usage"

    **Local execution** (no `host` parameter): Most tools will have limited functionality since macOS doesn't use systemd, journalctl, or standard Linux paths.

    | Tool | Local (macOS) | Remote (Linux) |
    |------|---------------|----------------|
    | `get_system_information` | ✅ Works | ✅ Works |
    | `list_processes` | ✅ Works | ✅ Works |
    | `get_network_interfaces` | ✅ Works | ✅ Works |
    | `list_services` | ❌ No systemd | ✅ Works |
    | `get_journal_logs` | ❌ No journald | ✅ Works |
    | `get_disk_usage` | ✅ Works | ✅ Works |

    **Remote execution** (with `host` parameter): Full functionality when connecting to Linux servers via SSH.

### Windows

#### Installing Python

=== "Microsoft Store (Easiest)"

    Search for "Python" in the Microsoft Store and install Python 3.12 or later. This automatically handles PATH configuration.

=== "winget"

    Using Windows Package Manager (built into Windows 11, available for Windows 10):

    ```powershell
    winget install Python.Python.3.12
    ```

=== "Official Installer"

    Download from [python.org/downloads/windows](https://www.python.org/downloads/windows/).

    !!! warning "Important"
        Check **"Add Python to PATH"** during installation, or you'll need to configure it manually.

=== "scoop"

    [Scoop](https://scoop.sh/) is a command-line installer for Windows:

    ```powershell
    scoop install python
    ```

**Verify installation** (in PowerShell or Command Prompt):

```powershell
python --version
```

#### Installing linux-mcp-server

=== "pip"

    ```powershell
    pip install --user linux-mcp-server
    ```

=== "uv"

    ```powershell
    # Install uv
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

    # Install linux-mcp-server
    uv tool install linux-mcp-server
    ```

??? failure "Command not found after installation?"

    The default pip user install location on Windows is:
    ```
    %APPDATA%\Python\Python3X\Scripts
    ```

    **Add to PATH via PowerShell:**
    ```powershell
    # Find Python user scripts directory
    python -c "import site; print(site.USER_SITE.replace('site-packages', 'Scripts'))"

    # Add to your PATH (replace X with your Python version)
    [Environment]::SetEnvironmentVariable("Path", $env:Path + ";$env:APPDATA\Python\Python312\Scripts", "User")
    ```

    Restart your terminal after making PATH changes.

#### SSH Setup on Windows

Windows 10/11 includes OpenSSH as an optional feature.

**Enable OpenSSH Client:**

=== "Settings UI"

    1. Open **Settings** → **Apps** → **Optional features**
    2. Click **Add a feature**
    3. Search for **OpenSSH Client** and install it

=== "PowerShell (Admin)"

    ```powershell
    Add-WindowsCapability -Online -Name OpenSSH.Client~~~~0.0.1.0
    ```

**Generate and copy SSH keys:**

```powershell
# Generate a key
ssh-keygen -t ed25519 -C "your_email@example.com"

# Copy to remote host (Windows doesn't have ssh-copy-id by default)
type $env:USERPROFILE\.ssh\id_ed25519.pub | ssh user@hostname "cat >> ~/.ssh/authorized_keys"
```

??? tip "Using ssh-agent on Windows"

    Start the ssh-agent service to manage your keys:

    ```powershell
    # Start the service (run as Administrator)
    Get-Service ssh-agent | Set-Service -StartupType Automatic
    Start-Service ssh-agent

    # Add your key
    ssh-add $env:USERPROFILE\.ssh\id_ed25519
    ```

#### Windows Limitations

!!! warning "Remote-Only Usage Recommended"

    This MCP server is designed for Linux systems. On Windows, **local execution will not work** for most tools since Windows lacks systemd, journalctl, and Linux-specific paths.

    **Supported use case:** Use Windows as a client to manage remote Linux servers via SSH.

    | Tool | Local (Windows) | Remote (Linux) |
    |------|-----------------|----------------|
    | `get_system_information` | ❌ Fails | ✅ Works |
    | `list_processes` | ❌ Fails | ✅ Works |
    | `list_services` | ❌ No systemd | ✅ Works |
    | `get_journal_logs` | ❌ No journald | ✅ Works |
    | All other tools | ❌ Fails | ✅ Works |

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

