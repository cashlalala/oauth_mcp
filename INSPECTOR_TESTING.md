# Testing with the MCP Inspector CLI

Commands used to test the server's OAuth flow with
`npx @modelcontextprotocol/inspector` in CLI mode, and what each returned.

Run on 2026-10-05 against `http://localhost:8000/mcp` with Inspector 2.9.0 and
Node 22.16.0.

## Prerequisites

- The server is running: `.venv\Scripts\python.exe server.py`
- `.env` holds the GitHub OAuth app credentials (see [README.md](README.md))
- Use `@latest`. On this machine the bare package name resolved to the deprecated
  v1, whose CLI has no OAuth support.
- Inspector 2.9.0 asks for Node >= 22.19 and prints `EBADENGINE` warnings on
  22.16. It still ran correctly.

## 1. Show the CLI options

```bash
npx -y @modelcontextprotocol/inspector@latest --cli --help
```

## 2. Confirm the server demands auth

`--stored-auth-only` stops the Inspector from starting a sign-in, so with no
stored token the call must fail.

```bash
npx -y @modelcontextprotocol/inspector@latest --cli http://localhost:8000/mcp --method tools/list --stored-auth-only
```

Result (exit code 3):

```json
{"error":{"code":"auth_required","message":"Error POSTing to endpoint: "}}
```

## 3. Sign in through the OAuth flow

Without `--stored-auth-only` the Inspector runs the whole flow: it reads the
server's metadata, registers itself as a client, opens the browser, and listens
on `http://127.0.0.1:6276/oauth/callback` for the result.

```bash
npx -y @modelcontextprotocol/inspector@latest --cli http://localhost:8000/mcp --method tools/list
```

In the browser: click **Allow Access** on the server's consent page, then sign in
to GitHub.

Result (exit code 0): the three tools `echo`, `add` and `whoami`, with their
schemas.

From a shell with no terminal attached (a script, CI, an agent) the command above
fails with:

```json
{"error":{"code":"auth_required","message":"Interactive OAuth requires a TTY on stdin or stderr (or MCP_AUTO_OPEN_ENABLED=true). For CI/non-interactive runs use --stored-auth-only."}}
```

Set the variable it names to let it open the browser anyway. This is how the run
recorded here was done:

```bash
MCP_AUTO_OPEN_ENABLED=true npx -y @modelcontextprotocol/inspector@latest --cli http://localhost:8000/mcp --method tools/list
```

PowerShell equivalent:

```powershell
$env:MCP_AUTO_OPEN_ENABLED = "true"
npx -y @modelcontextprotocol/inspector@latest --cli http://localhost:8000/mcp --method tools/list
```

## 4. Call the tools with the stored token

After step 3 the token is stored, so these run without a browser.

List the tools as a single JSON object:

```bash
npx -y @modelcontextprotocol/inspector@latest --cli http://localhost:8000/mcp --method tools/list --stored-auth-only --format json
```

`whoami` — proves the server sees the GitHub identity behind the token:

```bash
npx -y @modelcontextprotocol/inspector@latest --cli http://localhost:8000/mcp --method tools/call --tool-name whoami --stored-auth-only
```

```json
{
  "content": [
    {
      "type": "text",
      "text": "{\"login\":\"cashlalala\",\"name\":\"cashlalala\",\"github_id\":\"1712483\",\"scopes\":[\"read:user\"]}"
    }
  ],
  "structuredContent": {
    "login": "cashlalala",
    "name": "cashlalala",
    "github_id": "1712483",
    "scopes": ["read:user"]
  },
  "isError": false
}
```

`add`:

```bash
npx -y @modelcontextprotocol/inspector@latest --cli http://localhost:8000/mcp --method tools/call --tool-name add --tool-arg a=2 b=3 --stored-auth-only
```

```json
{
  "content": [{ "type": "text", "text": "5.0" }],
  "structuredContent": { "result": 5 },
  "isError": false
}
```

`echo`:

```bash
npx -y @modelcontextprotocol/inspector@latest --cli http://localhost:8000/mcp --method tools/call --tool-name echo --tool-arg message=hello --stored-auth-only
```

```json
{
  "content": [{ "type": "text", "text": "hello" }],
  "structuredContent": { "result": "hello" },
  "isError": false
}
```

## 5. Sign in again from scratch

`--relogin` deletes the stored token for this server before connecting, which
forces the browser flow of step 3 again.

```bash
npx -y @modelcontextprotocol/inspector@latest --cli http://localhost:8000/mcp --method tools/list --relogin
```

This one was not run.

## Things that did not behave as expected

- **`--list-stored-auth` reported no stored servers** even though the stored
  token was working:

  ```bash
  npx -y @modelcontextprotocol/inspector@latest --cli --list-stored-auth
  ```

  ```json
  {"oauthStatePath":"C:\\Users\\cash\\.mcp-inspector\\storage\\oauth.json","storedServerUrls":[]}
  ```

  The cause was not investigated.

- **A bad token cannot be tested this way once signed in.** This call returned
  the tool list instead of an error, because the Inspector used its stored token
  rather than the header:

  ```bash
  npx -y @modelcontextprotocol/inspector@latest --cli http://localhost:8000/mcp --method tools/list --header "Authorization: Bearer not-a-real-token" --stored-auth-only
  ```

  Rejection of an invalid token is covered by `test_invalid_token_is_rejected`
  in [tests/test_auth.py](tests/test_auth.py).
