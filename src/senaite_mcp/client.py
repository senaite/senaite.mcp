# -*- coding: utf-8 -*-
"""Thin HTTP client for the SENAITE JSON API (v1).

The client is intentionally dumb: it maps one method to one JSON API
route and returns the parsed envelope. All orchestration (workflow
chains, composing a lab) belongs behind the API, not here.

It is asynchronous because the MCP server runs every tool on one event
loop. A blocking call would hold up every other session on an HTTP
transport for as long as SENAITE takes to answer, and composing a
whole laboratory takes a while.
"""

import re

import httpx

API_MOUNT = "@@API/senaite/v1"

# A content UID, or "0" for the portal itself
UID_RE = re.compile(r"^(0|[0-9a-f]{32})$")

# Statuses a site answers with when it sends the caller to a login form
REDIRECTS = (301, 302, 303, 307, 308)


class SenaiteError(RuntimeError):
    """Raised when the JSON API returns an error envelope or bad status."""

    def __init__(self, message, status=None, error_type=None):
        super().__init__(message)
        self.status = status
        self.error_type = error_type


def require_uid(uid):
    """Return `uid` if it addresses one object, else raise.

    An empty uid would send a PATCH or DELETE to the API root, and a
    path fragment would be joined into the URL. Neither is a uid.

    :param uid: the value an agent passed as uid
    :returns: the uid, unchanged
    :raises ValueError: when `uid` is not 32 hex characters or "0"
    """
    if not isinstance(uid, str) or not UID_RE.match(uid):
        raise ValueError(
            "Not a uid: {!r}. A uid is 32 hex characters, as the "
            "`uid` key of a search result has it".format(uid))
    return uid


class SenaiteClient:
    """HTTP client bound to a single SENAITE instance."""

    def __init__(self, settings, transport=None):
        """
        :param settings: the connection :class:`Settings`
        :param transport: an optional httpx transport, for tests
        """
        self.settings = settings
        self.api_url = "{}/{}".format(settings.base_url, API_MOUNT)
        self._client = httpx.AsyncClient(
            auth=(settings.username, settings.password),
            timeout=settings.timeout,
            verify=settings.verify_ssl,
            headers={"Accept": "application/json"},
            transport=transport,
        )

    async def close(self):
        """Close the underlying HTTP connection pool."""
        await self._client.aclose()

    # -- low level --------------------------------------------------------

    async def request(self, method, path, params=None, payload=None):
        """Perform a request against the JSON API and unwrap the result.

        :param method: HTTP verb (GET, POST, PATCH, DELETE)
        :param path: route below the v1 mount, e.g. `search` or a uid
        :param params: optional query-string mapping
        :param payload: optional JSON body mapping
        :returns: the parsed response envelope
        :raises SenaiteError: on a non-2xx status or `success: false`
        """
        url = "{}/{}".format(self.api_url, path.lstrip("/"))
        try:
            resp = await self._client.request(
                method, url, params=params, json=payload)
        except httpx.TimeoutException:
            raise SenaiteError(
                "No answer from {} within {} seconds".format(
                    self.settings.base_url, self.settings.timeout))
        except httpx.TransportError as exc:
            raise SenaiteError("Cannot reach {}: {}".format(
                self.settings.base_url, exc))
        return self._unwrap(resp)

    def _unwrap(self, resp):
        """Return the JSON envelope of `resp`, or raise what went wrong.

        The message carries the status, because an MCP host passes the
        message on to the agent and nothing else.
        """
        try:
            data = resp.json()
        except ValueError:
            raise SenaiteError(
                self._not_json(resp), status=resp.status_code)
        if not isinstance(data, dict):
            raise SenaiteError(
                "Unexpected answer ({}): not a JSON object".format(
                    resp.status_code), status=resp.status_code)
        if resp.status_code >= 400 or data.get("success") is False:
            raise SenaiteError(
                "{} {}: {}".format(
                    resp.status_code, resp.reason_phrase,
                    data.get("message", "Request failed")),
                status=resp.status_code,
                error_type=data.get("type"))
        return data

    def _not_json(self, resp):
        """Explain a response that is not JSON at all.

        The common causes are a route the site does not have, which
        answers with an error page, and a login the site refused, which
        answers with a redirect to its login form. Saying "Non-JSON
        response (404)" leaves the caller to work out which.
        """
        status = resp.status_code
        if status == 404 and "/compose" in resp.url.path:
            return ("No composer on this site: the /compose route is "
                    "not there. Install senaite.composer on {}"
                    .format(self.settings.base_url))
        if status in REDIRECTS:
            return ("Redirected ({}) instead of answered: the username "
                    "or password is wrong, or {} is not a SENAITE site"
                    .format(status, self.settings.base_url))
        return "Non-JSON response ({} {})".format(
            status, resp.reason_phrase)

    # -- high level -------------------------------------------------------

    async def version(self):
        """Return the JSON API version envelope."""
        return await self.request("GET", "version")

    async def search(self, query=None):
        """Search content; `query` is a JSON API query mapping."""
        return await self.request("GET", "search", params=query or {})

    async def get(self, uid=None, resource=None):
        """Fetch a record by uid, a resource listing, or one of a kind.

        :param uid: 32-char object uid
        :param resource: plural resource / portal_type name
        """
        if uid and resource:
            path = "{}/{}".format(resource, require_uid(uid))
        elif uid:
            path = require_uid(uid)
        elif resource:
            path = resource
        else:
            raise ValueError("Provide 'uid' and/or 'resource'")
        return await self.request("GET", path)

    async def create(self, portal_type, parent_path, fields=None):
        """Create an object of `portal_type` inside `parent_path`."""
        payload = dict(fields or {})
        payload["parent_path"] = parent_path
        return await self.request(
            "POST", "{}/create".format(portal_type), payload=payload)

    async def update(self, uid, fields):
        """Update the object addressed by `uid` with `fields`."""
        return await self.request(
            "PATCH", require_uid(uid), payload=dict(fields or {}))

    async def delete(self, uid):
        """Delete the object addressed by `uid`."""
        return await self.request("DELETE", require_uid(uid))

    async def do_transition(self, uid, transition):
        """Fire a workflow `transition` on the object `uid`."""
        return await self.request(
            "PATCH", require_uid(uid), payload={"transition": transition})

    async def compose_reference(self):
        """Return what a spec may say, as the composer reports it.

        Read from the engine's own tables on the server, so it cannot
        drift from what a compose will actually accept.
        """
        return await self.request("GET", "compose/reference")

    async def compose(self, spec):
        """Build a whole laboratory from a declarative `spec`.

        The route is provided by `senaite.composer`, which resolves the
        references between the items and puts each one in the container
        its type belongs in. A site without that add-on answers 404,
        which is the honest answer rather than a partial build.

        :param spec: the composer spec, already parsed
        :returns: the composer report, with what was created, updated
            and skipped
        """
        return await self.request("POST", "compose", payload=spec)
