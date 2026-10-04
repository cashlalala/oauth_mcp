# oauth_mcp

A remote MCP server (Streamable HTTP) protected by OAuth 2.0, built with
[FastMCP](https://gofastmcp.com) and using GitHub as the authorization server.

The tools are dummies (`echo`, `add`, `whoami`); the point of the project is the
authorization flow described in the
[MCP authorization tutorial](https://modelcontextprotocol.io/docs/2026-07-28/tutorials/security/authorization).

## How the auth works

GitHub supports neither Dynamic Client Registration nor resource indicators, and
its tokens carry no audience. MCP clients need all three, so the server uses
FastMCP's `GitHubProvider` (an OAuth proxy):

```
MCP client ──(1) POST /mcp ──────────────► this server ── 401 + WWW-Authenticate
MCP client ──(2) GET  /.well-known/oauth-protected-resource/mcp
MCP client ──(3) GET  /.well-known/oauth-authorization-server
MCP client ──(4) POST /register            (dynamic client registration)
MCP client ──(5) GET  /authorize (PKCE) ─► consent page ─► github.com login
github.com ──(6) GET  /auth/callback ────► this server exchanges the code (as the OAuth client)
MCP client ──(7) POST /token ────────────► receives a JWT issued by this server
MCP client ──(8) POST /mcp + Bearer JWT ─► tools
```

- Towards GitHub, this server is the **OAuth client**: it holds the client ID and
  secret of a GitHub OAuth app and exchanges the authorization code.
- Towards MCP clients, it is the **authorization server and resource server**. The
  GitHub token never leaves the server; clients get a server-signed JWT bound to
  this server's resource URL, which avoids token passthrough.
- Every request re-validates the JWT and the upstream GitHub token.

## Setup

1. Register a GitHub OAuth app at <https://github.com/settings/developers>
   (**OAuth Apps → New OAuth App**):

   | Field | Value |
   | --- | --- |
   | Homepage URL | `http://localhost:8000` |
   | Authorization callback URL | `http://localhost:8000/auth/callback` |

   Then generate a client secret.

2. Install dependencies into the workspace venv:

   ```powershell
   uv pip install --python .venv\Scripts\python.exe -r requirements.txt
   ```

3. Configure credentials:

   ```powershell
   Copy-Item .env.example .env
   # then fill in GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET
   ```

## Run

```powershell
.venv\Scripts\python.exe server.py
```

The MCP endpoint is `http://localhost:8000/mcp`.

## Connect a client

Claude Code:

```powershell
claude mcp add --transport http oauth-demo http://localhost:8000/mcp
```

VS Code (`mcp.json`):

```json
{ "servers": { "oauth-demo": { "type": "http", "url": "http://localhost:8000/mcp" } } }
```

On first connection the client opens a browser for GitHub sign-in. Call `whoami`
to confirm the server sees your GitHub identity.

## Test

```powershell
.venv\Scripts\python.exe -m pytest tests
```

The tests cover the OAuth surface (401 challenge, metadata documents, client
registration, authorize redirect) and need no real GitHub credentials.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `GITHUB_CLIENT_ID` | required | GitHub OAuth app client ID |
| `GITHUB_CLIENT_SECRET` | required | GitHub OAuth app client secret |
| `BASE_URL` | `http://localhost:8000` | Public URL of the server |
| `HOST` / `PORT` | `127.0.0.1` / `8000` | Bind address |
| `GITHUB_SCOPES` | `read:user` | Scopes required on every token |
| `JWT_SIGNING_KEY` | derived from the client secret | Signs tokens issued to MCP clients |

For anything beyond local testing, serve over HTTPS, set `BASE_URL` to the public
URL, and set an explicit `JWT_SIGNING_KEY`.
