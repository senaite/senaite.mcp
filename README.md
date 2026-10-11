# senaite.mcp

An [MCP](https://modelcontextprotocol.io) server that lets an agent
work with a [SENAITE LIMS](https://www.senaite.com) site: search it,
read and change records, move samples through their workflow, and set
up a whole laboratory from one declarative spec.

It is a thin client of the SENAITE JSON API. Each tool maps to one
`senaite.jsonapi` route, and the server holds no logic of its own
beyond turning failures into messages an agent can act on. Everything
the agent does, it does as the SENAITE user the server logs in with,
with that user's permissions.

```
agent ──MCP──> senaite-mcp (Python 3) ──HTTP──> SENAITE JSON API
```

## Requirements

- Python 3.10 or newer, on any machine that can reach the site
- a SENAITE 2.x site with `senaite.jsonapi`
- a SENAITE user for the agent. Give it the roles the agent's work
  needs and no more: a lab manager login can verify and publish
- for `senaite_compose`: the `senaite.composer` add-on on the site,
  and a login holding `Manager`, since a spec creates users and grants
  roles

## Install

With [uv](https://docs.astral.sh/uv/), nothing has to be installed
first; an MCP host can run the server straight from the repository:

```bash
uvx --from git+https://github.com/senaite/senaite.mcp senaite-mcp --help
```

Or install it into a virtual environment:

```bash
git clone https://github.com/senaite/senaite.mcp
cd senaite.mcp
python3 -m venv .venv
.venv/bin/pip install -e .
```

## Configure

The server reads its connection from environment variables. Copy
`.env.example` to `.env` in the checkout and fill it in; the scripts
in `bin/` load it.

| Variable                  | Meaning                                    |
|---------------------------|--------------------------------------------|
| `SENAITE_URL`             | the site, e.g. `http://lims:8080/senaite`  |
| `SENAITE_USERNAME`        | the login (required)                       |
| `SENAITE_PASSWORD`        | its password (required)                    |
| `SENAITE_TIMEOUT`         | seconds per request, default `30`          |
| `SENAITE_COMPOSE_TIMEOUT` | seconds per compose, default `300`         |
| `SENAITE_VERIFY_SSL`      | verify TLS certificates, default `true`    |

`SENAITE_URL` points at the site, not at the server root:
`http://lims:8080/senaite`, not `http://lims:8080`. The flags `--url`
and `--username` override the variables, which is how one checkout
serves several sites. There is no password flag, because a flag shows
up in the process list.

Then check the connection:

```bash
bin/check          # or: senaite-mcp --check
```

```
login:   agent
api_url: http://lims:8080/senaite/@@API/senaite/v1
version: 2.7.0
  Client           12
  ...
```

The server makes the same login check when it starts. A site answers
a wrong password as if the caller were anonymous, with empty results
rather than an error, so the server asks the site who it is talking to
and stops when the answer is "nobody".

## Register with an MCP host

An MCP host starts the server itself and talks to it over stdin and
stdout. For Claude Code:

```bash
claude mcp add senaite -- /path/to/senaite.mcp/bin/serve
```

A second site on the same instance is a second entry with its own URL:

```bash
claude mcp add senaite2 -- /path/to/senaite.mcp/bin/serve \
  --url http://lims:8080/senaite2
```

Without a checkout, through uv, with the connection passed in:

```bash
claude mcp add senaite \
  -e SENAITE_URL=http://lims:8080/senaite \
  -e SENAITE_USERNAME=agent \
  -e SENAITE_PASSWORD=secret \
  -- uvx --from git+https://github.com/senaite/senaite.mcp senaite-mcp
```

Other hosts take the same command and environment in their own
configuration file. Restart the host after adding a server.

## Tools

| Tool                        | What it does                       |
|-----------------------------|------------------------------------|
| `senaite_version`           | API version                        |
| `senaite_search`            | search by any catalog index        |
| `senaite_get`               | one object by uid, or a listing    |
| `senaite_create`            | create one object                  |
| `senaite_update`            | change fields of one object        |
| `senaite_do_transition`     | a workflow step, e.g. `receive`    |
| `senaite_delete`            | deactivate one object (see below)  |
| `senaite_compose_reference` | what a composer spec may say       |
| `senaite_compose`           | build a laboratory from a spec     |

Searches and listings come in pages: `count` is the total, `next` is
empty on the last page, and `b_start` asks for the next one.

`senaite_delete` removes nothing. SENAITE keeps its records for the
audit trail, so the JSON API answers a delete with the `deactivate`
transition, which `activate` reverses. A sample has no `deactivate`;
it is retired with `cancel` or `invalidate`.

The tools carry MCP annotations: `version`, `search`, `get` and
`compose_reference` are marked read-only, so a host can let them run
without asking.

## Building a laboratory

`senaite_compose` takes a spec with two ordered sections: `setup` for
the configuration and `content` for clients, contacts and samples.
Each item names a `portal_type` and its `fields`. An `id` lets a later
item point at it with `{"ref": "<id>"}`, and the composer puts every
object in the container its type belongs in.

```json
{"version": 1,
 "setup": [
   {"id": "chem", "portal_type": "AnalysisCategory",
    "fields": {"title": "Chemistry"}}],
 "content": [
   {"id": "acme", "portal_type": "Client",
    "fields": {"title": "ACME", "ClientID": "ACME"}}]}
```

Runs are idempotent: sending the same spec twice updates what is there
instead of duplicating it, so an agent can correct one item and send
the whole spec again. The answer reports what was created, updated
and skipped and, per item, what failed.

An agent does not have to guess the keys. `senaite_compose_reference`
returns the sections, the item keys, the container of each type and
what a re-run recognises an object by, generated from the composer's
own tables. The spec format itself is documented in
[senaite.composer](https://github.com/senaite/senaite.composer).

## Running over the network

A reachable MCP endpoint gives whoever reaches it the same power over
SENAITE as the server's login. Treat it like the login itself. Two
ways to use a server on another machine, the first one preferred:

### SSH

The host starts the server on the remote machine over SSH. No port is
opened, and SSH does the encryption and the authentication:

```bash
claude mcp add senaite -- ssh lims.example.com /opt/senaite.mcp/bin/serve
```

The remote `.env` points `SENAITE_URL` at the site on that machine.

### HTTP

The server can listen for HTTP itself:

```bash
senaite-mcp --transport streamable-http --port 7980
```

```bash
claude mcp add --transport http senaite http://localhost:7980/mcp
```

The MCP HTTP transport has no authentication of its own, so the
server binds to `127.0.0.1` by default. Bound there it also refuses
any request whose Host header is not localhost, which protects it
against DNS rebinding. To serve other machines, put it behind a
reverse proxy that does TLS and authentication, and list the name
the proxy forwards:

```bash
senaite-mcp --transport streamable-http --allowed-host mcp.example.com
```

`--host 0.0.0.0` makes it listen on every interface and accept any
Host header. Do that only inside a network you trust, such as a VPN.

| Variable                    | Flag             | Default     |
|-----------------------------|------------------|-------------|
| `SENAITE_MCP_TRANSPORT`     | `--transport`    | `stdio`     |
| `SENAITE_MCP_HOST`          | `--host`         | `127.0.0.1` |
| `SENAITE_MCP_PORT`          | `--port`         | `7980`      |
| `SENAITE_MCP_ALLOWED_HOSTS` | `--allowed-host` | none        |

`SENAITE_MCP_ALLOWED_HOSTS` takes a comma-separated list; the flag is
repeated instead.

## Troubleshooting

The server puts the HTTP status and the likely cause into every error
message, because a host passes the message to the agent and nothing
else.

**"does not accept the login" at startup.** The username or password
is wrong. The site would have answered every call with empty results.

**"Redirected instead of answered".** The site sent the request to its
login form: wrong credentials, or `SENAITE_URL` is not a site.

**"500 Internal Server Error: Unable to get the portal object".**
`SENAITE_URL` points at the server root rather than at a site.

**"senaite.composer is not installed on this site"**, or **"No composer
on this site"** from an older composer. Add-ons are installed per
site, not per server.

**`403` on a compose.** Composing needs the permission
`senaite.composer: Compose`, which only `Manager` holds.

**`400` on a compose, before anything was built.** The spec does not
validate. The message names the problem and the item, e.g. a missing
`version`, an unknown key or two items with the same id.

**`405` on an update or a delete.** The site's JSON API does not let
`PATCH` and `DELETE` through. That needs `senaite.jsonapi` 2.7 or
newer, with `plone.jsonapi.core` 0.8 or newer.

**A field that is silently not set.** An older `senaite.jsonapi` skips
a field name it does not know and answers that all went well. Read the
object back with `senaite_get`: what comes back is what was stored.

**`421 Misdirected Request` over HTTP.** The Host header is not one
the server accepts. Add it with `--allowed-host`.

## Development

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[test]"
bin/test           # flake8, then pytest; arguments go to pytest
```

The tests run offline. An httpx mock transport stands in for the
site, so they check every request as it would go over the wire.

## License

GPLv2, see [LICENSE](LICENSE).
