import tempfile

from pathlib import Path

import pytest

from linux_mcp_server.auth_policy import AuthPolicy
from linux_mcp_server.auth_policy import evaluate_policy
from linux_mcp_server.auth_policy import get_policy
from linux_mcp_server.auth_policy import PolicyAction
from linux_mcp_server.auth_policy import PolicyRule
from linux_mcp_server.auth_policy import SSHKeyConfig


class TestSSHKeyConfig:
    def test_valid_config(self):
        config = SSHKeyConfig(path="/path/to/key", user="admin")
        assert config.path == "/path/to/key"
        assert config.user == "admin"


class TestPolicyRuleHostMatching:
    def test_wildcard_match(self):
        rule = PolicyRule(
            host="*.example.com",
            tools=["*"],
            claims={},
            action=PolicyAction.SSH_DEFAULT,
            all_users=True,
        )
        assert rule.matches_host("host1.example.com")
        assert rule.matches_host("host2.example.com")
        assert not rule.matches_host("example.com")

    def test_localhost_normalization(self):
        rule = PolicyRule(
            host="localhost",
            tools=["*"],
            claims={},
            action=PolicyAction.LOCAL,
            all_users=True,
        )
        # None gets normalized to localhost
        assert rule.matches_host(None)
        assert rule.matches_host("localhost")


class TestPolicyRuleToolMatching:
    def test_wildcard_match(self):
        rule = PolicyRule(
            host="*",
            tools=["*"],
            claims={},
            action=PolicyAction.SSH_DEFAULT,
            all_users=True,
        )
        assert rule.matches_tool("any_tool", set())
        assert rule.matches_tool("any_tool", {"tag1", "tag2"})

    def test_exact_tool_name_match(self):
        rule = PolicyRule(
            host="*",
            tools=["run_script_readonly"],
            claims={},
            action=PolicyAction.SSH_DEFAULT,
            all_users=True,
        )
        assert rule.matches_tool("run_script_readonly", set())
        assert not rule.matches_tool("other_tool", set())

    def test_toolset_prefix_match(self):
        rule = PolicyRule(
            host="*",
            tools=["@run_script"],
            claims={},
            action=PolicyAction.SSH_DEFAULT,
            all_users=True,
        )
        # Tool with run_script tag matches @run_script toolset
        assert rule.matches_tool("validate_script", {"run_script"})
        assert not rule.matches_tool("get_service_status", set())


class TestPolicyRuleClaimMatching:
    def test_empty_claims(self):
        rule = PolicyRule(
            host="*",
            tools=["*"],
            claims={},
            action=PolicyAction.SSH_DEFAULT,
            all_users=True,
        )
        # Empty claims always match
        assert rule.matches_claims({})
        assert rule.matches_claims({"email": "user@example.com"})

    def test_string_exact_match(self):
        rule = PolicyRule(
            host="*",
            tools=["*"],
            claims={"email": "admin@example.com"},
            action=PolicyAction.SSH_DEFAULT,
        )
        assert rule.matches_claims({"email": "admin@example.com"})
        assert not rule.matches_claims({"email": "user@example.com"})

    def test_string_in_list(self):
        rule = PolicyRule(
            host="*",
            tools=["*"],
            claims={"roles": "admin"},
            action=PolicyAction.SSH_DEFAULT,
        )
        # Token has list, config value must be in list
        assert rule.matches_claims({"roles": ["admin", "user"]})
        assert rule.matches_claims({"roles": ["admin"]})
        assert not rule.matches_claims({"roles": ["user"]})


class TestPolicyRuleMatches:
    def test_full_match(self):
        rule = PolicyRule(
            host="*.prod.example.com",
            tools=["@fixed"],
            claims={"email": "admin@example.com"},
            action=PolicyAction.SSH_DEFAULT,
        )
        assert rule.matches(
            tool_name="get_service_status",
            tool_tags={"fixed"},
            target_host="web.prod.example.com",
            token_claims={"email": "admin@example.com"},
        )

    def test_claims_mismatch(self):
        rule = PolicyRule(
            host="*.prod.example.com",
            tools=["@fixed"],
            claims={"email": "admin@example.com"},
            action=PolicyAction.SSH_DEFAULT,
        )
        assert not rule.matches(
            tool_name="get_service_status",
            tool_tags=set(),
            target_host="web.prod.example.com",
            token_claims={"email": "user@example.com"},
        )


class TestAuthPolicyEvaluate:
    def test_first_matching_rule(self):
        policy = AuthPolicy(
            rules=[
                PolicyRule(
                    host="*",
                    tools=["*"],
                    claims={"email": "admin@example.com"},
                    action=PolicyAction.SSH_DEFAULT,
                ),
                PolicyRule(
                    host="*",
                    tools=["*"],
                    claims={},
                    action=PolicyAction.DENY,
                    all_users=True,
                ),
            ]
        )

        # First rule matches
        action, ssh_key, all_users = policy.evaluate(
            tool_name="any_tool",
            tool_tags=set(),
            target_host="any-host",
            token_claims={"email": "admin@example.com"},
        )
        assert action == PolicyAction.SSH_DEFAULT
        assert ssh_key is None
        assert all_users is False

    def test_no_match_returns_deny(self):
        policy = AuthPolicy(
            rules=[
                PolicyRule(
                    host="*.prod.example.com",
                    tools=["*"],
                    claims={"email": "admin@example.com"},
                    action=PolicyAction.SSH_DEFAULT,
                ),
            ]
        )

        # No rule matches
        action, ssh_key, all_users = policy.evaluate(
            tool_name="any_tool",
            tool_tags=set(),
            target_host="stage-host",
            token_claims={},
        )
        assert action == PolicyAction.DENY
        assert ssh_key is None
        assert all_users is False

    def test_ssh_key_action_returns_config(self):
        ssh_key_config = SSHKeyConfig(path="/keys/db-key", user="db-admin")
        policy = AuthPolicy(
            rules=[
                PolicyRule(
                    host="*.db.example.com",
                    tools=["*"],
                    claims={"groups": "ops"},
                    action=PolicyAction.SSH_KEY,
                    ssh_key=ssh_key_config,
                ),
            ]
        )

        action, ssh_key, all_users = policy.evaluate(
            tool_name="any_tool",
            tool_tags=set(),
            target_host="mysql.db.example.com",
            token_claims={"groups": ["ops", "dev"]},
        )
        assert action == PolicyAction.SSH_KEY
        assert ssh_key == ssh_key_config
        assert all_users is False


class TestAuthPolicyFromYaml:
    def test_load_valid_yaml(self):
        yaml_content = """
rules:
  - host: "*.example.com"
    tools: ["@fixed"]
    claims:
      email: "admin@example.com"
    action: ssh_default

  - host: "localhost"
    tools: ["*"]
    claims: {}
    action: local
    all_users: true
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            path = Path(f.name)

        try:
            policy = AuthPolicy.from_yaml(path)
            assert len(policy.rules) == 2
            assert policy.rules[0].host == "*.example.com"
            assert policy.rules[0].action == PolicyAction.SSH_DEFAULT
            assert policy.rules[1].all_users is True
        finally:
            path.unlink()

    def test_load_with_ssh_key(self):
        yaml_content = """
rules:
  - host: "*.db.example.com"
    tools: ["*"]
    claims:
      groups: ops
    action: ssh_key
    ssh_key:
      path: /keys/db-key
      user: db-admin
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            path = Path(f.name)

        try:
            policy = AuthPolicy.from_yaml(path)
            assert len(policy.rules) == 1
            assert policy.rules[0].action == PolicyAction.SSH_KEY
            assert policy.rules[0].ssh_key is not None
            assert policy.rules[0].ssh_key.path == "/keys/db-key"
            assert policy.rules[0].ssh_key.user == "db-admin"
        finally:
            path.unlink()

    def test_invalid_yaml_raises(self):
        yaml_content = """
rules:
  - host: "*.example.com"
    tools: ["@fixed"]
    claims:
      email: "admin@example.com"
    action: invalid_action
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            path = Path(f.name)

        try:
            with pytest.raises(RuntimeError):
                AuthPolicy.from_yaml(path)
        finally:
            path.unlink()


class TestGetPolicy:
    def test_no_policy_path_returns_empty(self, mocker):
        mocker.patch("linux_mcp_server.auth_policy.CONFIG", policy_path=None)
        # Clear the cache
        get_policy.cache_clear()

        policy = get_policy()
        assert len(policy.rules) == 0

    def test_valid_policy_path(self, mocker):
        yaml_content = """
rules:
  - host: "localhost"
    tools: ["*"]
    claims: {}
    action: local
    all_users: true
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            path = Path(f.name)

        try:
            mocker.patch("linux_mcp_server.auth_policy.CONFIG", policy_path=path)
            get_policy.cache_clear()

            policy = get_policy()
            assert len(policy.rules) == 1
        finally:
            path.unlink()


class TestEvaluatePolicy:
    def test_delegates_to_policy(self, mocker):
        # Mock get_policy to return a specific policy
        mock_policy = mocker.Mock(spec=AuthPolicy)
        mock_policy.evaluate.return_value = (PolicyAction.SSH_DEFAULT, None, False)
        mocker.patch("linux_mcp_server.auth_policy.get_policy", return_value=mock_policy)

        # Create mock Tool object
        mock_tool = mocker.Mock()
        mock_tool.name = "test_tool"
        mock_tool.tags = {"tag1"}

        action, ssh_key = evaluate_policy(
            tool=mock_tool,
            target_host="test-host",
            token_claims={"email": "user@example.com"},
        )

        # Verify delegation, called with positional args
        mock_policy.evaluate.assert_called_once_with(
            "test_tool",
            {"tag1"},
            "test-host",
            {"email": "user@example.com"},
        )
        assert action == PolicyAction.SSH_DEFAULT
        assert ssh_key is None
