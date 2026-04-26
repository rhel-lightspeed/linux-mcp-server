import fnmatch
import logging

from enum import Enum
from functools import cache
from pathlib import Path
from typing import Any

import yaml

from fastmcp.tools import Tool
from pydantic import BaseModel
from pydantic import model_validator

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
    claims: dict[str, Any] = {}
    action: PolicyAction
    ssh_key: SSHKeyConfig | None = None
    all_users: bool = False

    # Validate that all_users and claims are mutually exclusive
    @model_validator(mode="after")
    def validate_all_users_and_claims(self):
        if self.all_users and self.claims:
            raise ValueError("Rule with 'all_users: true' must not have claims specified")
        if not self.all_users and not self.claims:
            raise ValueError("Rule with 'all_users: false' must have non-empty claims")
        return self

    # Validate that host and action are semantically compatible
    @model_validator(mode="after")
    def validate_host_action(self):
        # localhost should have LOCAL or DENY action
        if self.host == "localhost":
            if self.action not in [PolicyAction.LOCAL, PolicyAction.DENY]:
                raise ValueError(
                    f"Rule with host: 'localhost' must use action 'local' or 'deny' and not '{self.action.value}'"
                )
        # other hosts should have SSH_* or DENY action
        else:
            if self.action == PolicyAction.LOCAL:
                raise ValueError(f"Rule with host: '{self.host}' cannot be use action 'local'")
        return self

    # Validate that SSH_KEY action has ssh_key configuration
    @model_validator(mode="after")
    def validate_ssh_key_config(self):
        if self.action == PolicyAction.SSH_KEY and self.ssh_key is None:
            raise ValueError("Rule with action 'ssh_key' must have ssh_key(path and user) configured")
        return self

    def matches_host(self, target_host: str | None) -> bool:
        if target_host is None:
            # 'host: *' should not allow local execution
            return self.host == "localhost"
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

    # Check if the tokens claims satisfy the policy rules claim requirements
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
    # returns (action, ssh_key_config, all_users) if no rules match, returns (DENY, None, False)
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
                return rule.action, rule.ssh_key, rule.all_users

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
    tool: Tool,
    target_host: str | None,
    token_claims: dict[str, Any],
) -> tuple[PolicyAction, SSHKeyConfig | None]:
    policy = get_policy()
    tool_name = tool.name
    tool_tags = tool.tags if tool.tags else set()
    action, ssh_key_config, _ = policy.evaluate(tool_name, tool_tags, target_host, token_claims)
    return action, ssh_key_config
