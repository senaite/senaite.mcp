# -*- coding: utf-8 -*-
"""The MCP tools, bound to one SENAITE client.

Each tool is a method, so the client is passed in once rather than
read from a module global, and a test can call a tool directly. The
docstrings are what an agent reads to decide how to call a tool, so
they say what to pass, what comes back and how a failure looks.
"""

from typing import Optional

from mcp.types import ToolAnnotations

READ_ONLY = ToolAnnotations(readOnlyHint=True, openWorldHint=False)
WRITE = ToolAnnotations(
    readOnlyHint=False, destructiveHint=False, openWorldHint=False)
COMPOSE = ToolAnnotations(
    readOnlyHint=False, destructiveHint=False, idempotentHint=True,
    openWorldHint=False)


def batch(limit, b_start):
    """Return the batch parameters of a listing."""
    return {"limit": limit, "b_start": b_start}


class Tools:
    """The SENAITE operations an agent may call."""

    def __init__(self, client):
        """
        :param client: the :class:`SenaiteClient` every tool calls
        """
        self.client = client

    async def senaite_version(self) -> dict:
        """Return the SENAITE JSON API version and endpoint info."""
        return await self.client.version()

    async def senaite_search(
        self,
        portal_type: str = "",
        query: Optional[dict] = None,
        limit: int = 25,
        b_start: int = 0,
    ) -> dict:
        """Search SENAITE content by any catalog index.

        The answer is a page of results: `items` holds the records,
        `count` the total number of matches, `next` is null on the
        last page. To read the next page, call again with `b_start`
        raised by `limit`. Each item carries its `uid`, which the other
        tools take, and its `path`, whose first segment is the site id.

        :param portal_type: restrict to a content type, e.g. `Client`,
            `AnalysisRequest` (a sample), `AnalysisService`, `Worksheet`
        :param query: further query keys, each a string or a list of
            strings. Common ones: `review_state` (e.g. `sample_due`),
            `q` (full text), `getClientUID`, `sort_on` (an index name),
            `sort_order` (`ascending` or `descending`), `complete`
            (`true` returns every field, not only the summary),
            `catalog` (search a particular catalog)
        :param limit: maximum number of items on one page
        :param b_start: index of the first item, for paging
        """
        params = dict(query or {})
        if portal_type:
            params["portal_type"] = portal_type
        params.update(batch(limit, b_start))
        return await self.client.search(params)

    async def senaite_get(
        self,
        uid: str = "",
        resource: str = "",
        limit: int = 25,
        b_start: int = 0,
    ) -> dict:
        """Fetch one object by uid, or list every object of a kind.

        With `uid`, the answer holds that object with all its fields.
        With `resource` alone, it is a page of objects of that kind,
        paged like `senaite_search`. With both, the uid is looked up
        within that kind.

        :param uid: the object's uid, 32 hex characters, as a search
            result gives it; `0` is the site itself
        :param resource: a content type, e.g. `Client`, or a resource
            such as `users`
        :param limit: page size of a listing
        :param b_start: index of the first item of a listing
        """
        params = None if uid else batch(limit, b_start)
        return await self.client.get(
            uid=uid or None, resource=resource or None, params=params)

    async def senaite_create(
        self,
        portal_type: str,
        parent_path: str,
        fields: Optional[dict] = None,
    ) -> dict:
        """Create one object inside a container.

        To set up a whole laboratory, use `senaite_compose` instead: it
        finds the containers and links the objects itself.

        :param portal_type: content type to create, e.g. `Client`
        :param parent_path: physical path of the container, starting
            with the site id, e.g. `/senaite/clients`. The `path` of a
            search result shows the site id and where objects of a kind
            live
        :param fields: field values by schema field name, e.g.
            `{"title": "ACME", "ClientID": "ACME"}`. A reference field
            takes the uid of the referenced object
        """
        return await self.client.create(
            portal_type, parent_path, fields or {})

    async def senaite_update(self, uid: str, fields: dict) -> dict:
        """Change fields of one object.

        The answer holds the object as stored afterwards. An older
        site may skip a field name it does not know without saying so,
        so compare the answer with what was sent.

        :param uid: the object's uid, 32 hex characters
        :param fields: field values by schema field name
        """
        return await self.client.update(uid, fields)

    async def senaite_delete(self, uid: str) -> dict:
        """Retire one object, which is what deleting means in SENAITE.

        Nothing is removed. The object gets the `deactivate`
        transition, stays in the database and its audit trail, and
        comes back with `senaite_do_transition` and `activate`. An
        object whose workflow has no `deactivate`, a sample for
        instance, is refused: retire a sample with `cancel` or
        `invalidate` instead.

        :param uid: the object's uid, 32 hex characters
        """
        return await self.client.delete(uid)

    async def senaite_do_transition(
            self, uid: str, transition: str) -> dict:
        """Move an object along its workflow, e.g. receive a sample.

        The answer holds the object in its new state. A transition the
        object does not offer in its current state, or one the login
        may not perform, fails with a message that lists the
        transitions that are valid right now.

        :param uid: the object's uid, 32 hex characters
        :param transition: workflow transition id, e.g. `receive`,
            `submit`, `verify`, `publish`, `deactivate`
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
        belongs in. Call `senaite_compose_reference` first for the
        keys a spec may use.

        Runs are idempotent: composing the same spec twice updates what
        is there instead of duplicating it, so a spec can be corrected
        and sent again. The answer lists what was created, updated and
        skipped, and per item what failed.

        Needs `senaite.composer` installed on the target site. Without
        it the call fails rather than half-building the lab.

        :param spec: the composer spec as a mapping
        """
        return await self.client.compose(spec)

    def all(self):
        """Return (tool, annotations) pairs, in the order an agent sees
        them.
        """
        return [
            (self.senaite_version, READ_ONLY),
            (self.senaite_search, READ_ONLY),
            (self.senaite_get, READ_ONLY),
            (self.senaite_create, WRITE),
            (self.senaite_update, WRITE),
            (self.senaite_delete, WRITE),
            (self.senaite_do_transition, WRITE),
            (self.senaite_compose_reference, READ_ONLY),
            (self.senaite_compose, COMPOSE),
        ]
