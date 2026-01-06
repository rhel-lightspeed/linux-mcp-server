# Getting Started with Linux MCP Server

Welcome! This guide is designed for users who are new to the **Model Context Protocol (MCP)** or using AI agents for system administration.

## What is this?

Think of this setup as giving your AI assistant a pair of "hands" to interact with your Linux system safely.

- **The Brain (MCP Client):** This is the AI you talk to (like Claude Desktop, Cursor, or Goose). It understands your questions but can't touch your computer by default.
- **The Hands (MCP Server):** This is the **Linux MCP Server** (this project). It provides a set of safe, read-only tools that the AI can use to look at your system.
- **The Protocol (MCP):** The language they use to talk to each other.

When you ask: *"Why is my system slow?"*
1. The **Client** thinks: *"I should check CPU and memory."*
2. The **Client** asks the **Server**: *"Run `get_cpu_information` and `get_memory_information`."*
3. The **Server** runs those commands and sends the data back.
4. The **Client** reads the data and tells you: *"Your CPU is at 99% usage because of process 'ffmpeg'."*

---

## Step 1: Choose Your Client

You need an MCP-compatible client to use this server. There are many options available, including:

- **Claude Desktop**
- **Cursor**
- **Goose**
- **VS Code with Copilot**

See our **[Client Configuration Guide](clients.md)** for a full list of supported clients and download links.

---

## Step 2: Install the Server

You need Python installed on your system. Open your terminal and run:

```bash
pip install --user linux-mcp-server
```

*Note: If you see a "command not found" error later, you might need to add `~/.local/bin` to your PATH. See the [Installation Guide](install.md) for details.*

---

## Step 3: Connect Them

Once the server is installed, you need to configure your client to use it.

**👉 Go to the [Client Configuration Guide](clients.md)**

Find your specific client in the list and follow the instructions to add `linux-mcp-server` to your configuration.

Once configured, restart your client and come back here!

---

## Step 4: Your First Conversation

Now for the fun part! Open your client and try these prompts:

**Basic Check:**
> "What operating system and kernel version am I running?"

**Health Check:**
> "Check my system memory and disk usage. Is everything healthy?"

**Investigation:**
> "Are there any failed systemd services?"

**Deep Dive:**
> "Show me the last 10 error logs from the system journal."

---

## What's Next?

- **Explore Tools:** Check the [Cheatsheet](cheatsheet.md) for a quick reference of what you can do.
- **Go Remote:** Want to manage a remote server? Read about [SSH Configuration](install.md#ssh-configuration).
- **More Clients:** Using a different app? See [Client Configuration](clients.md).
