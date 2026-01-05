# Client Configuration

Configure your MCP client to use the Linux MCP Server.

!!! tip "Environment Variables"
    Most configurations require environment variables for SSH connections and features. See [Environment Variables](#environment-variables) for the full reference.

**MCP Client Configuration Examples**

- [Claude Code](#claude-code)
- [Claude Desktop](#claude-desktop)
- [Codex](#codex)
- [Cursor](#cursor)
- [Gemini CLI](#gemini-cli)
- [Goose](#goose)
- [opencode](#opencode)
- [VS Code / Copilot](#vs-code-copilot)
- [Windsurf](#windsurf)

---

## Claude Code

[Claude Code](https://docs.anthropic.com/en/docs/claude-code) is Anthropic's official CLI tool.

### Configuration

Edit `~/.claude.json`:

=== "pip/uv (Recommended)"

    ```json
    {
      "mcpServers": {
        "linux-mcp-server": {
          "command": "~/.local/bin/linux-mcp-server",
          "args": [],
          "env": {
            "LINUX_MCP_USER": "your-ssh-username"
          }
        }
      }
    }
    ```

=== "Container (Podman)"

    ```json
    {
      "mcpServers": {
        "linux-mcp-server": {
          "command": "podman",
          "args": [
            "run", "--rm", "--interactive",
            "--userns", "keep-id:uid=1001,gid=0",
            "-e", "LINUX_MCP_KEY_PASSPHRASE",
            "-e", "LINUX_MCP_USER",
            "-v", "/home/YOUR_USER/.ssh/id_ed25519:/var/lib/mcp/.ssh/id_ed25519:ro,Z",
            "-v", "/home/YOUR_USER/.local/share/linux-mcp-server/logs:/var/lib/mcp/.local/share/linux-mcp-server/logs:rw,Z",
            "quay.io/redhat-services-prod/rhel-lightspeed-tenant/linux-mcp-server:latest"
          ],
          "env": {
            "LINUX_MCP_KEY_PASSPHRASE": "<secret>",
            "LINUX_MCP_USER": "YOUR_USER"
          }
        }
      }
    }
    ```

    !!! warning "Replace Paths"
        Replace `YOUR_USER` with your actual username.

---

## Claude Desktop

### Configuration File Location

Edit your Claude Desktop configuration file:

- **Linux:** `~/.config/Claude/claude_desktop_config.json`
- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

### Configuration Examples

The value for `command` will vary depending on how `linux-mcp-server` was installed.

=== "pip (Recommended)"

    ```json
    {
      "mcpServers": {
        "linux-diagnostics": {
          "command": "~/.local/bin/linux-mcp-server",
          "args": [],
          "env": {
            "LINUX_MCP_ALLOWED_LOG_PATHS": "/var/log/messages,/var/log/secure,/var/log/audit/audit.log"
          }
        }
      }
    }
    ```

=== "uv"

    ```json
    {
      "mcpServers": {
        "linux-diagnostics": {
          "command": "~/.local/bin/linux-mcp-server",
          "args": [],
          "env": {
            "LINUX_MCP_ALLOWED_LOG_PATHS": "/var/log/messages,/var/log/secure,/var/log/audit/audit.log"
          }
        }
      }
    }
    ```

=== "Container (Podman)"

    ```json
    {
      "mcpServers": {
        "Linux Tools": {
          "command": "podman",
          "args": [
            "run",
            "--rm",
            "--interactive",
            "--userns", "keep-id:uid=1001,gid=0",
            "-e", "LINUX_MCP_KEY_PASSPHRASE",
            "-e", "LINUX_MCP_USER",
            "-v", "/home/YOUR_USER/.ssh/id_ed25519:/var/lib/mcp/.ssh/id_ed25519:ro,Z",
            "-v", "/home/YOUR_USER/.local/share/linux-mcp-server/logs:/var/lib/mcp/.local/share/linux-mcp-server/logs:rw,Z",
            "quay.io/redhat-services-prod/rhel-lightspeed-tenant/linux-mcp-server:latest"
          ],
          "env": {
            "LINUX_MCP_KEY_PASSPHRASE": "<secret>",
            "LINUX_MCP_USER": "YOUR_USER"
          }
        }
      }
    }
    ```

    !!! warning "Replace Paths"
        Replace `YOUR_USER` with your actual username and adjust paths as needed.

### Applying Configuration Changes

After editing the configuration file:

1. **Restart Claude Desktop** completely (quit and relaunch)
2. Look for the MCP server indicator in Claude Desktop
3. The server should appear in the list of available tools

---

## Codex

[Codex](https://github.com/openai/codex) is OpenAI's CLI tool.

### Configuration

Edit `~/.codex/config.toml`:

=== "pip/uv (Recommended)"

    ```toml
    [mcp_servers.linux-mcp-server]
    command = "~/.local/bin/linux-mcp-server"
    args = []

    [mcp_servers.linux-mcp-server.env]
    LINUX_MCP_USER = "your-ssh-username"
    ```

=== "Container (Podman)"

    ```toml
    [mcp_servers.linux-mcp-server]
    command = "podman"
    args = [
      "run", "--rm", "--interactive",
      "--userns", "keep-id:uid=1001,gid=0",
      "-e", "LINUX_MCP_KEY_PASSPHRASE",
      "-e", "LINUX_MCP_USER",
      "-v", "/home/YOUR_USER/.ssh/id_ed25519:/var/lib/mcp/.ssh/id_ed25519:ro,Z",
      "-v", "/home/YOUR_USER/.local/share/linux-mcp-server/logs:/var/lib/mcp/.local/share/linux-mcp-server/logs:rw,Z",
      "quay.io/redhat-services-prod/rhel-lightspeed-tenant/linux-mcp-server:latest"
    ]

    [mcp_servers.linux-mcp-server.env]
    LINUX_MCP_KEY_PASSPHRASE = "<secret>"
    LINUX_MCP_USER = "YOUR_USER"
    ```

    !!! warning "Replace Paths"
        Replace `YOUR_USER` with your actual username.

---

## Cursor

[Cursor](https://cursor.sh/) is an AI-powered code editor with MCP support.

### Configuration

Edit `~/.cursor/mcp.json`:

=== "pip/uv (Recommended)"

    ```json
    {
      "mcpServers": {
        "linux-mcp-server": {
          "command": "~/.local/bin/linux-mcp-server",
          "args": [],
          "env": {
            "LINUX_MCP_USER": "your-ssh-username"
          }
        }
      }
    }
    ```

=== "Container (Podman)"

    ```json
    {
      "mcpServers": {
        "linux-mcp-server": {
          "command": "podman",
          "args": [
            "run", "--rm", "--interactive",
            "--userns", "keep-id:uid=1001,gid=0",
            "-e", "LINUX_MCP_KEY_PASSPHRASE",
            "-e", "LINUX_MCP_USER",
            "-v", "/home/YOUR_USER/.ssh/id_ed25519:/var/lib/mcp/.ssh/id_ed25519:ro,Z",
            "-v", "/home/YOUR_USER/.local/share/linux-mcp-server/logs:/var/lib/mcp/.local/share/linux-mcp-server/logs:rw,Z",
            "quay.io/redhat-services-prod/rhel-lightspeed-tenant/linux-mcp-server:latest"
          ],
          "env": {
            "LINUX_MCP_KEY_PASSPHRASE": "<secret>",
            "LINUX_MCP_USER": "YOUR_USER"
          }
        }
      }
    }
    ```

    !!! warning "Replace Paths"
        Replace `YOUR_USER` with your actual username.

---

## Gemini CLI

[Gemini CLI](https://github.com/google-gemini/gemini-cli) is Google's command-line tool for Gemini.

### Configuration

Edit `~/.gemini/settings.json`:

=== "pip/uv (Recommended)"

    ```json
    {
      "mcpServers": {
        "linux-mcp-server": {
          "command": "~/.local/bin/linux-mcp-server",
          "args": [],
          "env": {
            "LINUX_MCP_USER": "your-ssh-username"
          }
        }
      }
    }
    ```

=== "Container (Podman)"

    ```json
    {
      "mcpServers": {
        "linux-mcp-server": {
          "command": "podman",
          "args": [
            "run", "--rm", "--interactive",
            "--userns", "keep-id:uid=1001,gid=0",
            "-e", "LINUX_MCP_KEY_PASSPHRASE",
            "-e", "LINUX_MCP_USER",
            "-v", "/home/YOUR_USER/.ssh/id_ed25519:/var/lib/mcp/.ssh/id_ed25519:ro,Z",
            "-v", "/home/YOUR_USER/.local/share/linux-mcp-server/logs:/var/lib/mcp/.local/share/linux-mcp-server/logs:rw,Z",
            "quay.io/redhat-services-prod/rhel-lightspeed-tenant/linux-mcp-server:latest"
          ],
          "env": {
            "LINUX_MCP_KEY_PASSPHRASE": "<secret>",
            "LINUX_MCP_USER": "YOUR_USER"
          }
        }
      }
    }
    ```

    !!! warning "Replace Paths"
        Replace `YOUR_USER` with your actual username.

---

## Goose

[Goose](https://block.github.io/goose/) is Block's open-source AI agent.

### Configuration Examples

=== "pip/uv (Recommended)"

    ```yaml
    extensions:
      linux-tools:
        enabled: true
        type: stdio
        name: linux-tools
        description: Linux tools
        cmd: ~/.local/bin/linux-mcp-server
        envs: {}
        env_keys:
          - LINUX_MCP_KEY_PASSPHRASE
          - LINUX_MCP_USER
        timeout: 30
        bundled: null
        available_tools: []
    ```

=== "Container (Podman)"

    ```yaml
    extensions:
      linux-tools:
        enabled: true
        type: stdio
        name: linux-tools
        description: Linux tools
        cmd: podman
        args:
          - run
          - --rm
          - --interactive
          - --userns
          - "keep-id:uid=1001,gid=0"
          - -e
          - LINUX_MCP_KEY_PASSPHRASE
          - -e
          - LINUX_MCP_USER
          - -v
          - /home/YOUR_USER/.ssh/id_ed25519:/var/lib/mcp/.ssh/id_ed25519:ro
          - -v
          - /home/YOUR_USER/.local/share/linux-mcp-server/logs:/var/lib/mcp/.local/share/linux-mcp-server/logs:rw
          - quay.io/redhat-services-prod/rhel-lightspeed-tenant/linux-mcp-server:latest
        envs: {}
        env_keys:
          - LINUX_MCP_KEY_PASSPHRASE
          - LINUX_MCP_USER
        timeout: 30
        bundled: null
        available_tools: []
    ```

    !!! warning "Replace Paths"
        Replace `YOUR_USER` with your actual username and adjust paths as needed.

---

## opencode

[opencode](https://opencode.ai/) is an AI-powered terminal coding assistant.

### Configuration

Edit `~/.config/opencode/opencode.json`:

=== "pip/uv (Recommended)"

    ```json
    {
      "$schema": "https://opencode.ai/config.json",
      "mcp": {
        "linux-mcp-server": {
          "type": "local",
          "command": ["~/.local/bin/linux-mcp-server"],
          "enabled": true,
          "env": {
            "LINUX_MCP_USER": "your-ssh-username"
          }
        }
      }
    }
    ```

=== "Container (Podman)"

    ```json
    {
      "$schema": "https://opencode.ai/config.json",
      "mcp": {
        "linux-mcp-server": {
          "type": "local",
          "command": [
            "podman", "run", "--rm", "--interactive",
            "--userns", "keep-id:uid=1001,gid=0",
            "-e", "LINUX_MCP_KEY_PASSPHRASE",
            "-e", "LINUX_MCP_USER",
            "-v", "/home/YOUR_USER/.ssh/id_ed25519:/var/lib/mcp/.ssh/id_ed25519:ro,Z",
            "-v", "/home/YOUR_USER/.local/share/linux-mcp-server/logs:/var/lib/mcp/.local/share/linux-mcp-server/logs:rw,Z",
            "quay.io/redhat-services-prod/rhel-lightspeed-tenant/linux-mcp-server:latest"
          ],
          "enabled": true,
          "env": {
            "LINUX_MCP_KEY_PASSPHRASE": "<secret>",
            "LINUX_MCP_USER": "YOUR_USER"
          }
        }
      }
    }
    ```

    !!! warning "Replace Paths"
        Replace `YOUR_USER` with your actual username.

---

## VS Code / Copilot

VS Code with GitHub Copilot supports MCP servers in agent mode.

### Configuration

Add to your VS Code `settings.json`:

=== "pip/uv (Recommended)"

    ```json
    {
      "mcp": {
        "servers": {
          "linux-mcp-server": {
            "command": "~/.local/bin/linux-mcp-server",
            "args": [],
            "env": {
              "LINUX_MCP_USER": "your-ssh-username"
            }
          }
        }
      }
    }
    ```

=== "Container (Podman)"

    ```json
    {
      "mcp": {
        "servers": {
          "linux-mcp-server": {
            "command": "podman",
            "args": [
              "run", "--rm", "--interactive",
              "--userns", "keep-id:uid=1001,gid=0",
              "-e", "LINUX_MCP_KEY_PASSPHRASE",
              "-e", "LINUX_MCP_USER",
              "-v", "/home/YOUR_USER/.ssh/id_ed25519:/var/lib/mcp/.ssh/id_ed25519:ro,Z",
              "-v", "/home/YOUR_USER/.local/share/linux-mcp-server/logs:/var/lib/mcp/.local/share/linux-mcp-server/logs:rw,Z",
              "quay.io/redhat-services-prod/rhel-lightspeed-tenant/linux-mcp-server:latest"
            ],
            "env": {
              "LINUX_MCP_KEY_PASSPHRASE": "<secret>",
              "LINUX_MCP_USER": "YOUR_USER"
            }
          }
        }
      }
    }
    ```

    !!! warning "Replace Paths"
        Replace `YOUR_USER` with your actual username.

!!! tip
    Use the command palette (`Ctrl+Shift+P`) and search for "MCP" to manage servers.

---

## Windsurf

[Windsurf](https://codeium.com/windsurf) is Codeium's AI-powered IDE.

### Configuration

Edit `~/.codeium/windsurf/mcp_config.json`:

=== "pip/uv (Recommended)"

    ```json
    {
      "mcpServers": {
        "linux-mcp-server": {
          "command": "~/.local/bin/linux-mcp-server",
          "args": [],
          "env": {
            "LINUX_MCP_USER": "your-ssh-username"
          }
        }
      }
    }
    ```

=== "Container (Podman)"

    ```json
    {
      "mcpServers": {
        "linux-mcp-server": {
          "command": "podman",
          "args": [
            "run", "--rm", "--interactive",
            "--userns", "keep-id:uid=1001,gid=0",
            "-e", "LINUX_MCP_KEY_PASSPHRASE",
            "-e", "LINUX_MCP_USER",
            "-v", "/home/YOUR_USER/.ssh/id_ed25519:/var/lib/mcp/.ssh/id_ed25519:ro,Z",
            "-v", "/home/YOUR_USER/.local/share/linux-mcp-server/logs:/var/lib/mcp/.local/share/linux-mcp-server/logs:rw,Z",
            "quay.io/redhat-services-prod/rhel-lightspeed-tenant/linux-mcp-server:latest"
          ],
          "env": {
            "LINUX_MCP_KEY_PASSPHRASE": "<secret>",
            "LINUX_MCP_USER": "YOUR_USER"
          }
        }
      }
    }
    ```

    !!! warning "Replace Paths"
        Replace `YOUR_USER` with your actual username.

---

## Environment Variables

Configure these environment variables in the `env` section of your client configuration.

### SSH Connection Settings

| Variable | Description | Example |
|----------|-------------|---------|
| `LINUX_MCP_USER` | Default username for SSH connections | `admin` |
| `LINUX_MCP_SSH_KEY_PATH` | Path to SSH private key | `~/.ssh/id_ed25519` |
| `LINUX_MCP_KEY_PASSPHRASE` | Passphrase for encrypted SSH key | (set value in env) |
| `LINUX_MCP_SEARCH_FOR_SSH_KEY` | Auto-discover keys in `~/.ssh` | `yes` |
| `LINUX_MCP_COMMAND_TIMEOUT` | SSH command timeout in seconds (default: 30) | `60` |

### SSH Security Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `LINUX_MCP_VERIFY_HOST_KEYS` | `False` | Verify remote host identity via known_hosts |
| `LINUX_MCP_KNOWN_HOSTS_PATH` | (none) | Custom path to known_hosts file |

### Feature-Specific Settings

| Variable | Required For | Description | Example |
|----------|--------------|-------------|---------|
| `LINUX_MCP_ALLOWED_LOG_PATHS` | `read_log_file` tool | Comma-separated allowlist of log files | `/var/log/messages,/var/log/secure` |

### Logging Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `LINUX_MCP_LOG_DIR` | `~/.local/share/linux-mcp-server/logs` | Server log directory |
| `LINUX_MCP_LOG_LEVEL` | `INFO` | Log verbosity (`DEBUG`, `INFO`, `WARNING`) |
| `LINUX_MCP_LOG_RETENTION_DAYS` | `10` | Days to keep log files |

---

## Other MCP Clients

The Linux MCP Server works with any MCP-compatible client. The general configuration pattern is:

1. **Command**: Path to `linux-mcp-server` executable (or `podman`/`docker` for container)
2. **Arguments**: Empty for native install, or container run arguments
3. **Environment**: Set variables from the table above as needed

Refer to your client's documentation for the specific configuration format.
