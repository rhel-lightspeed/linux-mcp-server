# Guarded Command Execution

Guarded Command Execution is an **experimental** feature of linux-mcp-server.
When it is enabled (by setting `LINUX_MCP_TOOLSET` to `run_script` or `both`),
linux-mcp-server exposes additional tools that allow models
to provide a script to run on the target system,
instead of simply calling fixed, read-only tools.

This greatly increases the functionality of linux-mcp-server.
It allows models to use all their knowledge of Linux operating systems to diagnose and even fix problems on the target system.

However, along with the increased functionality,
comes a greater risk of "prompt injection" attacks.
In a prompt injection attack, an attacker disguises commands in data that the model reads, and tricks the model into doing something that the user doesn't intend.
To control these risks, when Guarded Command Execution is enabled,
there are multiple levels of guardrails enabled:

 * **Gatekeeper model**: A separate model called the Gatekeeper does an initial check of the command to make sure that it looks OK and matches the provided description.
 * **Human in the loop**: commands that modify the system are flagged for human approval. The human can review the description and optionally the exact command.
 * **Sandboxing**: When possible, the command is run in an OS-level sandbox with limited permissions. (NOTE: sandboxing is currently rudimentary.)

## Step-by-step

1. The model calls the `validate_script` tool to check the script, passing in a human-readable description
2. linux-mcp-server uses the gatekeeper model to check that the script is safe.
3. if checks pass, the model calls `run_script` or `run_script_with_confirmation` to actually execute the script on the target machine.
4. If `run_script_with_confirmation` is required, the user is asked to approve the call.
5. The script is executed on the target machine, in an operating-system level sandbox if possible.

## The Gatekeeper Model

The gatekeeper model is simply a *user-provided* chat model.
It is given the script and a special prompt asking it to check the script. The model checks if the script:

* Matches the description
* Is read-only if that was specified by the model.
* Conforms to policy.
* Is clear and simple and written in an obvious, expected manner.
* Does not contain malicious code or introduce security vulnerabilities on the system.

Policy is currently hardcoded:

 * Software can only be installed from pre-configured repositories.
   No new repositories may be added.
 * Except for installing software from pre-configured repositories,
   nothing may be downloaded from the internet.

In the future,
administrators will be able to customize the policy to their particular needs.

The security of Guarded Command Execution depends
on configuring an appropriate gatekeeper model.

Some models that we have tested include:

| Model | Model Type | Score |
|------------|-------|--------|
| Claude Opus 4.6 | Frontier model | ?? |
| gpt-oss:120b | Datacenter | ?? |
| gpt-oss:20b  | Workstation |?? |

The scores come from the evaluation suite provided with the linux-mcp-server source code. If you use a different model,
running the evaluation suite is recommended.

The scores give an approximate sense of the capability of the model acting as a gatekeeper -
actual performance in real-world situations may vary.
Smaller models than those listed above are *not recommended*.

## Human In The Loop

To provide a better experience for the human approving the call:

 * The model provides a human readable description, and the gatekeeper model checks that it matches the script.
 * The user is only prompted to approve more dangerous commands (typically calls that modify the target system), but other commands can run non-interactively.
 * When possible a custom approval UI is embedded into the chat client using an [mcp-app](https://modelcontextprotocol.io/extensions/apps/).

When mcp-apps are available,
the server exposes `run_script_interactive`,
which uses a custom approval UI embedded in the chat client.
When mcp-apps are not available,
the server exposes `run_script_with_confirmation` instead,
which relies on the chat client's built-in confirmation mechanism.

## Configuring Guarded Command Execution

**Enable Guarded Command Execution**

Set `LINUX_MCP_TOOLSET` to `both` or `run_script`.

Three values are supported for `LINUX_MCP_TOOLSET`:

* **fixed**: only read-only tools with fixed functionality
* **run_script**: only the Guarded Command Execution tools.
* **both**: all the tools

**Note**: Running in `both` mode may not produce better results than `run_script` alone —
 everything can be done with the `run_script` tools,
 and the greater number of tools may confuse the AI agent.
 Try it both ways.

Example:

```sh
LINUX_MCP_TOOLSET=run_script
```

**Configure a Gatekeeper Model**

Set `LINUX_MCP_GATEKEEPER_MODEL` to the name of the model you want to use. Additional environment
variables may be needed to configure credentials. See the
[LiteLLM documentation](https://docs.litellm.ai/docs/providers) for details on how to configure your provider.

Example:

```sh
LINUX_MCP_GATEKEEPER_MODEL=openai/chatgpt-5.2
OPENAI_API_KEY=<....>
```


**Configure your client's tool policy**

The following three tools should be configured to be allowed without user confirmation:

* `validate_script`
* `run_script`
* `run_script_interactive` (used when mcp-apps are available)

The following tool should be configured to ask the user each time:

* `run_script_with_confirmation` (used when mcp-apps are unavailable)

!!! warning
    Setting `run_script_with_confirmation` to Always Allow is dangerous and not recommended.

Details of how to do this are client specific — it might be done through a config file,
or interactively when each tool is first called.


**Optional: configure a strict approval policy**

`LINUX_MCP_ALWAYS_CONFIRM_SCRIPTS=True` can be set to force *all* scripts to be run via `run_script_with_confirmation`, including read-only scripts.
This is not recommended — **it's better to let the user focus on higher risk approvals** and avoid "approval fatigue."

