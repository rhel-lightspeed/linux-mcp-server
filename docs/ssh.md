# SSH Configuration

The Linux MCP Server uses SSH to execute commands on remote Linux systems. This page covers how to set up and manage SSH connections.

## Setup

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

## Specifying Remote Hosts

When using MCP tools, the `host` parameter may be a fully qualified domain name (FQDN), an alias from `~/.ssh/config`, or an IP address.

## Per-Host Configuration

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

## Managing Host Keys

The Linux MCP Server enables SSH host key checking by default. Checking host keys guards against server spoofing and man-in-the-middle attacks but does require some additional setup and maintenance.

If a host is not yet in `known_hosts`, the connection will fail because there is no interactive prompt to accept the key.

If a host key changes, SSH connections will fail until the key is corrected in the `known_hosts` file.

### Adding Host Keys

To ensure the host's key is in the `known_hosts` file, connect to the host once:

```bash
ssh user@hostname
```

Accept the host key when prompted. This adds the key to `~/.ssh/known_hosts`, which is the default location the MCP server checks.

You can also add host keys without an interactive prompt using `ssh-keyscan`:

```bash
ssh-keyscan hostname >> ~/.ssh/known_hosts
```

!!! warning
    Using `ssh-keyscan` does not validate the authenticity of the host key. Only use this on trusted networks or verify the key fingerprint through an out-of-band channel.

### Using a Custom known_hosts File

By default, the server uses `~/.ssh/known_hosts`. To specify a different file:

```bash
linux-mcp-server --known-hosts-path /path/to/known_hosts
```

Or set the environment variable:

```bash
export LINUX_MCP_KNOWN_HOSTS_PATH=/path/to/known_hosts
```

### Disabling Host Key Checking

If you understand the implications and wish to disable host key checking, you can do so with a command line option:

```bash
linux-mcp-server --no-verify-host-keys
```

Or environment variable:

```bash
export LINUX_MCP_VERIFY_HOST_KEYS=false
```

!!! danger
    Disabling host key verification makes SSH connections vulnerable to man-in-the-middle attacks. Only disable this in trusted network environments such as isolated development or test networks.
