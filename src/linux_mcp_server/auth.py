import logging

from fastmcp.server.auth.auth import RemoteAuthProvider
from fastmcp.server.auth.providers.github import GitHubProvider
from fastmcp.server.auth.providers.google import GoogleProvider
from fastmcp.server.auth.providers.introspection import IntrospectionTokenVerifier
from fastmcp.server.auth.providers.jwt import JWTVerifier
from pydantic import AnyHttpUrl

from linux_mcp_server.config import AuthProvider
from linux_mcp_server.config import CONFIG


logger = logging.getLogger("linux-mcp-server")


# Create authentication provider based on configuration
def create_auth_provider():

    if CONFIG.auth is None:
        return None

    if CONFIG.auth.provider is None:
        return None

    # base URL from host and port
    base_url = f"http://{CONFIG.host}:{CONFIG.port}"

    if CONFIG.auth.provider == AuthProvider.GOOGLE:
        if CONFIG.auth.google is None:
            raise ValueError("Google auth provider selected but LINUX_MCP_AUTH__GOOGLE__* not configured")

        return GoogleProvider(
            client_id=CONFIG.auth.google.client_id,
            client_secret=CONFIG.auth.google.client_secret.get_secret_value(),
            base_url=base_url,
        )

    elif CONFIG.auth.provider == AuthProvider.GITHUB:
        if CONFIG.auth.github is None:
            raise ValueError("GitHub auth provider selected but LINUX_MCP_AUTH__GITHUB__* not configured")

        return GitHubProvider(
            client_id=CONFIG.auth.github.client_id,
            client_secret=CONFIG.auth.github.client_secret.get_secret_value(),
            base_url=base_url,
        )

    elif CONFIG.auth.provider == AuthProvider.JWT:
        if CONFIG.auth.jwt is None:
            raise ValueError("JWT auth provider selected but LINUX_MCP_AUTH__JWT__* not configured")

        verifier = JWTVerifier(
            jwks_uri=CONFIG.auth.jwt.jwks_uri,
            issuer=CONFIG.auth.jwt.issuer,
            audience=CONFIG.auth.jwt.audience,
        )

        # RemoteAuthProvider to advertise external authorization server
        return RemoteAuthProvider(
            token_verifier=verifier,
            authorization_servers=[AnyHttpUrl(CONFIG.auth.jwt.issuer)],
            base_url=base_url,
        )

    elif CONFIG.auth.provider == AuthProvider.INTROSPECTION:
        if CONFIG.auth.introspection is None:
            raise ValueError("LINUX_MCP_AUTH__INTROSPECTION__* not configured")

        # Create introspection verifier
        verifier = IntrospectionTokenVerifier(
            introspection_url=CONFIG.auth.introspection.introspection_url,
            client_id=CONFIG.auth.introspection.client_id,
            client_secret=CONFIG.auth.introspection.client_secret.get_secret_value(),
            timeout_seconds=CONFIG.auth.introspection.timeout_seconds,
        )

        # RemoteAuthProvider to advertise external authorization server
        return RemoteAuthProvider(
            token_verifier=verifier,
            authorization_servers=[AnyHttpUrl(CONFIG.auth.introspection.issuer)],
            base_url=base_url,
        )

    else:
        raise ValueError(f"Unknown auth provider: {CONFIG.auth.provider}")
