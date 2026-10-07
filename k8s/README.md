# k8s deployment (port of compose.mcp.yaml)

Public endpoint: `https://dev-auth.meditek.inc:8443` (DNS -> MetalLB `1.2.3.4`, TLS offloaded by ingress-nginx)

- Issuer:  `https://dev-auth.meditek.inc:8443/issuer1`
- MCP URL: `https://dev-auth.meditek.inc:8443/mcp`

One Pod, three containers (shared localhost, like the compose network namespace).

## Deploy

```
# 1. build + push the MCP image, then set it in deployment.yaml (REGISTRY/...)
git clone --depth 1 https://github.com/modelcontextprotocol/example-remote-server.git
docker build -f mcp/Dockerfile -t <registry>/mcp-example-remote-server:latest .
docker push <registry>/mcp-example-remote-server:latest

# 2. TLS cert, proxy source (namespace srv-mke-aigateway must already exist)
kubectl -n srv-mke-aigateway create secret tls dev-auth-tls --cert=tls.crt --key=tls.key
kubectl -n srv-mke-aigateway create configmap oauth-proxy-src --from-file=server.js=proxy/server.js \
  --dry-run=client -o yaml | kubectl apply -f -

# 3. app
kubectl apply -f k8s/deployment.yaml -f k8s/service.yaml -f k8s/ingress.yaml

# 4. MetalLB IP + 8443 on the ingress-nginx Service (adjust name/namespace if different)
kubectl -n ingress-nginx patch svc ingress-nginx-controller --patch-file k8s/ingress-nginx-lb-patch.yaml
```

After editing `proxy/server.js`: re-run the configmap command and `kubectl -n srv-mke-aigateway rollout restart deploy/oauth-mcp`.

## Verify

```
curl https://dev-auth.meditek.inc:8443/issuer1/.well-known/openid-configuration   # issuer must be https://dev-auth.meditek.inc:8443/issuer1
curl https://dev-auth.meditek.inc:8443/.well-known/oauth-protected-resource
```

## Notes

- Issuer is derived by the mock from the request Host (+ `X-Forwarded-Proto`). If `issuer` in the metadata comes back as `http://...`, the mock is not honouring the forwarded proto; check this first.
- The MCP server calls the public URL for introspection; `hostAliases` points the hostname at `1.2.3.4` so this hairpins through ingress-nginx. The cert must be trusted by Node (public CA, or mount your CA and set `NODE_EXTRA_CA_CERTS`).
- Keep `replicas: 1`.
