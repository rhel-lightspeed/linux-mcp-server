# Installation Guide

Get the Linux MCP Server running quickly with your favorite MCP client.

!!! note "Architecture Requirement"
    This setup requires a **Control System**, where the MCP server and AI assistant run, and a **Target System** - the Linux system you wish to troubleshoot, which can be the same system or a remote host accessed via SSH.

    Local execution (without SSH) is only supported on Linux.

---

## Install with uv (Recommended)

[uv](https://docs.astral.sh/uv/) is a fast Python package manager that handles Python installation automatically.

1. [Install uv](https://docs.astral.sh/uv/getting-started/installation/)

2. Install `linux-mcp-server`:

    ```bash
    uv tool install linux-mcp-server
    ```

3. Verify installation:

    ```bash
    linux-mcp-server --version
    ```

!!! tip
    If the command is not found, run `uv tool update-shell` to add `~/.local/bin` to your PATH, then restart your shell.

!!! note
    It is not necessary to run `linux-mcp-server` directly for normal use. The MCP client will handle starting and stopping the server.

!!! note "Optional dependencies"
    The `gssapi` package is needed for SSH authentication to Kerberos-registered systems. Install with `uv tool install linux-mcp-server[gssapi]`.

    The `gcp` optional dependency provides Google Cloud authentication for Vertex AI gatekeeper backends.
    Install with `uv tool install linux-mcp-server[gcp]`.

---

## Install from Fedora packages

On Fedora, the server is available as a system package:

```bash
sudo dnf install linux-mcp-server
```

---

## Run in a container

Instead of installing the Python code for linux-mcp-server directly on your system, you can run
the MCP server from a prebuilt container instead.  A container runtime such as [Podman](https://podman-desktop.io)
(recommended) or [Docker](https://docs.docker.com/desktop/) is required.

**Container image:**
```
quay.io/redhat-services-prod/rhel-lightspeed-tenant/linux-mcp-server:latest
```

### Container Setup (Podman)

Before running linux-mcp-server with podman, we need to create the directory where
the logs will be stored:

```bash
mkdir -p ~/.local/share/linux-mcp-server/logs
```

### Container Setup (Docker)

When running linux-mcp-server with docker, the container runs as a non-root user (UID 1001).
Files mounted from your host must be readable by this user.

The container needs access to your SSH keys for remote connections. You'll need to make a copy that is readable by the container:

```bash
# Create directories
mkdir -p ~/.local/share/linux-mcp-server/{logs,ssh}

# Copy your SSH keys/configs and set ownership (exact files will vary)
cp ~/.ssh/config ~/.local/share/linux-mcp-server/ssh/config
cp ~/.ssh/id_ed25519 ~/.local/share/linux-mcp-server/ssh
sudo chown -R 1001:1001 ~/.local/share/linux-mcp-server/
```

## Configuring your client

See [Client Configuration](clients.md) for specific examples. Make sure to modify the provided podman or docker command lines to have the correct paths.


---

## Next Steps

- **[SSH Configuration](ssh.md):** Set up SSH access to remote hosts
- **[Client Configuration](clients.md):** Configure your MCP client
- **[Troubleshooting](troubleshooting.md):** Solutions for common issues
