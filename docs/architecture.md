## Architecture Overview

```mermaid
graph TB
    Client["Client Layer<br/>MCP Client (e.g. Claude Desktop)"]

    subgraph Server["MCP Server"]
        FastMCP[FastMCP Server]

        subgraph Tools["Tool Categories"]
            direction LR
            subgraph Row1[" "]
                SystemInfo[System Info]
                Services[Services]
                Processes[Processes]
            end
            subgraph Row2[" "]
            Logs[Logs & Audit]
                Network[Network]
                Storage[Storage]
            end
        end

        Executor[SSH Executor]
        Logger[Audit Logger]
    end

    subgraph Targets["Execution Targets"]
        direction LR
        Local[Local System]
        Remote[Remote Hosts<br/>SSH]
    end

    Client -->|MCP Protocol| FastMCP
    FastMCP --> Tools
    Tools --> Executor
    Executor --> Targets

    FastMCP -.-> Logger
    Executor -.-> Logger

    style Client fill:#4a9eff,stroke:#2563eb,color:#fff
    style FastMCP fill:#f59e0b,stroke:#d97706,color:#fff
    style SystemInfo fill:#64748b,stroke:#475569,color:#fff
    style Services fill:#64748b,stroke:#475569,color:#fff
    style Processes fill:#64748b,stroke:#475569,color:#fff
    style Logs fill:#64748b,stroke:#475569,color:#fff
    style Network fill:#64748b,stroke:#475569,color:#fff
    style Storage fill:#64748b,stroke:#475569,color:#fff
    style Executor fill:#10b981,stroke:#059669,color:#fff
    style Logger fill:#8b5cf6,stroke:#7c3aed,color:#fff
    style Local fill:#eab308,stroke:#ca8a04,color:#fff
    style Remote fill:#eab308,stroke:#ca8a04,color:#fff
    style Row1 fill:none,stroke:none
    style Row2 fill:none,stroke:none
```

## Where Each Component Runs

Understanding where the **client**, **MCP server**, and **target Linux system** run is helpful for deployment and development alike.

| Component | Location | Description |
|-----------|----------|-------------|
| **Client** | User's machine | The MCP client (Cursor, Claude Desktop, Goose, etc.) runs on the machine where the user works. It spawns the Linux MCP Server as a **subprocess** and communicates over **stdio** (stdin/stdout) using the MCP protocol (JSON-RPC). |
| **MCP Server** | Same host as client, or in a container | The server process is started by the client (e.g. `linux-mcp-server` or `podman run ... linux-mcp-server`). With a native install it runs on the **same machine as the client**. With a container deploy it runs **inside the container** on that same machine. In both cases the server receives tool calls over stdio and performs command execution. |
| **Target Linux system** | Same host as client, or any host reachable via SSH | Commands are executed either **locally** on the same host where the MCP server is running (subprocess or container), or **remotely** on another machine. Remote execution is done by the server opening an **SSH connection from the server host to the target host** and running commands there. The client never talks to the target directly. |

This means:

- **Client ↔ Server**: Communication is **always** over stdio, using the MCP JSON-RPC protocol. The client does not connect to the target directly.
- **Server ↔ Target**: If `host` is omitted, execution is **local** (same host as the server). If `host` is set, the server **SSHs from its own host** to that host to run commands.
- **Containers**: When the server runs in a container, “local” means inside the container. Local execution can be disabled via the `disallow_local_execution_in_containers` decorator (tools then require a `host` parameter for remote SSH).

## Detailed Tool Call Flow

End-to-end flow of a single MCP tool call: from the client request through the server to command execution on the target, and back.

```mermaid
sequenceDiagram
    participant User
    participant Client as MCP Client<br/>(e.g. Cursor)
    participant LLM as LLM Service
    participant Server as MCP Server Process<br/>(same host or container)
    participant FastMCP as FastMCP
    participant Tool as Tool (e.g. get_system_information)
    participant Cmd as CommandSpec / COMMANDS
    participant Exec as execute_command
    participant Target as Target Linux System<br/>(local or remote)

    User->>Client: "What's my system info?"
    Client->>LLM: Send prompt request
    LLM->>Client: Decide to call tool
    Client->>Server: MCP JSON-RPC: tools/call get_system_information
    Note over Client,Server: stdio (stdin/stdout)

    Server->>FastMCP: Dispatch tool call
    FastMCP->>Tool: get_system_information(host=...)
    Tool->>Tool: @log_tool_call, @disallow_local_execution_in_containers
    Tool->>Cmd: get_command_group("system_info") etc.
    Tool->>Cmd: cmd.run(host=host) for each subcommand

    Cmd->>Exec: execute_command(command, host=host)

    alt host is None (local)
        Exec->>Target: asyncio.create_subprocess_exec (local)
        Note over Server,Target: Target = same host as server
    else host is set (remote)
        Exec->>Server: SSHConnectionManager.get_connection(host)
        Exec->>Target: conn.run(cmd) over SSH
        Note over Server,Target: Target = remote host
    end

    Target-->>Exec: return_code, stdout, stderr
    Exec-->>Cmd: return code, stdout, stderr
    Cmd-->>Tool: results
    Tool->>Tool: parse_*, format_*
    Tool-->>FastMCP: formatted string
    FastMCP-->>Server: MCP response
    Server-->>Client: JSON-RPC result
    Client->>LLM: Tool call result
    LLM->>Client: Inference completion
    Client->>User: Answer with system info
```

1. User asks a question in the MCP client (e.g. Cursor).
2. Client sends the prompt to the LLM; the LLM decides to call a tool.
3. Client sends MCP JSON-RPC `tools/call` (e.g. `get_system_information`) over **stdio** to the MCP server (same host or container).
4. FastMCP dispatches the call to the tool.
5. Tool runs decorators (`@log_tool_call`, `@disallow_local_execution_in_containers`), resolves commands via `CommandSpec`/`COMMANDS`, and invokes `cmd.run(host=host)` for each subcommand.
6. `execute_command` runs on the target: **local** (`asyncio.create_subprocess_exec` when `host` is omitted) or **remote** (SSH via `SSHConnectionManager` when `host` is set).
7. Target returns return code, stdout, and stderr to `execute_command`.
8. Results flow back: Exec → Cmd → Tool; tool parses and formats (e.g. `parse_*`, `format_*`).
9. Tool returns formatted string to FastMCP; server sends MCP response over stdio to the client.
10. Client passes the tool result to the LLM; LLM produces the answer; client presents it to the user.

