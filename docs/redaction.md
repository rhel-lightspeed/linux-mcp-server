# Redaction

linux-mcp-server has a simple redaction system that scans what tools return before it reaches the chat model.
It applies to the fixed tools and to [Guarded Command Execution](guarded-command-execution.md) alike.
Its goal is to keep certain kinds of information on the target system from being sent to the model.

There are several kinds of information you might not want returned to the chat model:

* **Credentials** - passwords, API keys, tokens, private keys.
  These are what the built-in rules cover.
* **Personally Identifiable Information (PII)** - email addresses, phone numbers, identifying numbers.
  ***No built-in rules*** - PII is prone to false positives and rarely appears in typical sysadmin output.
  You can add [custom rules](#custom-rules) for the forms that matter to you.
* **Prompt injection** - text that an attacker plants in the output to influence the model.
  ***Not handled*** - this is better filtered by the chat client or at the inference layer.
* **Sensitive or confidential information.**
  ***Not handled*** - recognizing it needs site-specific knowledge that linux-mcp-server doesn't have,
  as well as more sophisticated text handling than regular expressions.

Even for credentials, the built-in rules are necessarily far from complete.
***It is the responsibility of the administrator to put sufficient data protections in place for their LLM usage.***

## How it works

Redaction matches a set of regular expressions against the text a tool returns,
and replaces each matched string with a placeholder naming the rule that matched:

```text
$ echo 'password=hunter2' | linux-mcp-server --redact-test
password=[REDACTED:builtin:credentials:generic_key_value]
Matched rules:
  line 1: builtin:credentials:generic_key_value: 'password=hunter2'
```

A rule with capturing groups replaces only what its groups matched, so the surrounding context
(`password=` above) is kept and the model can still tell what was there.
A rule without capturing groups replaces the whole match.

Redaction is applied to:

* **Tool results.** Everything a tool returns is scanned, both the text content and the structured content.
  For structured content each string value is scanned separately; keys are left alone.
* **Error messages.** A tool's error message often quotes the output it was reading, so it is scanned too,
  and the [audit log](debugging.md) records the redacted message that the client sees.

## Configuration

| Option / Env Var | Default | Description |
|------------------|---------|-------------|
| `--redaction.enabled`<br>`LINUX_MCP_REDACTION__ENABLED` | `true` | If `false`, redaction is turned off entirely |
| `--redaction.rules-path`<br>`LINUX_MCP_REDACTION__RULES_PATH` | _(none)_ | Path to a YAML [rules file](#rules-file) customizing the rules |

With no rules file, only the [built-in rules](#built-in-rules) are used.

The rules file is read when the server starts. If it is missing or invalid, the server does not start,
so that a mistake in the file can't silently leave output unredacted.
Use [`--redact-list`](#checking-rules) to check a rules file before deploying it.

## Built-in rules

All built-in rules are enabled by default.

| Rule | Matches |
|------|---------|
| `builtin:credentials:generic_key_value` | `key=value` and `key: value` (ini files, JSON, YAML, shell assignments) where the key ends with `password`, `passwd`, `pwd`, `secret`, `token`, `key` or `credential` |
| `builtin:credentials:command_line_password` | Passwords given as command line arguments, as they appear in `ps` output: `--password <value>`, `--password=<value>`, `-p<value>` |
| `builtin:credentials:url_credentials` | Passwords embedded in URLs: `https://<user>:<password>@host` |
| `builtin:credentials:authorization_header` | `Authorization: Bearer <token>` and `Authorization: Basic <credentials>` header values |
| `builtin:credentials:pem_private_key` | PEM-encoded private key blocks, from `-----BEGIN ... PRIVATE KEY-----` to the matching footer |
| `builtin:credentials:gcp_key` | GCP service account private keys and GCP API keys |
| `builtin:credentials:azure:storage_connection_string` | `AccountKey` and `SharedAccessSignature` values in Azure storage connection strings |
| `builtin:credentials:jwt` | JSON Web Tokens |

`linux-mcp-server --redact-list` shows the exact pattern of each rule.

!!! note
    The set of built-in rules is not stable yet, and rules may be added, renamed or split up between releases.
    After upgrading, check the active rules with `--redact-list`.

## Rules file

A rules file adds rules of your own and turns built-in rules off or on.

```yaml
version: 1

disable_rules:
  # Turn off specific built-in rules
  - builtin:credentials:jwt
  # Wildcards are supported
  - builtin:credentials:azure:*

enable_rules:
  # Turn a rule back on that a broader pattern in disable_rules turned off
  - builtin:credentials:azure:storage_connection_string

rules:
  # Custom rules
  - name: hushhush
    description: Don't leak the secret word
    # Only the capturing group is replaced, so this produces hushhush = "[REDACTED:custom:hushhush]"
    match: 'hushhush\s*=\s*"(.*?)"'
  - name: employee_id
    description: Employee ID numbers
    # No capturing group, so the whole match is replaced
    match: '\bEMP-\d{6}\b'
```

| Key | Description |
|-----|-------------|
| `version` | Required. Must be `1`. |
| `disable_rules` | Names of rules to turn off. |
| `enable_rules` | Names of rules to turn on. |
| `rules` | Custom rules to add, each with a `name`, `description` and `match` pattern. |

### Enabling and disabling rules

Entries in `disable_rules` and `enable_rules` are rule names, which may contain `*` wildcards,
such as `builtin:credentials:*` or `custom:*`.
Each entry must match at least one rule, so that a misspelled name is reported rather than ignored.

When a rule is matched by entries in both lists, the most specific one wins.
This lets you turn off a whole group of rules and turn one of them back on, as in the example above.

All rules are on unless disabled, so `enable_rules` is currently only useful together with a broader entry in `disable_rules`.

### Custom rules

Custom rule names may contain letters, digits, `_`, `-`, `.` and `:`, and are given a `custom:` prefix -
the `hushhush` rule above is reported as `custom:hushhush`, and is disabled with `custom:hushhush`.

The `match` pattern is a [Python regular expression](https://docs.python.org/3/library/re.html#regular-expression-syntax).
Some things to keep in mind:

* **Capturing groups decide what is replaced.** Every capturing group is replaced with the placeholder,
  or the whole match if the pattern has no groups. Write groups that should stay in the output as `(?:...)`.
* **`.` matches newlines.** All rules are combined into one pattern compiled with `re.DOTALL` and `re.MULTILINE`,
  so `.*` can run on across many lines. Use a lazy `.*?`, or `[^\n]*`, to stay on one line.
* **Some patterns are rejected:** patterns that can match an empty string, backreferences such as `\1`,
  and conditional patterns. Combining the rules renumbers their groups, so a reference by number would point at the wrong group.
  Inline flags such as `(?i)` are fine.
* **Put patterns in single quotes in YAML**, so that backslashes don't need to be doubled.
* **Overlapping rules:** the text is scanned once, left to right, and matches never overlap.
  If more than one rule matches at the same position, which one applies is unspecified.

## Checking rules

Two options check the rules without starting the server.
They use the same redaction settings as the server, so give them the same `--redaction.*` options or `LINUX_MCP_REDACTION__*` variables.

* `--redact-list` lists the active rules, with each rule's description and pattern.
* `--redact-test` redacts standard input. The redacted text is printed to standard output,
  and the rules that matched, with line numbers and what they matched, to standard error.

```bash
linux-mcp-server --redact-list
linux-mcp-server --redaction.rules-path ./redaction.yaml --redact-test < /etc/myapp.conf
echo 'password=hunter2' | linux-mcp-server --redact-test
```

For example, with the rules file above:

```text
$ printf 'hushhush = "swordfish"\nowner EMP-123456\nmysql -u root -psecret\n' | \
    linux-mcp-server --redaction.rules-path ./redaction.yaml --redact-test
hushhush = "[REDACTED:custom:hushhush]"
owner [REDACTED:custom:employee_id]
mysql -u root -p[REDACTED:builtin:credentials:command_line_password]
Matched rules:
  line 1: custom:hushhush: 'hushhush = "swordfish"'
  line 2: custom:employee_id: 'EMP-123456'
  line 3: builtin:credentials:command_line_password: ' -psecret'
```

An invalid rules file, or redaction being turned off, gives an error message and exit status 1.

The container image runs `linux-mcp-server` as its entrypoint, so the same options work there:

```bash
echo 'password=hunter2' | podman run --rm -i quay.io/redhat-services-prod/rhel-lightspeed-tenant/linux-mcp-server:latest --redact-test
```

To test a rules file with the container, mount it and point `--redaction.rules-path` at it:

```bash
podman run --rm -i -v ./redaction.yaml:/redaction.yaml:ro,Z \
    quay.io/redhat-services-prod/rhel-lightspeed-tenant/linux-mcp-server:latest \
    --redaction.rules-path /redaction.yaml --redact-list
```

## Limitations

* **Regular expressions only.** Redaction does not use NLP or a model to recognize sensitive data.
  It won't catch a secret in a form no rule describes, and won't catch deliberate obfuscation,
  such as a script that base64-encodes a file before printing it.
* **Each string is scanned on its own.** In structured content, a secret that is split across fields isn't seen as a whole,
  and a rule can't use a field name as context for the value next to it.
* **What the model sends is not redacted.** Tool arguments, including scripts written for Guarded Command Execution,
  are sent to the gatekeeper model and written to the [audit log](debugging.md) as supplied,
  apart from parameters whose names mark them as sensitive.
* **Some failures are logged unredacted.** When a tool fails with an unexpected exception, or scanning itself fails,
  the traceback is written to the server log as it is, so that the problem can be diagnosed.
  The client is still only sent the redacted message.

For stronger protection, consider filtering in the chat client, at the inference layer, or in an MCP gateway in front of linux-mcp-server.
