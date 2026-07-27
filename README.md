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

## Run

Start your local instance first (`bin/instance fg` in the buildout root),
then:

```bash
SENAITE_URL=http://localhost:8080/senaite senaite-mcp
```

Register it with an MCP host (e.g. Claude) as a stdio server running
`senaite-mcp` with the `SENAITE_*` variables in its environment.

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
