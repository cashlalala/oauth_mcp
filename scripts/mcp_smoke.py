"""Smoke test: get a token from mock-oauth2-server (auth code + PKCE) and call the MCP server."""
import base64, hashlib, json, os, secrets, sys
from urllib.parse import parse_qs, urlparse

import requests

MCP = os.environ.get("MCP_URL", "http://localhost:3232")
ISSUER = os.environ.get("ISSUER", "http://localhost:8081/issuer1")
CLIENT_ID = "mcp-client"
REDIRECT = "http://localhost:9999/callback"  # nothing listens; we only read the redirect

meta = requests.get(f"{MCP}/.well-known/oauth-authorization-server").json()
print("metadata issuer:", meta["issuer"], "| authorize:", meta["authorization_endpoint"])

r = requests.post(f"{MCP}/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
print("no token ->", r.status_code)

verifier = secrets.token_urlsafe(48)
challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
s = requests.Session()
params = dict(response_type="code", client_id=CLIENT_ID, redirect_uri=REDIRECT, scope="openid",
              state="xyz", code_challenge=challenge, code_challenge_method="S256")
page = s.get(meta["authorization_endpoint"], params=params)
resp = s.post(page.url, data={"username": "alice", "claims": json.dumps({"preferred_username": "alice"})},
              allow_redirects=False)
code = parse_qs(urlparse(resp.headers["Location"]).query)["code"][0]
tok = s.post(meta["token_endpoint"], data=dict(grant_type="authorization_code", code=code,
             redirect_uri=REDIRECT, client_id=CLIENT_ID, code_verifier=verifier)).json()
access = tok["access_token"]
print("got access token:", access[:20], "...")

hdr = {"Authorization": f"Bearer {access}", "Accept": "application/json, text/event-stream"}
init = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
    "protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "smoke", "version": "1"}}}
r = requests.post(f"{MCP}/mcp", json=init, headers=hdr)
print("with token ->", r.status_code, r.text[:200])
sys.exit(0 if r.status_code == 200 else 1)
