// Tiny front for mock-oauth2-server that adds Dynamic Client Registration (RFC 7591).
// mock-oauth2-server accepts any client_id, so "registering" just mints one.
//  - POST /<issuer>/register        -> 201 with a generated client_id
//  - GET  .well-known metadata      -> upstream document + registration_endpoint
//  - GET /<issuer>/authorize without `scope` -> 302 to the same URL with scope=openid
//                                      (the mock rejects requests that have no scope)
//  - everything else                -> proxied unchanged (Host header preserved, because
//                                      the mock derives the issuer URL from it)
const http = require('http');
const crypto = require('crypto');

const PORT = Number(process.env.PORT || 8081);
const UP = new URL(process.env.UPSTREAM || 'http://localhost:8080');

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
  'Access-Control-Allow-Headers': '*',
};

const json = (res, status, body) => {
  res.writeHead(status, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store', ...CORS });
  res.end(JSON.stringify(body));
};

const readBody = (req) =>
  new Promise((resolve) => {
    const chunks = [];
    req.on('data', (c) => chunks.push(c));
    req.on('end', () => resolve(Buffer.concat(chunks)));
  });

// /issuer1/register
const registerMatch = (p) => /^\/[^/]+\/register$/.test(p);
// /issuer1/.well-known/{openid-configuration,oauth-authorization-server}
// /.well-known/{openid-configuration,oauth-authorization-server}/issuer1
const metadataIssuer = (p) => {
  let m = p.match(/^\/([^/]+)\/\.well-known\/(?:openid-configuration|oauth-authorization-server)$/);
  if (m) return m[1];
  m = p.match(/^\/\.well-known\/(?:openid-configuration|oauth-authorization-server)\/([^/]+)$/);
  return m ? m[1] : null;
};

async function metadata(req, res, issuer) {
  const host = req.headers.host;
  // fetch() cannot override the Host header, so use http.get.
  const doc = await new Promise((resolve, reject) => {
    http.get(
      { host: UP.hostname, port: UP.port, path: `/${issuer}/.well-known/openid-configuration`, headers: { host } },
      (r) => {
        const chunks = [];
        r.on('data', (c) => chunks.push(c));
        r.on('end', () => { try { resolve(JSON.parse(Buffer.concat(chunks))); } catch (e) { reject(e); } });
      }
    ).on('error', reject);
  });
  doc.registration_endpoint = `${doc.issuer}/register`;
  doc.token_endpoint_auth_methods_supported = ['none', 'client_secret_basic', 'client_secret_post'];
  doc.scopes_supported = ['openid'];
  doc.grant_types_supported = ['authorization_code', 'refresh_token'];
  json(res, 200, doc);
}

async function register(req, res) {
  let meta = {};
  try { meta = JSON.parse((await readBody(req)).toString() || '{}'); } catch { /* ignore */ }
  const clientId = `client-${crypto.randomUUID()}`;
  json(res, 201, {
    client_id: clientId,
    client_id_issued_at: Math.floor(Date.now() / 1000),
    client_name: meta.client_name,
    redirect_uris: meta.redirect_uris || [],
    grant_types: meta.grant_types || ['authorization_code', 'refresh_token'],
    response_types: meta.response_types || ['code'],
    token_endpoint_auth_method: 'none',
    scope: meta.scope,
  });
}

async function proxy(req, res) {
  const body = await readBody(req);
  const up = http.request(
    { host: UP.hostname, port: UP.port, path: req.url, method: req.method, headers: req.headers },
    (ur) => { res.writeHead(ur.statusCode, ur.headers); ur.pipe(res); }
  );
  up.on('error', (e) => json(res, 502, { error: 'bad_gateway', error_description: e.message }));
  up.end(body);
}

http.createServer(async (req, res) => {
  const { pathname } = new URL(req.url, 'http://x');
  console.log(req.method, req.url, 'origin=' + (req.headers.origin || '-'));
  try {
    if (req.method === 'OPTIONS' && (registerMatch(pathname) || metadataIssuer(pathname))) {
      res.writeHead(204, CORS); return res.end();
    }
    if (req.method === 'POST' && registerMatch(pathname)) return await register(req, res);
    if (req.method === 'GET' && /^\/[^/]+\/authorize$/.test(pathname)) {
      const u = new URL(req.url, 'http://x');
      if (!u.searchParams.get('scope')) {
        u.searchParams.set('scope', 'openid');
        res.writeHead(302, { Location: u.pathname + u.search });
        return res.end();
      }
    }
    const issuer = req.method === 'GET' && metadataIssuer(pathname);
    if (issuer) return await metadata(req, res, issuer);
    await proxy(req, res);
  } catch (e) {
    json(res, 500, { error: 'server_error', error_description: String(e) });
  }
}).listen(PORT, () => console.log(`DCR front listening on :${PORT}, upstream ${UP.origin}`));
