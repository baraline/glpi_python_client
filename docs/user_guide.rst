User Guide
==========

The ``glpi_python_client`` package exposes a single asynchronous
:class:`glpi_python_client.GlpiClient` whose surface is built from
contract-aligned per-endpoint mixins. The client speaks the GLPI **v2**
high-level API and falls back to the legacy v1 endpoint only for binary
document uploads.

The whole client is async-only. Public methods always return Pydantic
models (or simple Python types) and never raw dictionaries.

.. contents::
   :local:
   :depth: 2

How this guide is organised
---------------------------

The guide is split into the following sections:

1. **Creating a client** — how to instantiate :class:`GlpiClient` from
   explicit parameters or from environment variables.
2. **Calling the client from synchronous code** — recommended patterns
   for one-shot scripts, long-lived sync services, and tests.
3. **Seed data for the examples** — a self-contained snippet that
   creates the records reused by every later example. Run it once on a
   throwaway GLPI instance to follow along.
4. **GLPI API interface** — the contract-aligned helpers that map
   one-to-one to GLPI v2 endpoints (tickets, timeline, team members,
   users, locations, entities, documents).
5. **Added functionalities** — helpers built on top of the API mixins:
   the aggregated ticket context view and the reporting helpers.
6. **End-to-end examples** — full workflows that combine the previous
   building blocks.

.. _create-a-client:

1. Create a client
------------------

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

Optional constructor arguments
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

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

.. _calling-from-sync-code:

2. Calling the client from synchronous code
-------------------------------------------

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

Example output::

   [42, 43, 47, 51, 58, 60, 64, 68, 70, 72]

:func:`asyncio.run` creates a fresh event loop, runs the coroutine to
completion, and closes the loop. It must **not** be called while another
event loop is already running in the same thread (for example inside
Jupyter, FastAPI, or another async framework); use one of the patterns
below instead.

Long-lived sync applications: a dedicated event loop
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

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

Example output::

   created ticket 123

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

.. _seed-data:

3. Seed data for the examples
-----------------------------

Every later snippet operates on a small, predictable set of records.
Run the seed coroutine below once against a throwaway GLPI instance to
materialise the records; the rest of the guide assumes the identifiers
it prints are available under the variable names ``location_id``,
``alice_id``, ``bob_id``, and ``ticket_id``.

.. warning::

   This guide intentionally creates and deletes real records. Always
   target a development or sandbox GLPI environment, never a production
   tenant.

.. code-block:: python

   import asyncio

   from glpi_python_client import (
       GlpiClient,
       PostFollowup,
       PostLocation,
       PostTeamMember,
       PostTicket,
       PostUser,
   )


   async def seed() -> dict[str, int]:
       """Create the demo records reused by the rest of the user guide."""

       async with GlpiClient.from_env() as client:
           location_id = await client.create_location(
               PostLocation(name="HQ Paris")
           )
           alice_id = await client.create_user(
               PostUser(
                   username="alice.dupont",
                   password="initial-pwd",
                   password2="initial-pwd",
                   realname="Dupont",
                   firstname="Alice",
               )
           )
           bob_id = await client.create_user(
               PostUser(
                   username="bob.martin",
                   password="initial-pwd",
                   password2="initial-pwd",
                   realname="Martin",
                   firstname="Bob",
               )
           )
           ticket_id = await client.create_ticket(
               PostTicket(
                   name="Wi-Fi unreachable",
                   content="802.1X handshake fails on the 5 GHz radio.",
               )
           )
           await client.add_ticket_team_member(
               ticket_id,
               PostTeamMember(type="User", id=bob_id, role="assigned"),
           )
           await client.create_ticket_followup(
               ticket_id,
               PostFollowup(content="Reproduced on the lab laptop."),
           )
           return {
               "location_id": location_id,
               "alice_id": alice_id,
               "bob_id": bob_id,
               "ticket_id": ticket_id,
           }


   if __name__ == "__main__":
       print(asyncio.run(seed()))

Example output (identifiers vary across instances)::

   {'location_id': 7, 'alice_id': 21, 'bob_id': 22, 'ticket_id': 123}

A teardown snippet to drop the seed records once the walkthrough is
complete:

.. code-block:: python

   async def cleanup(ids: dict[str, int]) -> None:
       """Delete the seed records previously created by ``seed``."""

       async with GlpiClient.from_env() as client:
           await client.delete_ticket(ids["ticket_id"], force=True)
           await client.delete_user(ids["alice_id"], force=True)
           await client.delete_user(ids["bob_id"], force=True)
           await client.delete_location(ids["location_id"], force=True)

In the rest of the guide every snippet is wrapped in an
``async with GlpiClient.from_env() as client:`` block. The integer
variables ``ticket_id``, ``alice_id``, ``bob_id``, and ``location_id``
are assumed to come from the seed dictionary above.

.. _api-interface:

4. GLPI API interface
---------------------

The helpers in this section map one-to-one to GLPI v2 endpoints. They
all return Pydantic models from the public package root.

Get / Post / Patch / Delete models
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

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
   new_id = await client.create_ticket(ticket)

   fetched = await client.get_ticket(new_id)
   print(fetched.id, fetched.name)
   print(fetched.extra_payload)

Example output::

   124 Printer offline
   {'_room_code': 'PAR-3F-12'}

Tickets
~~~~~~~

The ticket mixin exposes search, fetch, create, update, and delete
helpers under ``/Assistance/Ticket``.

.. code-block:: python

   from glpi_python_client import PatchTicket

   await client.update_ticket(
       ticket_id,
       PatchTicket(content="Updated diagnosis: radius timeout."),
   )
   ticket = await client.get_ticket(ticket_id)
   print(ticket.id, ticket.name, ticket.status)

   results = await client.search_tickets("status==1", limit=3)
   for t in results:
       print(t.id, t.name)

Example output::

   123 Wi-Fi unreachable id=1 name='New'
   123 Wi-Fi unreachable
   124 Printer offline
   125 VPN drops

``force=True`` on :meth:`GlpiClient.delete_ticket` permanently deletes
the ticket; omit it (or pass ``force=False``) to send the record to the
GLPI trash. ``search_tickets`` accepts a raw RSQL filter string and
forwards ``limit`` / ``start`` to the API for pagination.

Ticket timeline
~~~~~~~~~~~~~~~

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

   print(len(followups), len(tasks), len(solutions))
   print(followups[0].content)

Example output::

   2 1 1
   Reproduced on the lab laptop.

.. note::

   The live GLPI v2 server returns each timeline list entry wrapped in a
   ``{"type": ..., "item": {...}}`` envelope, even when the OpenAPI
   contract documents a flat array. The client unwraps that envelope
   transparently for ``list_ticket_followups``, ``list_ticket_tasks``,
   ``list_ticket_solutions``, and ``list_ticket_timeline_documents``.

Team members
~~~~~~~~~~~~

Team members are managed via ``/Assistance/Ticket/{id}/TeamMember``.

.. code-block:: python

   from glpi_python_client import PostTeamMember

   await client.add_ticket_team_member(
       ticket_id,
       PostTeamMember(type="User", id=alice_id, role="observer"),
   )
   members = await client.list_ticket_team_members(ticket_id)
   for m in members:
       print(m.id, m.type, m.name, m.role)

   await client.remove_ticket_team_member(
       ticket_id,
       team_member_id=members[0].id,
   )

Example output::

   22 User bob.martin assigned
   21 User alice.dupont observer

The OpenAPI contract marks the ``id`` field as read-only, but the live
server requires it on the ``POST`` body. The client honours the live
behaviour and exposes ``id`` as a writable field on
:class:`glpi_python_client.PostTeamMember`.

Users, locations, entities
~~~~~~~~~~~~~~~~~~~~~~~~~~

Each of these resources exposes the same ``search_ / get_ / create_ /
update_ / delete_`` shape:

.. code-block:: python

   alice = await client.get_user(alice_id)
   print(alice.id, alice.username, alice.realname, alice.firstname)

   matches = await client.search_users(f"username=={alice.username}")
   print([(u.id, u.username) for u in matches])

   location = await client.get_location(location_id)
   print(location.id, location.name)

   entities = await client.search_entities(limit=2)
   for e in entities:
       print(e.id, e.name, e.completename)

Example output::

   21 alice.dupont Dupont Alice
   [(21, 'alice.dupont')]
   7 HQ Paris
   0 Root entity Root entity
   1 Paris Root entity > Paris

Documents
~~~~~~~~~

Document metadata is handled with the standard ``Get/Post/Patch/Delete``
helpers under ``/Management/Document``. Binary content goes through two
dedicated helpers:

.. code-block:: python

   uploaded_id = await client.upload_document(
       filename="diagnostic.txt",
       content=b"link layer ok\nradius timeout 3s\n",
       mime_type="text/plain",
       ticket_id=ticket_id,
   )
   print("uploaded document", uploaded_id)

   raw_bytes = await client.download_document_content(uploaded_id)
   print(len(raw_bytes), "bytes downloaded")

Example output::

   uploaded document 88
   34 bytes downloaded

``upload_document`` requires the legacy v1 session to be configured on
the client (``v1_base_url`` and ``v1_user_token``) because the GLPI v2
contract does not advertise a binary upload endpoint.

Enums
~~~~~

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

.. code-block:: python

   from glpi_python_client import GlpiTicketStatus

   solved = await client.search_tickets(
       f"status=={int(GlpiTicketStatus.SOLVED)}", limit=2
   )
   print([(t.id, t.name) for t in solved])

Example output::

   [(120, 'Replaced toner cartridge'), (121, 'Reset VPN profile')]

.. _added-functionalities:

5. Added functionalities
------------------------

The helpers in this section are not part of the GLPI contract. They are
small utilities the client builds on top of the API mixins.

Aggregated ticket context
~~~~~~~~~~~~~~~~~~~~~~~~~

:meth:`GlpiClient.get_ticket_context` runs the ticket fetch and the four
timeline list calls concurrently and returns a single
:class:`glpi_python_client.GlpiTicketContext` model:

.. code-block:: python

   bundle = await client.get_ticket_context(ticket_id)
   print(bundle.ticket.id, bundle.ticket.name)
   print(
       len(bundle.followups),
       len(bundle.tasks),
       len(bundle.solutions),
       len(bundle.documents),
   )

Example output::

   123 Wi-Fi unreachable
   2 1 1 1

:meth:`GlpiTicketContext.to_markdown` renders the ticket title, a
metadata subtitle, and every timeline event (followups, tasks,
solutions, document links) as a single Markdown transcript. Events are
always ordered by ``date_creation``:

.. code-block:: python

   print(bundle.to_markdown())

Example output::

   # Ticket #123 — Wi-Fi unreachable
   > Status: New | Requester: Alice Dupont | Last edited by: Bob Martin | Created at: 2026-01-02T09:00:00+00:00 | Updated at: 2026-01-02T09:20:00+00:00

   ## Description

   802.1X handshake fails on the 5 GHz radio.

   ## Timeline

   ### Followup #45
   > Created by: Bob Martin | Created at: 2026-01-02T09:05:00+00:00

   Reproduced on the lab laptop.

   ### Task #12
   > Created by: Bob Martin | Created at: 2026-01-02T09:10:00+00:00 | Duration: 900s | State: Todo

   On-site visit.

   ### Solution #7
   > Created by: Bob Martin | Created at: 2026-01-02T09:20:00+00:00 | Status: Approved

   Replaced the access point.

   ## Documents
   - diagnostic.txt

Reporting helpers
~~~~~~~~~~~~~~~~~

The custom statistics mixin exposes two helpers that aggregate the
ticket and ticket-task records returned by the contract-aligned mixins.
Both return plain Python dictionaries so they can be serialised or
forwarded as-is.

``get_ticket_statistics``
^^^^^^^^^^^^^^^^^^^^^^^^^

Counts tickets created within an ISO date window and groups them by
entity, status, priority, and type.

.. code-block:: python

   stats = await client.get_ticket_statistics(
       start_date="2026-01-01",
       end_date="2026-01-31",
   )
   print(stats)

Returned shape (the outer key is always ``"entities"``; entity keys are
the GLPI numeric identifier as a string, ``"unknown"`` when missing)::

   {
       "entities": {
           "0": {
               "total": 12,
               "by_status": {"1": 5, "2": 3, "5": 4},
               "by_priority": {"LOW": 2, "MEDIUM": 7, "HIGH": 3},
               "by_type": {"INCIDENT": 9, "REQUEST": 3},
           },
           "1": {
               "total": 4,
               "by_status": {"1": 1, "5": 3},
               "by_priority": {"MEDIUM": 4},
               "by_type": {"INCIDENT": 4},
           },
       }
   }

* ``total`` — number of tickets in the entity bucket.
* ``by_status`` — keyed by the GLPI numeric status as a string; resolve
  with :class:`glpi_python_client.GlpiTicketStatus`.
* ``by_priority`` / ``by_type`` — keyed by the matching IntEnum member
  name (``"LOW"``, ``"INCIDENT"``, …); unknown values fall back to the
  raw numeric value as a string.

``get_task_statistics``
^^^^^^^^^^^^^^^^^^^^^^^

Aggregates task durations across a caller-supplied list of ticket
identifiers. GLPI does not expose a global task collection endpoint, so
callers typically collect the relevant ticket IDs through
``search_tickets`` first.

.. code-block:: python

   ticket_ids = [
       t.id for t in await client.search_tickets("status==2", limit=200)
   ]
   tasks = await client.get_task_statistics(ticket_ids)
   print(tasks)

Returned shape (durations are integer seconds, matching the GLPI
``duration`` field; user keys are the GLPI numeric user identifier as a
string, ``"unknown"`` when missing)::

   {
       "ticket_count": 3,
       "task_count": 5,
       "total_duration": 6300,
       "duration_by_user": {"22": 4500, "21": 1800},
       "duration_by_ticket": {123: 2700, 124: 1800, 125: 1800},
   }

Returned identifiers are the raw GLPI numeric values; resolve them with
the appropriate ``search_*`` helpers when human-readable labels are
needed (for example
``await client.get_user(22)`` to turn user key ``"22"`` into a full
:class:`GetUser` model).

.. _end-to-end-examples:

6. End-to-end examples
----------------------

The snippets below combine the building blocks of the previous
sections. Every example is mirrored by an integration test in
``integration_tests/test_integration.py`` (named ``test_example_*``).
They all assume the seed step from :ref:`seed-data` has been executed
and that ``ticket_id`` / ``alice_id`` / ``bob_id`` are bound to the
matching identifiers.

Example 1 — Create a ticket and read it back
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from glpi_python_client import GlpiClient, PostTicket

   async with GlpiClient.from_env() as client:
       new_id = await client.create_ticket(
           PostTicket(
               name="Printer offline",
               content="The third-floor printer cannot be reached.",
           )
       )
       context = await client.get_ticket_context(new_id)
       print(context.to_markdown())

Expected Markdown (abridged)::

   # Ticket #124 — Printer offline
   > Status: New

   ## Description

   The third-floor printer cannot be reached.

Example 2 — Add a followup response
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from glpi_python_client import PostFollowup

   await client.create_ticket_followup(
       ticket_id,
       PostFollowup(content="Capturing radius logs."),
   )
   context = await client.get_ticket_context(ticket_id)
   print(context.to_markdown())

Expected Markdown (abridged)::

   # Ticket #123 — Wi-Fi unreachable

   ## Timeline

   ### Followup #46
   > Created at: 2026-01-02T10:15:00+00:00

   Capturing radius logs.

Example 3 — Add a task with a duration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from glpi_python_client import PostTicketTask

   await client.create_ticket_task(
       ticket_id,
       PostTicketTask(
           content="On-site visit to swap the access point.",
           duration=1800,
       ),
   )
   context = await client.get_ticket_context(ticket_id)
   print(context.to_markdown())

Expected Markdown (abridged)::

   ### Task #13
   > Duration: 1800s

   On-site visit to swap the access point.

Example 4 — Close a ticket with a solution
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

GLPI moves a ticket to the *Solved* status as soon as a solution is
posted, so adding a solution is the supported way to change the ticket
status from the v2 API.

.. code-block:: python

   from glpi_python_client import PostSolution

   await client.create_ticket_solution(
       ticket_id,
       PostSolution(content="Replaced the access point firmware."),
   )
   context = await client.get_ticket_context(ticket_id)
   print(context.to_markdown())

Expected Markdown (abridged)::

   # Ticket #123 — Wi-Fi unreachable
   > Status: Solved

   ## Timeline

   ### Solution #8

   Replaced the access point firmware.

Example 5 — Upload a document to an existing ticket
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``upload_document`` accepts a ``ticket_id`` and links the new document
to the timeline in a single call. The call requires the legacy v1
session (``v1_base_url`` and ``v1_user_token``).

.. code-block:: python

   await client.upload_document(
       filename="diagnostic.txt",
       content=b"link layer ok\nradius timeout 3s\n",
       mime_type="text/plain",
       ticket_id=ticket_id,
   )
   context = await client.get_ticket_context(ticket_id)
   print(context.to_markdown())

Expected Markdown (abridged)::

   ## Documents
   - diagnostic.txt

Example 6 — Full ticket workflow with a dedicated technician
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The following script mirrors the integration test suite. It creates a
fresh ticket, exercises every timeline subresource, assigns a
technician, and tears the records down at the end.

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
                   username="bob.workflow",
                   password="initial-pwd",
                   password2="initial-pwd",
                   realname="Workflow",
                   firstname="Bob",
               )
           )
           new_ticket_id = await client.create_ticket(
               PostTicket(name="VPN drops", content="Daily VPN drops at 11:00")
           )
           try:
               await client.create_ticket_followup(
                   new_ticket_id,
                   PostFollowup(content="Reproduced on lab laptop"),
               )
               await client.create_ticket_task(
                   new_ticket_id,
                   PostTicketTask(content="Capture VPN logs", duration=1800),
               )
               await client.add_ticket_team_member(
                   new_ticket_id,
                   PostTeamMember(type="User", id=user_id, role="assigned"),
               )
               await client.create_ticket_solution(
                   new_ticket_id,
                   PostSolution(content="Upgraded VPN client"),
               )
               context = await client.get_ticket_context(new_ticket_id)
               print(context.ticket.name, len(context.followups))
           finally:
               await client.delete_ticket(new_ticket_id, force=True)
               await client.delete_user(user_id, force=True)


   asyncio.run(workflow())

Example output::

   VPN drops 1

Example 7 — Build a monthly report
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Combines :meth:`get_ticket_statistics` and :meth:`get_task_statistics`
to summarise a calendar month.

.. code-block:: python

   import asyncio

   from glpi_python_client import GlpiClient


   async def monthly_report(start: str, end: str) -> dict[str, object]:
       async with GlpiClient.from_env() as client:
           ticket_stats = await client.get_ticket_statistics(
               start_date=start, end_date=end
           )
           solved_tickets = await client.search_tickets(
               "status==5", limit=200
           )
           task_stats = await client.get_task_statistics(
               [t.id for t in solved_tickets]
           )
           return {"tickets": ticket_stats, "tasks": task_stats}


   if __name__ == "__main__":
       print(asyncio.run(monthly_report("2026-01-01", "2026-01-31")))

Example output::

   {
       'tickets': {
           'entities': {
               '0': {
                   'total': 12,
                   'by_status': {'1': 5, '2': 3, '5': 4},
                   'by_priority': {'MEDIUM': 9, 'HIGH': 3},
                   'by_type': {'INCIDENT': 9, 'REQUEST': 3},
               }
           }
       },
       'tasks': {
           'ticket_count': 4,
           'task_count': 5,
           'total_duration': 6300,
           'duration_by_user': {'22': 4500, '21': 1800},
           'duration_by_ticket': {120: 1800, 121: 900, 122: 1800, 123: 1800},
       },
   }
