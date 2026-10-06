// mock-oauth2-server requires client authentication on /introspect, but the example
// server's ExternalTokenValidator sends none. Add optional HTTP Basic auth from env.
const fs = require('fs');
const file = 'src/interfaces/auth-validator.ts';
const src = fs.readFileSync(file, 'utf8');
const needle = "'Content-Type': 'application/x-www-form-urlencoded'";
if (!src.includes(needle)) throw new Error('patch target not found');
const patched = src.replace(needle, needle + `,
          ...(process.env.INTROSPECT_CLIENT_ID
            ? { Authorization: 'Basic ' + Buffer.from(
                \`\${process.env.INTROSPECT_CLIENT_ID}:\${process.env.INTROSPECT_CLIENT_SECRET ?? ''}\`
              ).toString('base64') }
            : {})`);
fs.writeFileSync(file, patched);

// In external mode the server answers 401 with
//   WWW-Authenticate: ... resource_metadata=".../.well-known/oauth-protected-resource"
// but never serves that document (only internal mode gets it, via mcpAuthRouter), so
// clients such as MCP Inspector fail with 404. Serve RFC 9728 Protected Resource Metadata.
{
  const idx = 'src/index.ts';
  const code = fs.readFileSync(idx, 'utf8');
  const marker = '  // Initialize modules based on auth mode';
  if (!code.includes(marker)) throw new Error('index.ts patch target not found');
  const route = `  if (config.auth.mode === 'external') {
    app.get(
      ['/.well-known/oauth-protected-resource', '/.well-known/oauth-protected-resource/mcp'],
      (_req, res) => {
        res.json({
          resource: \`\${config.baseUri}/mcp\`,
          authorization_servers: [config.auth.externalUrl],
          bearer_methods_supported: ['header'],
        });
      }
    );
  }

`;
  fs.writeFileSync(idx, code.replace(marker, route + marker));
}
