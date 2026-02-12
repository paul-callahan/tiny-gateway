## Suggested Title

Show HN: Tiny Gateway - config-driven multi-tenant dev API gateway (JWT + RBAC + proxy)

## Draft Post

I built Tiny Gateway for local/dev environments where teams want authenticated proxying without standing up a full identity stack.

You define tenants, users, roles, and proxy rules in YAML, then run with Docker.
It includes:

- JWT login endpoint
- RBAC checks for proxied requests
- tenant/role binding (token claims must match current configured user state)
- `X-Tenant-ID` forwarding to upstream services

Quick demo:

```bash
docker compose up
```

or:

```bash
./scripts/demo.sh
```

Repo: https://github.com/paul-callahan/tiny-gateway

### Intended Use / Limitations

- Intended for development and testing workflows, not production deployment
- Configuration is file-based YAML (not a dynamic control plane)
- Authorization model is intentionally simple and endpoint-oriented
- No distributed/session storage; behavior is stateless and config-driven
- Not a replacement for full production API management platforms

