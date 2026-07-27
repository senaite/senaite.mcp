# -*- coding: utf-8 -*-
"""Thin HTTP client for the SENAITE JSON API (v1).

The client is intentionally dumb: it maps one method to one JSON API
route and returns the parsed envelope. All orchestration (workflow
chains, composing a lab) belongs behind the API, not here.
"""

import httpx

API_MOUNT = "@@API/senaite/v1"


class SenaiteError(RuntimeError):
    """Raised when the JSON API returns an error envelope or bad status."""

    def __init__(self, message, status=None, error_type=None):
        super().__init__(message)
        self.status = status
        self.error_type = error_type


class SenaiteClient:
    """HTTP client bound to a single SENAITE instance."""

    def __init__(self, settings):
        self.settings = settings
        self.api_url = "{}/{}".format(settings.base_url, API_MOUNT)
        self._client = httpx.Client(
            auth=(settings.username, settings.password),
            timeout=settings.timeout,
            verify=settings.verify_ssl,
            headers={"Accept": "application/json"},
        )

    def close(self):
        """Close the underlying HTTP connection pool."""
        self._client.close()

    # -- low level --------------------------------------------------------

    def request(self, method, path, params=None, payload=None):
        """Perform a request against the JSON API and unwrap the result.

        :param method: HTTP verb (GET, POST, PATCH, DELETE)
        :param path: route below the v1 mount, e.g. `search` or a uid
        :param params: optional query-string mapping
        :param payload: optional JSON body mapping
        :returns: the parsed response envelope
        :raises SenaiteError: on a non-2xx status or `success: false`
        """
        url = "{}/{}".format(self.api_url, path.lstrip("/"))
        resp = self._client.request(
            method, url, params=params, json=payload)
        return self._unwrap(resp)

    def _unwrap(self, resp):
        try:
            data = resp.json()
        except ValueError:
            raise SenaiteError(
                "Non-JSON response ({})".format(resp.status_code),
                status=resp.status_code)
        if resp.status_code >= 400 or data.get("success") is False:
            raise SenaiteError(
                data.get("message", "Request failed"),
                status=resp.status_code,
                error_type=data.get("type"))
        return data

    # -- high level -------------------------------------------------------

    def version(self):
        """Return the JSON API version envelope."""
        return self.request("GET", "version")

    def search(self, query=None):
        """Search content; `query` is a JSON API query mapping."""
        return self.request("GET", "search", params=query or {})

    def get(self, uid=None, resource=None):
        """Fetch a record by uid, a resource listing, or one of a kind.

        :param uid: 32-char object uid
        :param resource: plural resource / portal_type name
        """
        if uid and resource:
            path = "{}/{}".format(resource, uid)
        elif uid:
            path = uid
        elif resource:
            path = resource
        else:
            raise ValueError("Provide 'uid' and/or 'resource'")
        return self.request("GET", path)

    def create(self, portal_type, parent_path, fields=None):
        """Create an object of `portal_type` inside `parent_path`."""
        payload = dict(fields or {})
        payload["parent_path"] = parent_path
        return self.request(
            "POST", "{}/create".format(portal_type), payload=payload)

    def update(self, uid, fields):
        """Update the object addressed by `uid` with `fields`."""
        return self.request("PATCH", uid, payload=dict(fields or {}))

    def delete(self, uid):
        """Delete the object addressed by `uid`."""
        return self.request("DELETE", uid)

    def do_transition(self, uid, transition):
        """Fire a workflow `transition` on the object `uid`."""
        return self.request(
            "PATCH", uid, payload={"transition": transition})
