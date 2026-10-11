# -*- coding: utf-8 -*-
"""The MCP tools, bound to one SENAITE client.

Each tool is a method, so the client is passed in once rather than
read from a module global, and a test can call a tool directly. The
docstrings are what an agent reads to decide how to call a tool.
"""

from typing import Optional


class Tools:
    """The SENAITE operations an agent may call."""

    def __init__(self, client):
        self.client = client

    async def senaite_version(self) -> dict:
        """Return the SENAITE JSON API version and endpoint info."""
        return await self.client.version()

    async def senaite_search(
        self,
        portal_type: str = "",
        query: Optional[dict] = None,
        limit: int = 25,
    ) -> dict:
        """Search SENAITE content.

        :param portal_type: restrict to a content type, e.g. `Client`
        :param query: extra JSON API query params (catalog indexes,
            sorting)
        :param limit: maximum number of items to return
        """
        params = dict(query or {})
        if portal_type:
            params["portal_type"] = portal_type
        params.setdefault("limit", limit)
        return await self.client.search(params)

    async def senaite_get(self, uid: str = "", resource: str = "") -> dict:
        """Fetch a record by uid, or list a resource / portal_type.

        :param uid: 32-char object uid
        :param resource: plural resource or portal_type name
        """
        return await self.client.get(
            uid=uid or None, resource=resource or None)

    async def senaite_create(
        self,
        portal_type: str,
        parent_path: str,
        fields: Optional[dict] = None,
    ) -> dict:
        """Create a content object.

        :param portal_type: content type to create, e.g. `Client`
        :param parent_path: physical path of the container, e.g.
            `/senaite/clients`
        :param fields: field values for the new object
        """
        return await self.client.create(
            portal_type, parent_path, fields or {})

    async def senaite_update(self, uid: str, fields: dict) -> dict:
        """Update the object addressed by `uid` with `fields`."""
        return await self.client.update(uid, fields)

    async def senaite_delete(self, uid: str) -> dict:
        """Delete the object addressed by `uid`."""
        return await self.client.delete(uid)

    async def senaite_do_transition(
            self, uid: str, transition: str) -> dict:
        """Fire a workflow transition on an object.

        :param uid: 32-char object uid
        :param transition: workflow transition id, e.g. `receive`,
            `submit`, `verify`, `publish`
        """
        return await self.client.do_transition(uid, transition)

    async def senaite_compose_reference(self) -> dict:
        """Return what a composer spec may say on this site.

        Read this before writing a spec. It reports the types the
        composer can place and where it puts each one, what a re-run
        recognises an existing object by, the keys an item and a
        workflow step may carry, and the field values the composer
        converts on the way in.

        It is read from the server's own tables, so it describes what a
        compose will actually accept rather than what a document says
        it should.
        """
        return await self.client.compose_reference()

    async def senaite_compose(self, spec: dict) -> dict:
        """Build a laboratory from a declarative spec, in one call.

        This is the tool to reach for when the task is "set up a lab",
        not "change one object". The spec names what to create, in two
        ordered sections, `setup` for the configuration and `content`
        for clients, contacts and samples. An item gives a
        `portal_type` and its `fields`; an `id` lets a later item point
        at it with `{"ref": "<id>"}`, and the server resolves those
        into UIDs and puts every object in the container its type
        belongs in.

        Runs are idempotent: composing the same spec twice updates what
        is there instead of duplicating it, so a spec can be corrected
        and sent again.

        Needs `senaite.composer` installed on the target site. Without
        it the call fails rather than half-building the lab.

        :param spec: the composer spec as a mapping
        """
        return await self.client.compose(spec)

    def all(self):
        """Return every tool method, in the order an agent sees them."""
        return [
            self.senaite_version,
            self.senaite_search,
            self.senaite_get,
            self.senaite_create,
            self.senaite_update,
            self.senaite_delete,
            self.senaite_do_transition,
            self.senaite_compose_reference,
            self.senaite_compose,
        ]
