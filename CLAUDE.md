# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Two independent setups share this repo, both using [mock-oauth2-server](https://github.com/navikt/mock-oauth2-server) (`ghcr.io/navikt/mock-oauth2-server:5.0.2`) as the OAuth2 provider. Docker (Desktop) is required. Shell is Windows; the venv is `.venv` (use `.venv\Scripts\python`).

## 1. Python OAuth2 client + tests (port of a Spring Boot guide)

```
python -m venv .venv && .venv\Scripts\activate && pip install -r requirements.txt
pytest                                   # all tests
pytest tests/test_login.py::test_admin_access   # single test
```

- `compose.yaml` runs the mock server on :8081. The `mock_oauth2_server` fixture in `tests/conftest.py` reuses a server already on :8081, otherwise runs `docker compose up -d` and `down` afterwards.
- `app/main.py` is a Flask/Authlib client (authorization code + PKCE). The `live_server` fixture serves it on a random port in a thread: OAuth redirects need a real reachable server, so Flask's test client can't be used.
- Java's "enqueue token callback" has no Python equivalent. `tests/login_helper.py` instead POSTs a `claims` JSON field to the mock server's login form; that is how roles (`realm_access.roles`) get into the token.
- Issuer is `http://localhost:8081/issuer1` (any path name works with the mock).

## 2. MCP example-remote-server + mock OAuth server (Docker)

Full steps and rationale: `MCP-SETUP.md`. Short version:

```
git clone --depth 1 https://github.com/modelcontextprotocol/example-remote-server.git   # git-ignored, build context
docker compose -f compose.mcp.yaml up -d --build
.venv\Scripts\python scripts\mcp_smoke.py        # token via auth code+PKCE, then MCP initialize -> expect 200
docker compose -f compose.mcp.yaml up -d --force-recreate   # restart the stack (see below)
```

MCP URL is `http://localhost:3232/mcp`; verified with MCP Inspector (leave client ID empty, it registers via DCR).

Architecture (non-obvious, spans several files):
- The mock server builds the issuer from the request Host, so browser, client and MCP server must all see it as `http://localhost:8081`. Therefore `compose.mcp.yaml` puts all three services in one network namespace owned by `oauth-proxy` (`network_mode: service:oauth-proxy`); published ports (8081, 3232) live on that service. **Restarting only `oauth-proxy` breaks the others; always `--force-recreate` the whole stack.** `host.docker.internal` does not work on this machine.
- `proxy/server.js` (dependency-free Node, mounted into a `node:22` container) listens on :8081 in front of the mock (:8080). It adds DCR (`POST /issuer1/register`, mock accepts any client_id), injects `registration_endpoint`/`scopes_supported` into metadata (also serving the path-aware `.well-known` URLs the mock answers 405 to), 302-redirects `/authorize` calls lacking `scope` to `scope=openid`, and proxies everything else with the Host header preserved.
- The upstream MCP server is run with `AUTH_MODE=external` and is **patched at image build** by `mcp/patch-introspect.js` (run from `mcp/Dockerfile`; the clone itself stays untouched): (a) Basic auth on `/introspect`, since the mock returns `invalid_client` otherwise (`INTROSPECT_CLIENT_ID/SECRET` env, any values); (b) an RFC 9728 `/.well-known/oauth-protected-resource[/mcp]` route that external mode otherwise never serves. If upstream code changes, the patch script throws "patch target not found".
- The mock's introspection response has no `client_id`/`scope`, so the MCP server sees client `unknown` with no scopes.
