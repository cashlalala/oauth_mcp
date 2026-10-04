"""Remote MCP server protected by OAuth 2.0, using GitHub as the authorization server.

GitHub does not support Dynamic Client Registration or resource indicators, so the
server runs FastMCP's OAuth proxy: MCP clients register and authorize against this
server, which in turn acts as the OAuth client of a pre-registered GitHub OAuth app.
"""

from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv
from fastmcp import FastMCP
from fastmcp.server.auth.providers.github import GitHubProvider
from fastmcp.server.dependencies import get_access_token
from key_value.aio.protocols import AsyncKeyValue

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
DEFAULT_SCOPES = "read:user"


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"{name} is not set. Copy .env.example to .env and fill in the "
            "credentials of your GitHub OAuth app."
        )
    return value


def create_auth(client_storage: AsyncKeyValue | None = None) -> GitHubProvider:
    """Build the GitHub OAuth provider from environment variables."""
    port = int(os.getenv("PORT", DEFAULT_PORT))
    return GitHubProvider(
        client_id=_require_env("GITHUB_CLIENT_ID"),
        client_secret=_require_env("GITHUB_CLIENT_SECRET"),
        # Public URL of this server; GitHub redirects to {BASE_URL}/auth/callback.
        base_url=os.getenv("BASE_URL", f"http://localhost:{port}"),
        required_scopes=os.getenv("GITHUB_SCOPES", DEFAULT_SCOPES).split(),
        # Falls back to a key derived from the client secret when unset.
        jwt_signing_key=os.getenv("JWT_SIGNING_KEY") or None,
        client_storage=client_storage,
    )


def create_server(client_storage: AsyncKeyValue | None = None) -> FastMCP:
    """Create the MCP server with its dummy tools."""
    mcp = FastMCP("OAuth MCP Demo", auth=create_auth(client_storage))

    @mcp.tool
    def echo(message: str) -> str:
        """Echo the message back."""
        return message

    @mcp.tool
    def add(a: float, b: float) -> float:
        """Add two numbers."""
        return a + b

    @mcp.tool
    def whoami() -> dict[str, Any]:
        """Return the GitHub identity of the authenticated caller."""
        token = get_access_token()
        if token is None:
            raise RuntimeError("No authenticated user")
        return {
            "login": token.claims.get("login"),
            "name": token.claims.get("name"),
            "github_id": token.claims.get("sub"),
            "scopes": token.scopes,
        }

    return mcp


def main() -> None:
    load_dotenv()
    create_server().run(
        transport="http",
        host=os.getenv("HOST", DEFAULT_HOST),
        port=int(os.getenv("PORT", DEFAULT_PORT)),
    )


if __name__ == "__main__":
    main()
