# senaite.mcp

An [MCP](https://modelcontextprotocol.io) server that exposes the
SENAITE JSON API to agents. It is a thin HTTP client: each tool maps to
one `senaite.jsonapi` v1 route. All orchestration (workflow chains,
composing a whole lab via `senaite.composer`) lives behind the API in
SENAITE, not here.

## Architecture

```
agent ──MCP──> senaite.mcp (py3) ──HTTP──> senaite.jsonapi (Zope, py2.7)
```

The py2.7 SENAITE stack and this py3 server never share a runtime; they
talk over HTTP. That boundary is deliberate.

This project lives at `src/senaite.mcp` in the SENAITE buildout and
uses its own pyenv virtualenv, kept fully separate from the py2.7
buildout.

## Install

The virtualenv is pinned via `.python-version`, so pyenv activates it
automatically inside the project directory:

```bash
pyenv virtualenv 3.12.12 senaite.mcp     # once
cd src/senaite.mcp                   # auto-selects the env
pip install -e ".[test]"
pyenv rehash                              # expose the senaite-mcp script
```

## Configure

Set the target instance via environment variables (see `.env.example`).
Point it at your local SENAITE instance:

- `SENAITE_URL` (required) — site URL, e.g. `http://localhost:8080/senaite`
- `SENAITE_USERNAME` / `SENAITE_PASSWORD` — defaults `admin` / `admin`
- `SENAITE_TIMEOUT` — request timeout in seconds (default `30`)
- `SENAITE_VERIFY_SSL` — verify TLS certificates (default `true`)

## Commands

Convenience wrappers in `bin/` (they load `.env` and use the pyenv env,
so they work from any directory):

- `bin/serve` — run the MCP server (stdio). This is what an MCP host runs.
- `bin/check` — smoke-test the connection: print the API version and a
  few content counts.
- `bin/test` — run the test suite (extra args pass through to pytest).

## Run

Start your local SENAITE instance first (`bin/instance fg` in the
buildout root), then verify connectivity:

```bash
cd src/senaite.mcp
bin/check
```

## Register with an MCP host

Register `bin/serve` as a stdio server. For Claude Code:

```bash
claude mcp add senaite -- /Users/rbartl/develop/buildout/src/senaite.mcp/bin/serve
```

Connection settings come from `.env` (copy from `.env.example`). To pass
them inline instead of using `bin/serve` / `.env`:

```bash
claude mcp add senaite \
  -e SENAITE_URL=http://localhost:8080/senaite \
  -e SENAITE_USERNAME=admin \
  -e SENAITE_PASSWORD=admin \
  -- ~/.pyenv/versions/senaite.mcp/bin/senaite-mcp
```

Each SENAITE site is a separate `SENAITE_URL` (multiple sites on one host
are addressed by their path, e.g. `.../senaite`). After adding the
server, restart the MCP host so it picks up the new connection.

## Running over the network

A reachable MCP endpoint grants the caller the **same power over SENAITE
as this server's credentials** (create, transition, delete). Treat it
like the credentials themselves. There are two ways to reach a server on
a remote host, in order of preference:

### 1. SSH-tunnelled stdio (recommended)

Run the server on the remote host (next to its SENAITE) and let the MCP
host launch it over SSH. No open ports, no new auth — SSH provides the
transport, encryption and authentication:

```bash
claude mcp add senaite -- ssh user@remote /path/to/senaite.mcp/bin/serve
```

The remote `.env` points `SENAITE_URL` at the remote's local site.

### 2. HTTP transport

Run the server as an HTTP service on the remote host:

```bash
SENAITE_MCP_TRANSPORT=streamable-http SENAITE_MCP_PORT=7980 bin/serve
```

and connect from the client:

```bash
claude mcp add --transport http senaite http://remote:7980/mcp
```

The default bind host is `127.0.0.1` deliberately. The SDK's HTTP
transport has **no built-in authentication**, so do not bind a public
interface directly. Put it behind a reverse proxy with TLS and auth, an
SSH tunnel, or a VPN, and only then set `SENAITE_MCP_HOST=0.0.0.0`.

## Tools

| Tool                    | JSON API route                           |
|-------------------------|------------------------------------------|
| `senaite_version`       | `GET /version`                           |
| `senaite_search`        | `GET /search`                            |
| `senaite_get`           | `GET /<uid>` or `/<resource>/<uid>`      |
| `senaite_create`        | `POST /<portal_type>/create`             |
| `senaite_update`        | `PATCH /<uid>`                           |
| `senaite_delete`        | `DELETE /<uid>`                          |
| `senaite_do_transition` | `PATCH /<uid>` with a `transition` field |

The REST verbs (`PATCH` / `DELETE`) require senaite.jsonapi with the
REST-verb support and a JSON API framework that lets those verbs through
(plone.jsonapi.core >= 0.8.0).

## Tests

```bash
pytest
```

The bundled tests are offline: they assert that each client method maps
to the correct route without contacting a live instance.
