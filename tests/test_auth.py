"""Tests for the OAuth surface of the MCP server. No real GitHub credentials needed."""

from __future__ import annotations

import base64
import hashlib
from urllib.parse import parse_qs, urlparse

import pytest
from key_value.aio.stores.memory import MemoryStore
from starlette.testclient import TestClient

import server

BASE_URL = "http://localhost:8000"
REDIRECT_URI = "http://localhost:53682/callback"
INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "0"},
    },
}
MCP_HEADERS = {"Accept": "application/json, text/event-stream"}


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GITHUB_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("GITHUB_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("BASE_URL", BASE_URL)
    monkeypatch.setenv("GITHUB_SCOPES", "read:user")
    app = server.create_server(client_storage=MemoryStore()).http_app()
    with TestClient(app, base_url=BASE_URL, follow_redirects=False) as c:
        yield c


def _register(client: TestClient) -> dict:
    response = client.post(
        "/register",
        json={
            "client_name": "Test MCP Client",
            "redirect_uris": [REDIRECT_URI],
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "none",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_missing_credentials_fail_fast(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GITHUB_CLIENT_ID", raising=False)
    monkeypatch.delenv("GITHUB_CLIENT_SECRET", raising=False)
    with pytest.raises(RuntimeError, match="GITHUB_CLIENT_ID"):
        server.create_server()


def test_unauthenticated_request_is_challenged(client: TestClient):
    response = client.post("/mcp", json=INITIALIZE, headers=MCP_HEADERS)
    assert response.status_code == 401
    challenge = response.headers["www-authenticate"]
    assert challenge.startswith("Bearer")
    assert (
        f'resource_metadata="{BASE_URL}/.well-known/oauth-protected-resource/mcp"'
        in challenge
    )


def test_invalid_token_is_rejected(client: TestClient):
    response = client.post(
        "/mcp",
        json=INITIALIZE,
        headers={**MCP_HEADERS, "Authorization": "Bearer not-a-real-token"},
    )
    assert response.status_code == 401
    assert "invalid_token" in response.headers["www-authenticate"]


def test_protected_resource_metadata(client: TestClient):
    response = client.get("/.well-known/oauth-protected-resource/mcp")
    assert response.status_code == 200
    metadata = response.json()
    assert metadata["resource"] == f"{BASE_URL}/mcp"
    assert [s.rstrip("/") for s in metadata["authorization_servers"]] == [BASE_URL]
    assert "read:user" in metadata["scopes_supported"]


def test_authorization_server_metadata(client: TestClient):
    response = client.get("/.well-known/oauth-authorization-server")
    assert response.status_code == 200
    metadata = response.json()
    assert metadata["issuer"].rstrip("/") == BASE_URL
    assert metadata["authorization_endpoint"] == f"{BASE_URL}/authorize"
    assert metadata["token_endpoint"] == f"{BASE_URL}/token"
    assert metadata["registration_endpoint"] == f"{BASE_URL}/register"
    assert "S256" in metadata["code_challenge_methods_supported"]


def test_dynamic_client_registration(client: TestClient):
    registration = _register(client)
    assert registration["client_id"]
    assert registration["redirect_uris"] == [REDIRECT_URI]


def test_authorize_never_leaks_upstream_secret(client: TestClient):
    registration = _register(client)
    verifier = "v" * 64
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    response = client.get(
        "/authorize",
        params={
            "response_type": "code",
            "client_id": registration["client_id"],
            "redirect_uri": REDIRECT_URI,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": "xyz",
            "scope": "read:user",
            "resource": f"{BASE_URL}/mcp",
        },
    )
    # The user is sent to this server's consent page before going on to GitHub.
    assert response.status_code in (302, 303, 307)
    location = response.headers["location"]
    assert urlparse(location).path == "/consent"
    assert "test-client-secret" not in location
    assert "txn_id" in parse_qs(urlparse(location).query)


def test_authorize_rejects_unregistered_client(client: TestClient):
    response = client.get(
        "/authorize",
        params={
            "response_type": "code",
            "client_id": "unknown-client",
            "redirect_uri": REDIRECT_URI,
            "code_challenge": "x" * 43,
            "code_challenge_method": "S256",
        },
    )
    assert response.status_code == 400
