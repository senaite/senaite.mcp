# Changelog

## 1.0.0 (unreleased)

Initial release.

- Tools for the SENAITE JSON API v1: version, search, get, create,
  update, do_transition and delete (which deactivates), each with MCP
  annotations
- `senaite_compose` and `senaite_compose_reference` for sites with
  `senaite.composer`
- stdio, streamable HTTP and SSE transports; Host header allowlist for
  a server behind a reverse proxy
- Login check at startup and `--check`
- Error messages that carry the HTTP status and the likely cause
