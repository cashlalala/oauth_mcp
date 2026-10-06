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

   Connect to `http://localhost:3232/mcp` (Streamable HTTP). Under *Authentication > OAuth*, enter a **Client ID** manually (e.g. `mcp-client`),
   because mock-oauth2-server has no dynamic client registration. At the mock login page type any username
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
3. **No dynamic client registration.** The example server advertises `/register`, which mock-oauth2-server doesn't implement, so clients must use a preconfigured client ID.
4. **Reduced token info.** The mock's introspection response has no `client_id` or `scope`, so the MCP server sees client `unknown` and no scopes. `sub` is the username you logged in with.

## Files

- [compose.mcp.yaml](compose.mcp.yaml): the two services
- [mcp/Dockerfile](mcp/Dockerfile): builds the cloned server, applying the patch
- [mcp/patch-introspect.js](mcp/patch-introspect.js): Basic-auth patch
- [scripts/mcp_smoke.py](scripts/mcp_smoke.py): auth code + PKCE login, then an MCP `initialize` call
