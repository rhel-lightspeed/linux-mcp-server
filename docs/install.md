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

    The `gcp` package is needed for Google Cloud Platform integration with the gatekeeper model. Install with `uv tool install linux-mcp-server[gcp]`.

---

## Install from Fedora packages

On Fedora, the server is available as a system package:

```bash
sudo dnf install linux-mcp-server
```

---

## Run in a container (Podman)

A container runtime such as [Podman](https://podman-desktop.io) is required.

**Container image:**
```
quay.io/redhat-services-prod/rhel-lightspeed-tenant/linux-mcp-server:latest
```

See [Client Configuration](clients.md) for examples of how to run the container using stdio transport.

When using an HTTP transport, the container must be started before launching the MCP client:

```bash
podman run --rm --interactive \
  --userns "keep-id:uid=1001,gid=0" \
  --port 8000:8000 \
  -e LINUX_MCP_KEY_PASSPHRASE \
  -e LINUX_MCP_TRANSPORT=http \
  -e LINUX_MCP_HOST=0.0.0.0 \
  -v /home/YOUR_USER/.ssh/id_ed25519:/var/lib/mcp/.ssh/id_ed25519:ro \
  -v /home/YOUR_USER/.ssh/config:/var/lib/mcp/.ssh/config:ro,Z \
  -v /home/YOUR_USER/.local/share/linux-mcp-server/logs:/var/lib/mcp/.local/share/linux-mcp-server/logs:rw \
  quay.io/redhat-services-prod/rhel-lightspeed-tenant/linux-mcp-server:latest
```

### Container Setup for SSH Keys

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


Once the SSH keys are configured, configure your [MCP client](clients.md) to run the container image. It is not necessary to run the container manually since the MCP client will do that.

---

## Next Steps

- **[SSH Configuration](ssh.md):** Set up SSH access to remote hosts
- **[Client Configuration](clients.md):** Configure your MCP client
- **[Troubleshooting](troubleshooting.md):** Solutions for common issues
