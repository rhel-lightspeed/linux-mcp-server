"""The --redact-list and --redact-test commands, for checking redaction rules.

They build the engine from the same configuration as the server, so what they show is
what the server would do with the same settings.
"""

import sys

from linux_mcp_server.config import Config
from linux_mcp_server.redaction.engine import create_redaction_engine
from linux_mcp_server.redaction.engine import RedactionEngine


# Longer matches, like PEM private keys, are cut short when reporting what matched.
MAX_MATCH_PREVIEW = 60


def run(config: Config) -> int:
    """Run --redact-list or --redact-test, returning the exit status."""
    if config.redact_list and config.redact_test:
        return _fail("--redact-list and --redact-test can't be used together")

    try:
        engine = create_redaction_engine(config.redaction)
    except (OSError, ValueError) as e:
        return _fail(str(e))

    if engine is None:
        return _fail("redaction is disabled (LINUX_MCP_REDACTION__ENABLED)")

    if config.redact_list:
        return _list_rules(engine)

    return _test(engine, sys.stdin.read())


def _list_rules(engine: RedactionEngine) -> int:
    rules = engine.list_active_rules()
    if not rules:
        print("No redaction rules are active", file=sys.stderr)

    for rule in rules:
        print(rule["name"])
        print(f"    {rule['description']}")
        print(f"    {rule['pattern']}")

    return 0


def _test(engine: RedactionEngine, text: str) -> int:
    # The redacted text goes to standard output and the report to standard error, so
    # that the redacted text can be redirected to a file on its own.
    redacted = engine.redact(text)
    print(redacted, end="" if redacted.endswith("\n") else "\n")

    matches = engine.find_matches(text)
    if not matches:
        print("No rules matched", file=sys.stderr)
        return 0

    print("Matched rules:", file=sys.stderr)
    for match in matches:
        line = text.count("\n", 0, match.start) + 1
        preview = match.text
        if len(preview) > MAX_MATCH_PREVIEW:
            preview = preview[: MAX_MATCH_PREVIEW - 3] + "..."
        print(f"  line {line}: {match.rule}: {preview!r}", file=sys.stderr)

    return 0


def _fail(message: str) -> int:
    print(f"linux-mcp-server: {message}", file=sys.stderr)
    return 1
