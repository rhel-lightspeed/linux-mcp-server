import logging

from typing import Any

from fastmcp.server.auth.auth import RemoteAuthProvider
from fastmcp.server.auth.providers.github import GitHubProvider
from fastmcp.server.auth.providers.google import GoogleProvider
from fastmcp.server.auth.providers.introspection import IntrospectionTokenVerifier
from fastmcp.server.auth.providers.jwt import JWTVerifier
from pydantic import AnyHttpUrl

from linux_mcp_server.config import AuthProvider
from linux_mcp_server.config import CONFIG


logger = logging.getLogger(__name__)

# Without "email", Google's token check returns no email claim, so authorization
# policy rules could only match the opaque "sub" claim.
GOOGLE_SCOPES = ["openid", "email"]

# Claims some providers return as the strings "true"/"false" rather than booleans -
# FastMCP's Google provider passes email_verified through from Google's tokeninfo endpoint.
BOOLEAN_CLAIMS = ("email_verified",)


def normalize_claims(claims: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of the token claims with string booleans converted to bool.

    Policy rules and audit logs then see one type for these claims whatever the provider.
    """
    normalized = dict(claims)
    for name in BOOLEAN_CLAIMS:
        value = normalized.get(name)
        if isinstance(value, str) and value.lower() in ("true", "false"):
            normalized[name] = value.lower() == "true"
    return normalized


# Create authentication provider based on configuration
def create_auth_provider():

    if CONFIG.auth is None:
        return None

    if CONFIG.auth.provider is None:
        return None

    base_url = CONFIG.effective_base_url

    if CONFIG.auth.provider == AuthProvider.GOOGLE:
        if CONFIG.auth.google is None:
            raise ValueError("Google auth provider selected but LINUX_MCP_AUTH__GOOGLE__* not configured")

        return GoogleProvider(
            client_id=CONFIG.auth.google.client_id,
            client_secret=CONFIG.auth.google.client_secret.get_secret_value(),
            base_url=base_url,
            required_scopes=GOOGLE_SCOPES,
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
