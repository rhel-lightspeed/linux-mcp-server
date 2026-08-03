"""Google Cloud authentication helpers for Vertex AI backends."""

import os

from linux_mcp_server.config import CONFIG


class GCPAuthError(RuntimeError):
    """Raised when GCP credentials cannot be obtained."""


def get_gcp_project() -> str:
    project = CONFIG.gatekeeper.project or os.environ.get("VERTEXAI_PROJECT") or os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not project:
        raise GCPAuthError(
            "Vertex backend requires a GCP project. Set VERTEXAI_PROJECT, GOOGLE_CLOUD_PROJECT, "
            "or LINUX_MCP_GATEKEEPER__PROJECT."
        )
    return project


def get_gcp_location() -> str:
    return CONFIG.gatekeeper.location or os.environ.get("VERTEXAI_LOCATION") or "global"


def get_gcp_access_token() -> str:
    try:
        import google.auth  # pyright: ignore[reportMissingImports]
        import google.auth.transport.requests  # pyright: ignore[reportMissingImports]
    except ImportError as exc:
        raise GCPAuthError(
            "Vertex backend requires the gcp optional dependency. Install with: uv tool install linux-mcp-server[gcp]"
        ) from exc

    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    request = google.auth.transport.requests.Request()
    credentials.refresh(request)
    if not credentials.token:
        raise GCPAuthError("Failed to obtain GCP access token from application default credentials.")
    return credentials.token
