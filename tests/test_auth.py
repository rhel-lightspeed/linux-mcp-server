import pytest

from pydantic import SecretStr
from pytest_mock import MockerFixture

from linux_mcp_server.auth import create_auth_provider
from linux_mcp_server.config import AuthConfig
from linux_mcp_server.config import AuthProvider
from linux_mcp_server.config import Config
from linux_mcp_server.config import GitHubAuthConfig
from linux_mcp_server.config import GoogleAuthConfig
from linux_mcp_server.config import IntrospectionAuthConfig
from linux_mcp_server.config import JWTAuthConfig


class TestCreateAuthProvider:
    def test_no_auth_config_returns_none(self, mocker):
        mocker.patch("linux_mcp_server.auth.CONFIG", Config(auth=None, host="localhost", port=8000))
        provider = create_auth_provider()
        assert provider is None

    def test_no_provider_selected_returns_none(self, mocker):
        auth_config = AuthConfig(provider=None)
        mocker.patch("linux_mcp_server.auth.CONFIG", Config(auth=auth_config, host="localhost", port=8000))
        provider = create_auth_provider()
        assert provider is None

    def test_google_provider(self, mocker):
        google_config = GoogleAuthConfig(
            client_id="test-client-id",
            client_secret=SecretStr("test-secret"),
        )
        auth_config = AuthConfig(
            provider=AuthProvider.GOOGLE,
            google=google_config,
        )
        mocker.patch("linux_mcp_server.auth.CONFIG", Config(auth=auth_config, host="localhost", port=8000))

        provider = create_auth_provider()
        assert provider is not None
        # Verify it's a GoogleProvider
        from fastmcp.server.auth.providers.google import GoogleProvider

        assert isinstance(provider, GoogleProvider)

    def test_google_provider_missing_config_raises(self, mocker):
        auth_config = AuthConfig(
            provider=AuthProvider.GOOGLE,
            google=None,
        )
        mocker.patch("linux_mcp_server.auth.CONFIG", Config(auth=auth_config, host="localhost", port=8000))

        with pytest.raises(ValueError, match="Google auth provider selected"):
            create_auth_provider()

    def test_github_provider(self, mocker):
        github_config = GitHubAuthConfig(
            client_id="test-client-id",
            client_secret=SecretStr("test-secret"),
        )
        auth_config = AuthConfig(
            provider=AuthProvider.GITHUB,
            github=github_config,
        )
        mocker.patch("linux_mcp_server.auth.CONFIG", Config(auth=auth_config, host="localhost", port=8000))

        provider = create_auth_provider()
        assert provider is not None
        # Verify it's a GitHubProvider
        from fastmcp.server.auth.providers.github import GitHubProvider

        assert isinstance(provider, GitHubProvider)

    def test_github_provider_missing_config_raises(self, mocker):
        auth_config = AuthConfig(
            provider=AuthProvider.GITHUB,
            github=None,
        )
        mocker.patch("linux_mcp_server.auth.CONFIG", Config(auth=auth_config, host="localhost", port=8000))

        with pytest.raises(ValueError, match="GitHub auth provider selected"):
            create_auth_provider()

    def test_jwt_provider(self, mocker):
        jwt_config = JWTAuthConfig(
            jwks_uri="https://example.com/.well-known/jwks.json",
            issuer="https://example.com",
            audience="test-audience",
        )
        auth_config = AuthConfig(
            provider=AuthProvider.JWT,
            jwt=jwt_config,
        )
        mocker.patch("linux_mcp_server.auth.CONFIG", Config(auth=auth_config, host="localhost", port=8000))

        provider = create_auth_provider()
        assert provider is not None
        # RemoteAuthProvider should have token_verifier
        assert hasattr(provider, "token_verifier")

    def test_jwt_provider_missing_config_raises(self, mocker):
        auth_config = AuthConfig(
            provider=AuthProvider.JWT,
            jwt=None,
        )
        mocker.patch("linux_mcp_server.auth.CONFIG", Config(auth=auth_config, host="localhost", port=8000))

        with pytest.raises(ValueError, match="JWT auth provider selected"):
            create_auth_provider()

    def test_introspection_provider(self, mocker):
        introspection_config = IntrospectionAuthConfig(
            introspection_url="https://example.com/introspect",
            client_id="test-client-id",
            client_secret=SecretStr("test-secret"),
            issuer="https://example.com",
            timeout_seconds=10,
        )
        auth_config = AuthConfig(
            provider=AuthProvider.INTROSPECTION,
            introspection=introspection_config,
        )
        mocker.patch("linux_mcp_server.auth.CONFIG", Config(auth=auth_config, host="localhost", port=8000))

        provider = create_auth_provider()
        assert provider is not None
        assert hasattr(provider, "token_verifier")

    def test_introspection_provider_missing_config_raises(self, mocker):
        auth_config = AuthConfig(
            provider=AuthProvider.INTROSPECTION,
            introspection=None,
        )
        mocker.patch("linux_mcp_server.auth.CONFIG", Config(auth=auth_config, host="localhost", port=8000))

        with pytest.raises(ValueError, match="LINUX_MCP_AUTH__INTROSPECTION__"):
            create_auth_provider()


@pytest.mark.parametrize(
    "tls, base_url, expected",
    [
        (False, None, "http://localhost:8443"),
        (True, None, "https://localhost:8443"),
        (False, "https://mcp.example.com/proxy", "https://mcp.example.com/proxy"),
        (True, "https://mcp.example.com/proxy", "https://mcp.example.com/proxy"),
    ],
)
def test_auth_base_url(
    tls: bool,
    base_url: str | None,
    expected: str,
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
) -> None:
    monkeypatch.setenv("LINUX_MCP_TRANSPORT", "http")
    if tls:
        monkeypatch.setenv("LINUX_MCP_TLS_CERT", "cert.pem")
        monkeypatch.setenv("LINUX_MCP_TLS_KEY", "key.pem")
    if base_url is not None:
        monkeypatch.setenv("LINUX_MCP_BASE_URL", base_url)
    config = Config(
        host="localhost",
        port=8443,
        auth=AuthConfig(
            provider=AuthProvider.JWT,
            jwt=JWTAuthConfig(jwks_uri="https://auth.example.com/jwks", issuer="https://auth.example.com"),
        ),
    )
    mocker.patch("linux_mcp_server.auth.CONFIG", config)
    provider = mocker.patch("linux_mcp_server.auth.RemoteAuthProvider", autospec=True)
    create_auth_provider()
    assert provider.call_args is not None
    assert provider.call_args.kwargs["base_url"] == expected
