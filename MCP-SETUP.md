# Running the MCP example remote server with mock-oauth2-server

Follows the [example-remote-server README](https://github.com/modelcontextprotocol/example-remote-server/blob/main/README.md),
using its **external auth mode** (`AUTH_MODE=external`) with mock-oauth2-server as the authorization server instead of the bundled demo auth server.

Verified on Windows 11 + Docker Desktop: `scripts/mcp_smoke.py` gets a token and calls `/mcp` with HTTP 200.

## Steps

1. **Clone the MCP server** next to these files (it is git-ignored):

   ```
   git clone --depth 1 https://github.com/modelcontextprotocol/example-remote-server.git
   ```

2. **Start both containers** (builds the MCP image from the clone, node 22):

   ```
   docker compose -f compose.mcp.yaml up -d --build
   ```

3. **Check it** (needs the project virtualenv, see README.md):

   ```
   .venv\Scripts\python scripts\mcp_smoke.py
   ```

   Expected: metadata issuer `http://localhost:8081/issuer1`, `no token -> 401`, then `with token -> 200`.

4. **Try it interactively** with MCP Inspector:

   ```
   npx -y @modelcontextprotocol/inspector
   ```

   Connect to `http://localhost:3232/mcp` (Streamable HTTP). Leave the OAuth client ID empty: Inspector registers itself dynamically (DCR) through the proxy in `proxy/`. At the mock login page type any username
   (optionally claims JSON such as `{"preferred_username":"alice"}`) and submit.
   Mock server debugger: `http://localhost:8081/issuer1/debugger`.

5. **Stop**: `docker compose -f compose.mcp.yaml down`

## How it is wired

| Piece | Setting |
|---|---|
| MCP server | `AUTH_MODE=external`, `AUTH_SERVER_URL=http://localhost:8081/issuer1`, `BASE_URI=http://localhost:3232` |
| Mock server | Port 8081, issuer `issuer1` (any path name works) |
| Discovery | MCP server serves `/.well-known/oauth-authorization-server`, pointing at `.../issuer1/authorize`, `/token`, `/introspect` |
| Token validation | MCP server POSTs each bearer token to `<AUTH_SERVER_URL>/introspect` (cached 60 s) |

## Things that differ from the plain README and why

1. **Shared network namespace.** The mock server builds the issuer from the request host, so the browser, client and MCP server must all call it as `http://localhost:8081`.
   `host.docker.internal` did not work here (it resolves to the LAN IP, which timed out from the host). So the MCP container uses
   `network_mode: "service:mock-oauth2-server"`; inside it `localhost:8081` is the mock server, and port 3232 is published on the mock service.
2. **Introspection needs client auth.** mock-oauth2-server answers `/introspect` with `invalid_client` unless the request has client credentials,
   and the example server sends none (every token came back `Token is not active`). [mcp/patch-introspect.js](mcp/patch-introspect.js) is applied at image build time
   and adds HTTP Basic auth from `INTROSPECT_CLIENT_ID` / `INTROSPECT_CLIENT_SECRET`. The mock server accepts any values.
3. **Missing Protected Resource Metadata (Inspector 404).** In external mode the server's 401 response says
   `WWW-Authenticate: ... resource_metadata="http://localhost:3232/.well-known/oauth-protected-resource"`, but nothing serves that URL
   (only internal mode gets it, through the SDK's `mcpAuthRouter`). MCP Inspector (and any spec-following client) fetches it first, gets 404 and stops.
   The same patch script now also adds an RFC 9728 route to `src/index.ts` for external mode, at both
   `/.well-known/oauth-protected-resource` and `/.well-known/oauth-protected-resource/mcp`:

   ```json
   {"resource":"http://localhost:3232/mcp","authorization_servers":["http://localhost:8081/issuer1"],"bearer_methods_supported":["header"]}
   ```

   Clients then read the mock server's `http://localhost:8081/issuer1/.well-known/openid-configuration` for the endpoints.
   Rebuild after changing the patch: `docker compose -f compose.mcp.yaml up -d --build`.
   Verify: `curl http://localhost:3232/.well-known/oauth-protected-resource` should return the JSON above.
4. **Dynamic client registration (DCR) added by a front proxy.** mock-oauth2-server has no `/register` endpoint, and the example server advertises one,
   so Inspector's DCR step failed. [proxy/server.js](proxy/server.js) (plain Node, no dependencies) now sits on port 8081 in front of the mock server (moved to 8080):
   - `POST /issuer1/register` returns `201` with a generated `client_id` (the mock server accepts any client_id, so nothing needs storing), with CORS headers because Inspector calls it from the browser.
   - The `.well-known` metadata documents get a `registration_endpoint` added. It also answers the path-aware URLs
     (`/.well-known/oauth-authorization-server/issuer1`, `/.well-known/openid-configuration/issuer1`) that the mock server rejects with 405.
   - `GET /issuer1/authorize` without a `scope` is redirected (302) to the same URL with `scope=openid`: the mock server rejects a missing scope
     (`invalid_request: missing scope parameter`), and Inspector sends none because the server advertises no scopes.
   - Everything else is proxied unchanged with the `Host` header preserved, since the mock derives the issuer from it.

   Since the mock and MCP containers join the proxy's network namespace, restarting only `oauth-proxy` breaks them; use
   `docker compose -f compose.mcp.yaml up -d --force-recreate`.
   Test: `curl -X POST http://localhost:8081/issuer1/register -H "content-type: application/json" -d '{"redirect_uris":["http://localhost:6274/oauth/callback"]}'`
5. **Reduced token info.** The mock's introspection response has no `client_id` or `scope`, so the MCP server sees client `unknown` and no scopes. `sub` is the username you logged in with.

## Files

- [compose.mcp.yaml](compose.mcp.yaml): the three services (proxy, mock server, MCP server)
- [proxy/server.js](proxy/server.js): DCR front proxy
- [mcp/Dockerfile](mcp/Dockerfile): builds the cloned server, applying the patch
- [mcp/patch-introspect.js](mcp/patch-introspect.js): build-time patches (introspection Basic auth, protected resource metadata route)
- [scripts/mcp_smoke.py](scripts/mcp_smoke.py): auth code + PKCE login, then an MCP `initialize` call
