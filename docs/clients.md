# Client Configuration

Configure your MCP client - an AI application, to use the Linux MCP Server.

!!! tip "Environment Variables"
    Most configurations require environment variables for SSH connections and features. See the [Configuration Reference](config-reference.md) for the full list of options.

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

=== "uv (Recommended)"

    ```json
    {
      "mcpServers": {
        "linux-mcp-server": {
          "command": "/home/YOUR_USER/.local/bin/linux-mcp-server",
          "args": [],
          "env": {
            "LINUX_MCP_USER": "your-ssh-username"
          }
        }
      }
    }
    ```

=== "Container (stdio transport)"

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
            "-v", "/home/YOUR_USER/.ssh/config:/var/lib/mcp/.ssh/config:ro,Z",
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

=== "uv (Recommended)"

    ```json
    {
      "mcpServers": {
        "linux-diagnostics": {
          "command": "/home/YOUR_USER/.local/bin/linux-mcp-server",
          "args": [],
          "env": {
            "LINUX_MCP_ALLOWED_LOG_PATHS": "/var/log/messages,/var/log/lastlog"
          }
        }
      }
    }
    ```

=== "Container (stdio transport)"

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
            "-v", "/home/YOUR_USER/.ssh/config:/var/lib/mcp/.ssh/config:ro,Z",
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

=== "uv (Recommended)"

    ```toml
    [mcp_servers.linux-mcp-server]
    command = "/home/YOUR_USER/.local/bin/linux-mcp-server"
    args = []

    [mcp_servers.linux-mcp-server.env]
    LINUX_MCP_USER = "your-ssh-username"
    ```

=== "Container (stdio transport)"

    ```toml
    [mcp_servers.linux-mcp-server]
    command = "podman"
    args = [
      "run", "--rm", "--interactive",
      "--userns", "keep-id:uid=1001,gid=0",
      "-e", "LINUX_MCP_KEY_PASSPHRASE",
      "-e", "LINUX_MCP_USER",
      "-v", "/home/YOUR_USER/.ssh/id_ed25519:/var/lib/mcp/.ssh/id_ed25519:ro,Z",
      "-v", "/home/YOUR_USER/.ssh/config:/var/lib/mcp/.ssh/config:ro,Z",
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

=== "uv (Recommended)"

    ```json
    {
      "mcpServers": {
        "linux-mcp-server": {
          "command": "/home/YOUR_USER/.local/bin/linux-mcp-server",
          "args": [],
          "env": {
            "LINUX_MCP_USER": "your-ssh-username"
          }
        }
      }
    }
    ```

=== "Container (stdio transport)"

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
            "-v", "/home/YOUR_USER/.ssh/config:/var/lib/mcp/.ssh/config:ro,Z",
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

=== "uv (Recommended)"

    ```json
    {
      "mcpServers": {
        "linux-mcp-server": {
          "command": "/home/YOUR_USER/.local/bin/linux-mcp-server",
          "args": [],
          "env": {
            "LINUX_MCP_USER": "your-ssh-username"
          }
        }
      }
    }
    ```

    !!! note "Merging with Existing Settings"
        If you have other settings in your `settings.json`, add the `mcpServers` object alongside them.

=== "Container (stdio transport)"

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
            "-v", "/home/YOUR_USER/.ssh/config:/var/lib/mcp/.ssh/config:ro,Z",
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

[Goose](https://block.github.io/goose/) is Block's open-source AI agent. You can configure extensions via the GUI wizard or by editing the YAML config file directly.



### GUI Wizard (Desktop App)

The Goose desktop app provides a wizard for adding extensions:

1. Open Goose and click the **three dots menu** (⋯) in the top-right corner
2. Select **Settings** → **Extensions**
3. Click **Add custom extension**
4. Fill in the fields:

    | Field | Value |
    |-------|-------|
    | **Type** | `Standard IO` |
    | **ID** | `linux-tools` |
    | **Name** | `linux-tools` |
    | **Description** | `Linux system diagnostics` |
    | **Command** | `/home/YOUR_USER/.local/bin/linux-mcp-server` |
    | **Arguments** | *(leave empty)* |
    | **Environment Variables** | `LINUX_MCP_USER=your-ssh-username` |

5. Click **Add** to save the extension

!!! tip "Container Installation"
    For container-based installs, set **Command** to `podman` and add the container arguments in the **Arguments** field (one per line).

### YAML Configuration (CLI)

If you prefer editing config files directly, add to `~/.config/goose/config.yaml`:

=== "uv (Recommended)"

    ```yaml
    extensions:
      linux-tools:
        enabled: true
        type: stdio
        name: linux-tools
        description: Linux tools
        cmd: /home/YOUR_USER/.local/bin/linux-mcp-server
        envs: {}
        env_keys:
          - LINUX_MCP_KEY_PASSPHRASE
          - LINUX_MCP_USER
        timeout: 30
        bundled: null
        available_tools: []
        args: []
    ```

=== "Container (stdio transport)"

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
          - /home/YOUR_USER/.ssh/config:/var/lib/mcp/.ssh/config:ro,Z
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
=== "HTTP transport"

    !!! warning "HTTP Transport Security"
        The HTTP transport does not currently have authentication. It should not be used in production or on untrusted networks.

    !!! note
        `linux-mcp-server` must be started separately when using HTTP transport.

    ```yaml
    extensions:
      linux-tools-http:
        enabled: true
        type: streamable_http
        name: linux-tools-http
        description: Linux Tools HTTP
        uri: http://localhost:8000/mcp
        envs: {}
        env_keys: []
        headers: {}
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

=== "uv (Recommended)"

    ```json
    {
      "$schema": "https://opencode.ai/config.json",
      "mcp": {
        "linux-mcp-server": {
          "type": "local",
          "command": ["/home/YOUR_USER/.local/bin/linux-mcp-server"],
          "enabled": true,
          "env": {
            "LINUX_MCP_USER": "your-ssh-username"
          }
        }
      }
    }
    ```

=== "Container (stdio transport)"

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
            "-v", "/home/YOUR_USER/.ssh/config:/var/lib/mcp/.ssh/config:ro,Z",
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

Add to your VS Code `mcp.json`:

=== "uv (Recommended)"

    ```json
    {
      "servers": {
        "linux-mcp-server": {
          "command": "/home/YOUR_USER/.local/bin/linux-mcp-server",
          "args": [],
          "env": {
            "LINUX_MCP_USER": "your-ssh-username"
          }
        }
      }
    }
    ```

=== "Container (stdio transport)"

    ```json
    {
      "servers": {
        "linux-mcp-server": {
          "command": "podman",
          "args": [
            "run", "--rm", "--interactive",
            "--userns", "keep-id:uid=1001,gid=0",
            "-e", "LINUX_MCP_KEY_PASSPHRASE",
            "-e", "LINUX_MCP_USER",
            "-v", "/home/YOUR_USER/.ssh/id_ed25519:/var/lib/mcp/.ssh/id_ed25519:ro,Z",
            "-v", "/home/YOUR_USER/.ssh/config:/var/lib/mcp/.ssh/config:ro,Z",
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

!!! tip
    Use the command palette (`Ctrl+Shift+P`) and search for "MCP" to manage servers.

---

## Windsurf

[Windsurf](https://codeium.com/windsurf) is Codeium's AI-powered IDE.

### Configuration

Edit `~/.codeium/windsurf/mcp_config.json`:

=== "uv (Recommended)"

    ```json
    {
      "mcpServers": {
        "linux-mcp-server": {
          "command": "/home/YOUR_USER/.local/bin/linux-mcp-server",
          "args": [],
          "env": {
            "LINUX_MCP_USER": "your-ssh-username"
          }
        }
      }
    }
    ```

=== "Container (stdio transport)"

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
            "-v", "/home/YOUR_USER/.ssh/config:/var/lib/mcp/.ssh/config:ro,Z",
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

## Other MCP Clients

The Linux MCP Server works with any MCP-compatible client. The general configuration pattern is:

1. **Command**: Path to `linux-mcp-server` executable (or `podman`/`docker` for container)
2. **Arguments**: Empty for native install, or container run arguments
3. **Environment**: Set variables as needed (see [Configuration Reference](config-reference.md))

Refer to your client's documentation for the specific configuration format.
