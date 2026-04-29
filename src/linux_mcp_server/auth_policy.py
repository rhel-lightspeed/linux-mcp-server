import fnmatch
import logging

from enum import Enum
from functools import cache
from pathlib import Path
from typing import Any

import yaml

from pydantic import BaseModel

from linux_mcp_server.config import CONFIG
from linux_mcp_server.toolset import get_toolset


logger = logging.getLogger("linux-mcp-server")


class PolicyAction(str, Enum):
    DENY = "deny"
    SSH_KEY = "ssh_key"
    SSH_DEFAULT = "ssh_default"
    LOCAL = "local"


class SSHKeyConfig(BaseModel):
    path: str
    user: str


class PolicyRule(BaseModel):
    host: str
    tools: list[str]
    claims: dict[str, Any]
    action: PolicyAction
    ssh_key: SSHKeyConfig | None = None
    allow_unauthorized: bool = False

    def matches_host(self, target_host: str | None) -> bool:
        # Wildcards can match both local (None) and remote hosts
        # The action field determines whether execution is local or SSH
        if target_host is None:
            target_host = "localhost"
        return fnmatch.fnmatch(target_host, self.host)

    # Check if the rule matches the policy tool name
    # Supports exact tool name: "run_script_readonly", prefixes: "@fixed" and wildcard: "*"
    def matches_tool(self, tool_name: str, tool_tags: set[str]) -> bool:
        for allowed_tool in self.tools:
            if allowed_tool == "*":
                return True
            elif allowed_tool.startswith("@"):
                # Toolset prefix check if tool belongs to this toolset
                toolset_name = allowed_tool[1:]  # Remove @ prefix
                toolset = get_toolset(toolset_name)
                if toolset is None:
                    logger.warning(f"Unknown toolset: {toolset_name}")
                    return False

                if toolset.includes_tool(tool_tags):
                    return True
            elif allowed_tool == tool_name:
                return True
        return False

    # Check if the token's claims satisfy the policy rule's claim requirements
    def matches_claims(self, token_claims: dict[str, Any]) -> bool:

        for claim_key, claim_value in self.claims.items():
            # Key must be present
            if claim_key not in token_claims:
                return False

            token_value = token_claims[claim_key]

            # If the value in the token is string, the values must match exactly
            if isinstance(token_value, str):
                if token_value != claim_value:
                    return False
            # If config value is string and token value is list, must be in list
            elif isinstance(claim_value, str) and isinstance(token_value, list):
                if claim_value not in token_value:
                    return False
            # For other types (bool, int, etc), must match exactly
            else:
                if token_value != claim_value:
                    return False

        return True

    def matches(
        self,
        tool_name: str,
        tool_tags: set[str],
        target_host: str | None,
        token_claims: dict[str, Any],
    ) -> bool:
        # Check if this rule matches the given context.
        return (
            self.matches_host(target_host)
            and self.matches_tool(tool_name, tool_tags)
            and self.matches_claims(token_claims)
        )


class AuthPolicy(BaseModel):
    rules: list[PolicyRule]

    @classmethod
    def from_yaml(cls, yaml_path: Path) -> "AuthPolicy":
        """Load policy from YAML file using Pydantic validation."""
        try:
            with open(yaml_path, "r") as f:
                data = yaml.safe_load(f)

            if not data:
                logger.warning(f"Empty policy file {yaml_path}")
                return cls(rules=[])

            return cls.model_validate(data)

        except Exception as e:
            logger.error(f"Failed to load auth policy from {yaml_path}: {e}")
            raise RuntimeError(f"Failed to load auth policy from {yaml_path}: {e}") from e

    # Evaluate the policy for a given context
    # returns (action, ssh_key_config, allow_unauthorized) if no rules match, returns (DENY, None, False)
    def evaluate(
        self,
        tool_name: str,
        tool_tags: set[str],
        target_host: str | None,
        token_claims: dict[str, Any],
    ) -> tuple[PolicyAction, SSHKeyConfig | None, bool]:

        for rule in self.rules:
            if rule.matches(tool_name, tool_tags, target_host, token_claims):
                logger.debug(f"Policy match: tool={tool_name}, host={target_host}, action={rule.action.value}")
                return rule.action, rule.ssh_key, rule.allow_unauthorized

        logger.warning(f"No policy rule matched: tool={tool_name}, host={target_host}, claims={token_claims}")
        return PolicyAction.DENY, None, False


# Get the current policy loading it if necessary
@cache
def get_policy() -> AuthPolicy:

    if CONFIG.policy_path is None:
        logger.info("No auth policy path configured, all requests will be denied")
        return AuthPolicy(rules=[])

    if not CONFIG.policy_path.exists():
        logger.error(f"Auth policy file not found: {CONFIG.policy_path}")
        return AuthPolicy(rules=[])

    return AuthPolicy.from_yaml(CONFIG.policy_path)


# Wrapper that loads policy and calls AuthPolicy.evaluate()
def evaluate_policy(
    tool_name: str,
    tool_tags: set[str],
    target_host: str | None,
    token_claims: dict[str, Any],
) -> tuple[PolicyAction, SSHKeyConfig | None, bool]:
    policy = get_policy()
    return policy.evaluate(tool_name, tool_tags, target_host, token_claims)
