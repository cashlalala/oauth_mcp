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
