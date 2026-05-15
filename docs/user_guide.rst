User Guide
==========

The ``glpi_python_client`` package exposes a single asynchronous
:class:`glpi_python_client.GlpiClient` whose surface is built from
contract-aligned per-endpoint mixins. The client speaks the GLPI **v2**
high-level API and falls back to the legacy v1 endpoint only for binary
document uploads.

The whole client is async-only. Public methods always return Pydantic
models (or simple Python types) and never raw dictionaries.

.. _create-a-client:

Create a Client
---------------

Provide the GLPI v2 API URL and at least one complete authentication
pair. The OAuth password grant accepts either ``client_id`` /
``client_secret``, ``username`` / ``password``, or both pairs at once.

.. code-block:: python

   import asyncio

   from glpi_python_client import GlpiClient


   async def main() -> None:
       client = GlpiClient(
           glpi_api_url="https://glpi.example.com/api.php/v2",
           client_id="oauth-client-id",
           client_secret="oauth-client-secret",
           username="api-user",
           password="api-password",
           glpi_entity=1,
           glpi_profile=4,
       )
       try:
           tickets = await client.search_tickets("status==1", limit=10)
           for ticket in tickets:
               print(ticket.id, ticket.name)
       finally:
           await client.close()


   asyncio.run(main())

The client is also usable as an async context manager:

.. code-block:: python

   async with GlpiClient(glpi_api_url="...", client_id="...", client_secret="...") as client:
       tickets = await client.search_tickets("status==1")

.. _calling-from-sync-code:

Calling the Client from Synchronous Code
----------------------------------------

The client is async-only by design, but every public coroutine can be
driven from a synchronous program. The recommended patterns are listed
below in order of preference.

One-shot scripts: ``asyncio.run``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When the synchronous caller is a CLI, a cron entry, or any other
process that performs a single GLPI interaction and exits, wrap the
call in a coroutine and hand it to :func:`asyncio.run`:

.. code-block:: python

   import asyncio

   from glpi_python_client import GlpiClient


   def fetch_open_tickets() -> list[int]:
       """Return the IDs of the first ten open tickets (sync wrapper)."""

       async def _run() -> list[int]:
           async with GlpiClient.from_env() as client:
               tickets = await client.search_tickets("status==1", limit=10)
               return [ticket.id for ticket in tickets]

       return asyncio.run(_run())


   if __name__ == "__main__":
       print(fetch_open_tickets())

:func:`asyncio.run` creates a fresh event loop, runs the coroutine to
completion, and closes the loop. It must **not** be called while another
event loop is already running in the same thread (for example inside
Jupyter, FastAPI, or another async framework); use one of the patterns
below instead.

Long-lived sync applications: a dedicated event loop
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If a synchronous service needs to issue many GLPI calls during its
lifetime, building and tearing down a loop on every call is wasteful.
Open the client once on a dedicated background loop and dispatch
coroutines to it from any synchronous thread:

.. code-block:: python

   import asyncio
   import threading

   from glpi_python_client import GlpiClient, PostTicket


   class SyncGlpi:
       """Run an async ``GlpiClient`` on a background event loop."""

       def __init__(self, **client_kwargs: object) -> None:
           self._loop = asyncio.new_event_loop()
           self._thread = threading.Thread(
               target=self._loop.run_forever, name="glpi-loop", daemon=True
           )
           self._thread.start()
           self._client = GlpiClient(**client_kwargs)  # type: ignore[arg-type]

       def _submit(self, coro):  # type: ignore[no-untyped-def]
           """Schedule ``coro`` on the background loop and block on the result."""

           future = asyncio.run_coroutine_threadsafe(coro, self._loop)
           return future.result()

       def create_ticket(self, name: str, content: str) -> int:
           return self._submit(
               self._client.create_ticket(PostTicket(name=name, content=content))
           )

       def close(self) -> None:
           self._submit(self._client.close())
           self._loop.call_soon_threadsafe(self._loop.stop)
           self._thread.join()
           self._loop.close()


   if __name__ == "__main__":
       glpi = SyncGlpi(
           glpi_api_url="https://glpi.example.com/api.php/v2",
           client_id="oauth-client-id",
           client_secret="oauth-client-secret",
           username="api-user",
           password="api-password",
       )
       try:
           ticket_id = glpi.create_ticket(
               "Printer issue", "The printer is offline."
           )
           print("created ticket", ticket_id)
       finally:
           glpi.close()

This pattern keeps the OAuth token cache and the underlying HTTP
connection pool alive across calls while exposing a regular blocking
API to the rest of the application.

Calling from inside a running event loop
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Synchronous code that runs *inside* an already-running event loop (for
example a Jupyter notebook cell or a sync route in an async web
framework) cannot use :func:`asyncio.run`. Use :func:`asyncio.to_thread`
to off-load the synchronous wrapper to a worker thread, or call the
client directly with ``await`` if the surrounding code can be made
async. The :class:`SyncGlpi` helper above also works because it owns
its own loop on a separate thread.

Using GLPI helpers in test suites
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Synchronous test functions can drive the client with ``asyncio.run``
inside a small helper, which keeps the test signature plain ``def``:

.. code-block:: python

   import asyncio

   from glpi_python_client import GlpiClient


   def _run(coro):  # type: ignore[no-untyped-def]
       """Execute ``coro`` to completion on a fresh event loop."""

       return asyncio.run(coro)


   def test_search_tickets_returns_models() -> None:
       async def scenario() -> int:
           async with GlpiClient.from_env() as client:
               return len(await client.search_tickets("status==1", limit=1))

       assert _run(scenario()) >= 0

For ``pytest``-style async tests, install ``pytest-asyncio`` and mark
the coroutine directly with ``@pytest.mark.asyncio`` instead of
wrapping with ``asyncio.run``.

Optional constructor arguments include:

* ``glpi_entity`` — numeric GLPI entity ID sent as the ``GLPI-Entity`` header.
* ``glpi_profile`` — numeric GLPI profile ID sent as the ``GLPI-Profile`` header.
* ``entity_recursive`` — when ``True`` the request scope includes child
  entities.
* ``language`` — value of the ``Accept-Language`` header (defaults to
  ``"en_GB"``).
* ``verify_ssl`` — set to ``False`` only on test instances with
  self-signed certificates.
* ``auth_token_refresh`` — number of seconds before token expiry at
  which the auth manager proactively refreshes the OAuth access token.
* ``v1_base_url`` and ``v1_user_token`` — together enable the legacy v1
  fallback used by :meth:`GlpiClient.upload_document`.

``from_env``
~~~~~~~~~~~~

When the same configuration is already exposed through environment
variables, :meth:`GlpiClient.from_env` reads the ``GLPI_``-prefixed
keys and builds the client for you:

* ``GLPI_API_URL``
* ``GLPI_CLIENT_ID`` and ``GLPI_CLIENT_SECRET``
* ``GLPI_USERNAME`` and ``GLPI_PASSWORD``
* ``GLPI_ENTITY``, ``GLPI_PROFILE``, ``GLPI_ENTITY_RECURSIVE``
* ``GLPI_LANGUAGE``, ``GLPI_VERIFY_SSL``
* ``GLPI_V1_BASE_URL``, ``GLPI_V1_USER_TOKEN``, ``GLPI_V1_APP_TOKEN``

.. code-block:: python

   from glpi_python_client import GlpiClient

   client = GlpiClient.from_env()

Get / Post / Patch / Delete Models
----------------------------------

Each GLPI resource is represented by four Pydantic models named after
the verb of the HTTP operation:

* ``Get<Name>`` — what the server returns from list and read endpoints.
* ``Post<Name>`` — request body for the create endpoint.
* ``Patch<Name>`` — partial body for the update endpoint.
* ``Delete<Name>`` — optional body for the delete endpoint (typically a
  single ``force`` flag).

The full set is re-exported from the package root, including
``GetTicket`` / ``PostTicket`` / ``PatchTicket`` / ``DeleteTicket``,
``GetUser`` / ``PostUser`` / ``PatchUser`` / ``DeleteUser``,
``GetLocation`` / ``PostLocation`` / ``PatchLocation`` / ``DeleteLocation``,
``GetEntity`` / ``PostEntity`` / ``PatchEntity`` / ``DeleteEntity``,
``GetFollowup``, ``GetTicketTask``, ``GetSolution``, ``GetTimelineDocument``,
``GetTeamMember``, and ``GetDocument`` together with their post / patch /
delete variants.

All models inherit from a permissive base: the GLPI server is the
authoritative validator, so any extra keys returned by the live server
flow into the public ``extra_payload`` attribute rather than raising a
validation error. Caller-provided ``extra_payload`` keys win over
ambient extras when both are present.

.. code-block:: python

   from glpi_python_client import PostTicket

   ticket = PostTicket(
       name="Printer offline",
       content="The third-floor printer cannot be reached.",
       extra_payload={"_room_code": "PAR-3F-12"},
   )
   ticket_id = await client.create_ticket(ticket)

   fetched = await client.get_ticket(ticket_id)
   print(fetched.id, fetched.name)
   print(fetched.extra_payload)  # plugin keys returned by the server

Tickets
-------

The ticket mixin exposes search, fetch, create, update, and delete
helpers under ``/Assistance/Ticket``.

.. code-block:: python

   from glpi_python_client import PatchTicket, PostTicket

   ticket_id = await client.create_ticket(
       PostTicket(name="Wi-Fi unreachable", content="802.1X failure")
   )
   try:
       await client.update_ticket(
           ticket_id,
           PatchTicket(content="Updated diagnosis"),
       )
       ticket = await client.get_ticket(ticket_id)
       results = await client.search_tickets("status==1", limit=20)
   finally:
       await client.delete_ticket(ticket_id, force=True)

``force=True`` permanently deletes the ticket; omit it (or pass
``force=False``) to send the record to the GLPI trash.

``search_tickets`` accepts a raw RSQL filter string and forwards
``limit`` / ``start`` to the API for pagination.

Ticket Timeline
---------------

The ticket timeline groups followups, tasks, solutions, and document
links under ``/Assistance/Ticket/{id}/Timeline/{Followup|Task|Solution|Document}``.
Each subresource exposes the same ``list_ / get_ / create_ / update_ /
delete_`` shape (``link_`` / ``unlink_`` for documents).

.. code-block:: python

   from glpi_python_client import (
       PostFollowup,
       PostSolution,
       PostTicketTask,
   )

   followup_id = await client.create_ticket_followup(
       ticket_id,
       PostFollowup(content="Triaged: ongoing"),
   )
   task_id = await client.create_ticket_task(
       ticket_id,
       PostTicketTask(content="On-site visit", duration=900),
   )
   solution_id = await client.create_ticket_solution(
       ticket_id,
       PostSolution(content="Replaced the access point"),
   )

   followups = await client.list_ticket_followups(ticket_id)
   tasks = await client.list_ticket_tasks(ticket_id)
   solutions = await client.list_ticket_solutions(ticket_id)

.. note::

   The live GLPI v2 server returns each timeline list entry wrapped in a
   ``{"type": ..., "item": {...}}`` envelope, even when the OpenAPI
   contract documents a flat array. The client unwraps that envelope
   transparently for ``list_ticket_followups``, ``list_ticket_tasks``,
   ``list_ticket_solutions``, and ``list_ticket_timeline_documents``.

Team Members
------------

Team members are managed via ``/Assistance/Ticket/{id}/TeamMember``.

.. code-block:: python

   from glpi_python_client import PostTeamMember

   await client.add_ticket_team_member(
       ticket_id,
       PostTeamMember(type="User", id=42, role="assigned"),
   )

   members = await client.list_ticket_team_members(ticket_id)

   await client.remove_ticket_team_member(
       ticket_id,
       team_member_id=members[0].id,
   )

The OpenAPI contract marks the ``id`` field as read-only, but the live
server requires it on the ``POST`` body. The client honours the live
behaviour and exposes ``id`` as a writable field on
:class:`glpi_python_client.PostTeamMember`.

Users, Locations, Entities
--------------------------

Each of these resources exposes the same ``search_ / get_ / create_ /
update_ / delete_`` shape:

.. code-block:: python

   from glpi_python_client import PostLocation, PostUser

   user_id = await client.create_user(
       PostUser(
           username="alice.dupont",
           password="initial-pwd",
           password2="initial-pwd",
           realname="Dupont",
           firstname="Alice",
       )
   )
   location_id = await client.create_location(PostLocation(name="HQ Paris"))

   user = await client.get_user(user_id)
   users = await client.search_users(f"username=={user.username}")
   entities = await client.search_entities("name==Root entity")

Documents
---------

Document metadata is handled with the standard ``Get/Post/Patch/Delete``
helpers under ``/Management/Document``. Binary content goes through two
dedicated helpers:

.. code-block:: python

   raw_bytes = await client.download_document_content(document_id)

   uploaded = await client.upload_document(
       filename="diagnostic.png",
       content=raw_bytes,
       mime_type="image/png",
       ticket_id=ticket_id,
   )

``upload_document`` requires the legacy v1 session to be configured on
the client (``v1_base_url`` and ``v1_user_token``) because the GLPI v2
contract does not advertise a binary upload endpoint.

Aggregated Ticket Context
-------------------------

:meth:`GlpiClient.get_ticket_context` runs the ticket fetch and the four
timeline list calls concurrently and returns a single
:class:`glpi_python_client.GlpiTicketContext` model:

.. code-block:: python

   bundle = await client.get_ticket_context(ticket_id)
   print(bundle.ticket.id, bundle.ticket.name)
   print(len(bundle.followups), len(bundle.tasks))
   print(len(bundle.solutions), len(bundle.documents))

Reporting Helpers
-----------------

The custom statistics mixin exposes two helpers built on top of the
contract-aligned mixins:

.. code-block:: python

   from glpi_python_client import GlpiTicketStatus, GlpiTicketType

   ticket_stats = await client.get_ticket_statistics(
       start_date="2026-01-01",
       end_date="2026-01-31",
   )

   ticket_ids = [t.id for t in await client.search_tickets("status==2", limit=200)]
   task_stats = await client.get_task_statistics(ticket_ids)

   print(ticket_stats["entities"])
   print(task_stats["total_duration"], task_stats["duration_by_user"])

Returned identifiers are the raw GLPI numeric values; resolve them with
the appropriate ``search_*`` helpers when human-readable labels are
needed.

Enums
-----

Public IntEnum classes mirror the GLPI numeric constants and stay at
the package root for easy use in RSQL filters:
:class:`glpi_python_client.GlpiTicketStatus`,
:class:`glpi_python_client.GlpiTicketType`,
:class:`glpi_python_client.GlpiPriority`,
:class:`glpi_python_client.GlpiTaskState`,
:class:`glpi_python_client.GlpiSolutionStatus`,
:class:`glpi_python_client.GlpiTimelinePosition`,
:class:`glpi_python_client.GlpiUserAuthType`, and
:class:`glpi_python_client.GlpiGlobalValidation`.

End-to-End Example
------------------

The following example mirrors the integration test suite:

.. code-block:: python

   import asyncio

   from glpi_python_client import (
       GlpiClient,
       PostFollowup,
       PostSolution,
       PostTeamMember,
       PostTicket,
       PostTicketTask,
       PostUser,
   )


   async def workflow() -> None:
       async with GlpiClient.from_env() as client:
           user_id = await client.create_user(
               PostUser(
                   username="bob.martin",
                   password="initial-pwd",
                   password2="initial-pwd",
                   realname="Martin",
                   firstname="Bob",
               )
           )
           ticket_id = await client.create_ticket(
               PostTicket(name="VPN drops", content="Daily VPN drops at 11:00")
           )
           try:
               await client.create_ticket_followup(
                   ticket_id,
                   PostFollowup(content="Reproduced on lab laptop"),
               )
               await client.create_ticket_task(
                   ticket_id,
                   PostTicketTask(content="Capture VPN logs", duration=1800),
               )
               await client.add_ticket_team_member(
                   ticket_id,
                   PostTeamMember(type="User", id=user_id, role="assigned"),
               )
               await client.create_ticket_solution(
                   ticket_id,
                   PostSolution(content="Upgraded VPN client"),
               )
               context = await client.get_ticket_context(ticket_id)
               print(context.ticket.name, len(context.followups))
           finally:
               await client.delete_ticket(ticket_id, force=True)
               await client.delete_user(user_id, force=True)


   asyncio.run(workflow())
