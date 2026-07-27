User Guide
==========

The ``glpi_python_client`` package exposes two high-level clients
whose surface is built from contract-aligned per-endpoint mixins:

* :class:`glpi_python_client.GlpiClient` — synchronous, blocking
  client.
* :class:`glpi_python_client.AsyncGlpiClient` — asynchronous client
  doing real non-blocking I/O on the event loop.

Neither is a wrapper around the other; both are the same code, as
*Sync vs async surface* below explains.

Both clients speak the GLPI **v2** high-level API and fall back to the
legacy v1 API for features that are not exposed by v2, currently
binary document uploads and the ``Fields`` plugin custom-field
helpers. They expose the exact same endpoint methods and accept the
same constructor arguments.
Public methods always return Pydantic models (or simple Python types)
and never raw dictionaries.

.. contents::
   :local:
   :depth: 2

How this guide is organised
---------------------------

The guide is split into the following sections:

1. **Creating a client** — how to instantiate either client from
   explicit parameters or from environment variables.
2. **Sync vs async surface** — when to pick which client and how both
   are produced from a single source.
3. **Seed data for the examples** — a self-contained snippet that
   creates the records reused by every later example. Run it once on a
   throwaway GLPI instance to follow along.
4. **GLPI API interface** — the contract-aligned helpers that map
   one-to-one to GLPI v2 endpoints (tickets, timeline, team members,
   users, locations, entities, documents).
5. **Added functionalities** — helpers built on top of the API mixins:
    the ``Fields`` plugin custom-field helpers, the aggregated ticket
    context view, and the reporting helpers.
6. **End-to-end examples** — full workflows that combine the previous
   building blocks.
7. **Error handling** — the public exception hierarchy, what each
   branch means, and how retries behave.

The sample snippets in sections 3 to 6 use the synchronous
:class:`GlpiClient`. Every snippet works on the asynchronous client by
replacing ``with ... as client:`` with ``async with ... as client:`` and
prefixing every client method call with ``await`` — the public method
names and signatures are identical.

.. _create-a-client:

1. Create a client
------------------

Provide the GLPI v2 API URL and at least one complete authentication
pair. The OAuth password grant accepts either ``client_id`` /
``client_secret``, ``username`` / ``password``, or both pairs at once.

.. code-block:: python

   from glpi_python_client import GlpiClient

   with GlpiClient(
       glpi_api_url="https://glpi.example.com/api.php/v2",
       client_id="oauth-client-id",
       client_secret="oauth-client-secret",
       username="api-user",
       password="api-password",
       glpi_entity=1,
       glpi_profile=4,
   ) as client:
       tickets = client.search_tickets("status==1", limit=10)
       for ticket in tickets:
           print(ticket.id, ticket.name)

The asynchronous client takes the same arguments and is used inside an
``async with`` block:

.. code-block:: python

   import asyncio

   from glpi_python_client import AsyncGlpiClient


   async def main() -> None:
       async with AsyncGlpiClient(
           glpi_api_url="https://glpi.example.com/api.php/v2",
           client_id="oauth-client-id",
           client_secret="oauth-client-secret",
           username="api-user",
           password="api-password",
       ) as client:
           tickets = await client.search_tickets("status==1", limit=10)
           for ticket in tickets:
               print(ticket.id, ticket.name)


   asyncio.run(main())

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
    fallback used by :meth:`GlpiClient.upload_document` and the
    ``Fields`` plugin helpers such as
    :meth:`GlpiClient.get_ticket_custom_fields`.

``from_env``
~~~~~~~~~~~~

When the same configuration is already exposed through environment
variables, :meth:`GlpiClient.from_env` (and
:meth:`AsyncGlpiClient.from_env`) read the ``GLPI_``-prefixed keys and
build the client for you:

* ``GLPI_API_URL``
* ``GLPI_CLIENT_ID`` and ``GLPI_CLIENT_SECRET``
* ``GLPI_USERNAME`` and ``GLPI_PASSWORD``
* ``GLPI_ENTITY``, ``GLPI_PROFILE``, ``GLPI_ENTITY_RECURSIVE``
* ``GLPI_LANGUAGE``, ``GLPI_VERIFY_SSL``
* ``GLPI_V1_BASE_URL``, ``GLPI_V1_USER_TOKEN``, ``GLPI_V1_APP_TOKEN``

.. code-block:: python

   from glpi_python_client import AsyncGlpiClient, GlpiClient

   sync_client = GlpiClient.from_env()
   async_client = AsyncGlpiClient.from_env()

.. _sync-vs-async:

2. Sync vs async surface
------------------------

Both :class:`GlpiClient` and :class:`AsyncGlpiClient` expose the same
public endpoint methods. The parity is enforced by a unit test so any
new sync endpoint is automatically reflected on the async client.

When to pick which
~~~~~~~~~~~~~~~~~~

* Use :class:`GlpiClient` for plain Python scripts, CLI tools, cron
  entries, and synchronous services. No event loop, no ``await``.
* Use :class:`AsyncGlpiClient` when your application already runs an
  event loop (for example a FastAPI or aiohttp service, an async CLI,
  or a Jupyter notebook cell), or when you want concurrent fan-out.

How the two clients stay in step
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Both clients are the same code. The asynchronous tree is written by hand
and the synchronous one is *generated* from it: a build step strips
``async``/``await`` and renames the handful of tokens that differ between
the two surfaces. The generated tree is committed, and CI regenerates it
and fails on any difference, so the two cannot drift apart.

This is why the endpoint surfaces are identical and why a fix never has
to be applied twice. It also means neither client is a wrapper around the
other: :class:`AsyncGlpiClient` performs real non-blocking I/O on the
event loop, and :class:`GlpiClient` performs real blocking I/O with no
thread pool, no executor, and no coroutine scheduling.

Exactly one module is maintained separately for each surface, because the
two need genuinely different primitives rather than differently-spelled
ones:

* **Fan-out.** Aggregating helpers such as
  :meth:`AsyncGlpiClient.get_ticket_context` issue several GLPI calls
  through a shared ``gather`` helper. On the async surface that is
  :func:`asyncio.gather` and the calls overlap; on the sync surface the
  arguments have already been evaluated by the time ``gather`` is
  entered, so the same expression means "one after the other". The
  calling code is identical.
* **The auth lock.** :class:`AsyncGlpiClient` uses an
  :class:`asyncio.Lock` and :class:`GlpiClient` a
  :class:`threading.Lock`. Neither substitutes for the other. A
  :class:`threading.Lock` on the event loop would be held across an
  ``await``, so a second task waiting on it would block the loop and the
  task holding it could never resume to release it. An
  :class:`asyncio.Lock` in the sync client would bind itself to whichever
  event loop first contended it, breaking the guarantee that one
  :class:`GlpiClient` may be shared across threads.

Pagination helpers (``iter_search_tickets``, ``iter_search_users``,
``iter_search_entities``) are exposed as **async generators** on the
async client. Iterate them with ``async for`` to walk every page
without blocking the event loop:

.. code-block:: python

   async for batch in client.iter_search_tickets("status==1", batch_size=200):
       for ticket in batch:
           ...

The synchronous versions of the same helpers issue the calls
sequentially.

Bounding concurrency
~~~~~~~~~~~~~~~~~~~~

There is no thread pool to size and no ``executor`` argument: the async
client issues real non-blocking requests, so concurrency is bounded by
the underlying HTTP connection pool rather than by worker threads.

To keep a large fan-out from overwhelming the GLPI server, bound it on
your side with an :class:`asyncio.Semaphore`:

.. code-block:: python

   import asyncio

   from glpi_python_client import AsyncGlpiClient


   async def main() -> None:
       limit = asyncio.Semaphore(8)

       async with AsyncGlpiClient.from_env() as client:

           async def fetch(ticket_id: int):
               async with limit:
                   return await client.get_ticket(ticket_id)

           tickets = await asyncio.gather(*(fetch(i) for i in range(1, 101)))
           print(len(tickets))


   asyncio.run(main())

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

   from glpi_python_client import (
       GlpiClient,
       PostFollowup,
       PostLocation,
       PostTeamMember,
       PostTicket,
       PostUser,
   )


   def seed() -> dict[str, int]:
       """Create the demo records reused by the rest of the user guide."""

       with GlpiClient.from_env() as client:
           location_id = client.create_location(
               PostLocation(name="HQ Paris")
           )
           alice_id = client.create_user(
               PostUser(
                   username="alice.dupont",
                   password="initial-pwd",
                   password2="initial-pwd",
                   realname="Dupont",
                   firstname="Alice",
               )
           )
           bob_id = client.create_user(
               PostUser(
                   username="bob.martin",
                   password="initial-pwd",
                   password2="initial-pwd",
                   realname="Martin",
                   firstname="Bob",
               )
           )
           ticket_id = client.create_ticket(
               PostTicket(
                   name="Wi-Fi unreachable",
                   content="802.1X handshake fails on the 5 GHz radio.",
               )
           )
           client.add_ticket_team_member(
               ticket_id,
               PostTeamMember(type="User", id=bob_id, role="assigned"),
           )
           client.create_ticket_followup(
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
       print(seed())

Example output (identifiers vary across instances)::

   {'location_id': 7, 'alice_id': 21, 'bob_id': 22, 'ticket_id': 123}

A teardown snippet to drop the seed records once the walkthrough is
complete:

.. code-block:: python

   def cleanup(ids: dict[str, int]) -> None:
       """Delete the seed records previously created by ``seed``."""

       with GlpiClient.from_env() as client:
           client.delete_ticket(ids["ticket_id"], force=True)
           client.delete_user(ids["alice_id"], force=True)
           client.delete_user(ids["bob_id"], force=True)
           client.delete_location(ids["location_id"], force=True)

In the rest of the guide every snippet is wrapped in an
``with GlpiClient.from_env() as client:`` block. The integer
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
   new_id = client.create_ticket(ticket)

   fetched = client.get_ticket(new_id)
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

   client.update_ticket(
       ticket_id,
       PatchTicket(content="Updated diagnosis: radius timeout."),
   )
   ticket = client.get_ticket(ticket_id)
   print(ticket.id, ticket.name, ticket.status)

   results = client.search_tickets("status==1", limit=3)
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

   followup_id = client.create_ticket_followup(
       ticket_id,
       PostFollowup(content="Triaged: ongoing"),
   )
   task_id = client.create_ticket_task(
       ticket_id,
       PostTicketTask(content="On-site visit", duration=900),
   )
   solution_id = client.create_ticket_solution(
       ticket_id,
       PostSolution(content="Replaced the access point"),
   )

   followups = client.list_ticket_followups(ticket_id)
   tasks = client.list_ticket_tasks(ticket_id)
   solutions = client.list_ticket_solutions(ticket_id)

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

   client.add_ticket_team_member(
       ticket_id,
       PostTeamMember(type="User", id=alice_id, role="observer"),
   )
   members = client.list_ticket_team_members(ticket_id)
   for m in members:
       print(m.id, m.type, m.name, m.role)

   client.remove_ticket_team_member(
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

   alice = client.get_user(alice_id)
   print(alice.id, alice.username, alice.realname, alice.firstname)

   matches = client.search_users(f"username=={alice.username}")
   print([(u.id, u.username) for u in matches])

   location = client.get_location(location_id)
   print(location.id, location.name)

   entities = client.search_entities(limit=2)
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

   uploaded_id = client.upload_document(
       filename="diagnostic.txt",
       content=b"link layer ok\nradius timeout 3s\n",
       mime_type="text/plain",
       ticket_id=ticket_id,
   )
   print("uploaded document", uploaded_id)

   raw_bytes = client.download_document_content(uploaded_id)
   print(len(raw_bytes), "bytes downloaded")

Example output::

   uploaded document 88
   34 bytes downloaded

``upload_document`` requires the legacy v1 session to be configured on
the client (``v1_base_url`` and ``v1_user_token``) because the GLPI v2
contract does not advertise a binary upload endpoint.

Knowledge base
~~~~~~~~~~~~~~

The knowledge base mixins map to ``/Knowledgebase``. Articles and
categories expose the ``search_ / get_ / create_ / update_ / delete_``
shape; comments are nested under an article; revisions are read-only.
Article ``content`` and ``description`` accept and return Markdown. An
article's ``categories`` association is read-only in the v2 GLPI contract,
so the client sets it through a legacy fallback — see
`Assigning categories`_.

.. note::

   The Knowledge base API was introduced in the GLPI High-Level API
   **2.2.0**. Instances serving an older API version (e.g. 2.1.0) do not
   expose ``/Knowledgebase`` and these helpers will raise a
   ``ValueError`` (HTTP 404).

.. code-block:: python

   from glpi_python_client import (
       PostKBArticle,
       PostKBArticleComment,
       PostKBCategory,
   )

   client.create_kb_category(PostKBCategory(name="Networking"))
   categories = client.search_kb_categories("name==Networking")
   print([c.name for c in categories])

   article_id = client.create_kb_article(
       PostKBArticle(
           name="Reset a Wi-Fi controller",
           content="Hold **reset** for 10s, then re-provision.",
           is_faq=True,
       )
   )
   client.create_kb_article_comment(
       article_id,
       PostKBArticleComment(comment="Confirmed on firmware 4.2."),
   )

   article = client.get_kb_article(article_id)
   print(article.id, article.name)

   faq = client.search_kb_articles("is_faq==1", limit=10)
   for entry in faq:
       print(entry.id, entry.name)

   revisions = client.list_kb_article_revisions(article_id)
   print(len(revisions), "revision(s)")

Example output::

   ['Networking']

Assigning categories
^^^^^^^^^^^^^^^^^^^^^

On GLPI 11 the v2 API cannot write a KB article's categories (the nested
``categories[].id`` is ``readOnly`` and category writes are silently
dropped). GLPI 11 stores KB categories as a many-to-many relationship that
only the legacy ``apirest.php`` can write, so the client applies categories
through the legacy v1 session. Configure ``v1_base_url`` / ``v1_user_token``
(pointing at the legacy ``apirest.php``) and either pass ``categories`` on
create/update or call the helper directly. The supplied ids replace the
article's full category set; passing an empty list clears every category.

.. code-block:: python

   from glpi_python_client import IdNameRef

   # Categories set on create are applied via the legacy fallback. The
   # create is atomic: if the assignment fails, the new article is rolled
   # back and the error is re-raised.
   article_id = client.create_kb_article(
       PostKBArticle(
           name="Reset a Wi-Fi controller",
           content="Hold **reset** for 10s.",
           categories=[IdNameRef(id=14)],
       )
   )

   # Or set them explicitly at any time.
   client.set_kb_article_categories(article_id, [14])  # replace the full set
   client.set_kb_article_categories(article_id, [])    # clear all
   42 Reset a Wi-Fi controller
   42 Reset a Wi-Fi controller
   1 revision(s)

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

   solved = client.search_tickets(
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

Ticket custom fields via the Fields plugin
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The `Fields plugin <https://github.com/pluginsGLPI/fields>`_ exposes
ticket custom fields through the legacy v1 API rather than the GLPI v2
contract. Configure the client with ``v1_base_url`` and
``v1_user_token`` (or the matching ``GLPI_V1_*`` environment
variables), then use the discovery helpers when you need the plugin's
internal container and field names:

.. code-block:: python

    from glpi_python_client import GlpiClient

   with GlpiClient(
       glpi_api_url="https://glpi.example.com/api.php/v2",
       client_id="oauth-client-id",
       client_secret="oauth-client-secret",
       username="api-user",
       password="api-password",
       v1_base_url="https://glpi.example.com/apirest.php",
       v1_user_token="legacy-user-token",
   ) as client:
       containers = client.list_plugin_fields_containers(itemtype="Ticket")
       for container in containers:
           print(container.id, container.name)
           fields = client.list_plugin_fields_fields(container_id=container.id)
           print([field.name for field in fields])

       custom_fields = client.get_ticket_custom_fields(ticket_id)
       print(custom_fields)

       client.set_ticket_custom_fields(
           ticket_id,
           {
               "aidelarsolution": {
                   "aidelarsolutionfield": "<p>Handled by the NOC shift</p>",
               }
           },
       )

The high-level ``get_ticket_custom_fields`` /
``set_ticket_custom_fields`` pair uses the mapping
``{container_name: {field_name: value}}`` and automatically decides
whether the v1 plugin needs a row creation or an in-place update. Drop
to ``list_item_plugin_field_rows``, ``create_item_plugin_field_row``,
or ``update_item_plugin_field_row`` only when you need the raw v1 row
shape.

Aggregated ticket context
~~~~~~~~~~~~~~~~~~~~~~~~~

:meth:`GlpiClient.get_ticket_context` runs the ticket fetch and the four
timeline list calls concurrently and returns a single
:class:`glpi_python_client.GlpiTicketContext` model:

.. code-block:: python

   bundle = client.get_ticket_context(ticket_id)
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

Customising the Markdown output
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Pass a :class:`TicketMarkdownOptions` instance to select which sections
and metadata fields appear in the output. All flags default to ``True``
so the default call reproduces the full transcript shown above.

+-------------------------------+----------------------------------------------+
| Flag                          | Controls                                     |
+===============================+==============================================+
| ``include_description``       | ``## Description`` section                   |
+-------------------------------+----------------------------------------------+
| ``include_followups``         | Followup entries in ``## Timeline``          |
+-------------------------------+----------------------------------------------+
| ``include_tasks``             | Task entries in ``## Timeline``              |
+-------------------------------+----------------------------------------------+
| ``include_solutions``         | Solution entries in ``## Timeline``          |
+-------------------------------+----------------------------------------------+
| ``include_documents``         | ``## Documents`` section                     |
+-------------------------------+----------------------------------------------+
| ``show_status``               | ``Status`` in the ticket subtitle            |
+-------------------------------+----------------------------------------------+
| ``show_requester``            | ``Requester`` in the ticket subtitle         |
+-------------------------------+----------------------------------------------+
| ``show_editor``               | ``Last edited by`` in the ticket subtitle    |
+-------------------------------+----------------------------------------------+
| ``show_dates``                | All ticket-level date fields                 |
+-------------------------------+----------------------------------------------+
| ``show_event_author``         | ``Created by`` in event subtitles            |
+-------------------------------+----------------------------------------------+
| ``show_event_editor``         | ``Last edited by`` in event subtitles        |
+-------------------------------+----------------------------------------------+
| ``show_event_dates``          | All date fields in event subtitles           |
+-------------------------------+----------------------------------------------+
| ``show_event_state``          | ``State`` in event subtitles                 |
+-------------------------------+----------------------------------------------+
| ``show_event_status``         | ``Status`` in event subtitles                |
+-------------------------------+----------------------------------------------+
| ``show_duration``             | ``Duration`` in task subtitles               |
+-------------------------------+----------------------------------------------+
| ``show_technician``           | ``Technician`` / ``Technician group``        |
+-------------------------------+----------------------------------------------+
| ``show_approver``             | ``Approver`` in solution subtitles           |
+-------------------------------+----------------------------------------------+

Example — description and timeline only, no metadata fields:

.. code-block:: python

   from glpi_python_client import TicketMarkdownOptions

   opts = TicketMarkdownOptions(
       include_documents=False,
       show_status=False,
       show_requester=False,
       show_editor=False,
       show_dates=False,
       show_event_author=False,
       show_event_editor=False,
       show_event_dates=False,
       show_event_state=False,
       show_event_status=False,
       show_duration=False,
       show_technician=False,
       show_approver=False,
   )
   print(bundle.to_markdown(opts))

Reporting helpers
~~~~~~~~~~~~~~~~~

The custom statistics mixin exposes several helpers that aggregate the
ticket and ticket-task records returned by the contract-aligned mixins.
They all return plain Python dictionaries so they can be serialised or
forwarded as-is.

Streaming pagination with ``iter_search_*``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The ``search_*`` helpers return one page at a time and require the
caller to manage the ``start`` cursor. The companion ``iter_search_*``
generators handle pagination automatically by yielding successive
batches until the API returns fewer rows than the requested
``batch_size`` (the natural end-of-stream signal):

* :meth:`GlpiClient.iter_search_tickets`
* :meth:`GlpiClient.iter_search_users`
* :meth:`GlpiClient.iter_search_entities`

.. code-block:: python

   # Walk every "open" ticket without loading the full result set in memory.
   total = 0
   for batch in client.iter_search_tickets("status==1", batch_size=200):
       total += len(batch)
       for ticket in batch:
           print(ticket.id, ticket.name)
   print(f"processed {total} tickets")

.. note::

   Always pass an RSQL filter to ``iter_search_tickets``. Querying
   without any filter can return very large result sets and may cause
   the GLPI server to return a 500 errors.

On the asynchronous client the same helpers are exposed as **async
generators** through the bridge, so each ``next()`` call runs off the
event loop and the consumer uses ``async for``:

.. code-block:: python

   async for batch in async_client.iter_search_users("", batch_size=100):
       for user in batch:
           print(user.id, user.username)

``get_ticket_statistics``
^^^^^^^^^^^^^^^^^^^^^^^^^

Counts tickets created within an ISO date window and groups them by
entity, status, priority, and type. The ``start_date`` is inclusive
from 00:00:00 and the ``end_date`` is inclusive through 23:59:59, so
tickets created at any time on those days are counted. Optional
filters restrict the result set on the server side:

* ``entity_id`` — restrict to a single entity by numeric identifier.
* ``entity_name`` — substring match against the entity ``name`` column;
  the helper resolves matching IDs via ``search_entities`` and ORs
  them together. Ignored when ``entity_id`` is provided.
* ``extra_filter`` — raw RSQL fragment AND-joined with the date window.

.. code-block:: python

   # Tickets created in January 2026 on a specific entity, restricted to
   # priority "HIGH" (5) via an extra raw RSQL fragment.
   stats = client.get_ticket_statistics(
       start_date="2026-01-01",
       end_date="2026-01-31",
       entity_id=3,
       extra_filter="priority==5",
   )
   print(stats)

   # Resolve the entity by (partial) name instead of by ID:
   stats = client.get_ticket_statistics(
       start_date="2026-01-01",
       end_date="2026-01-31",
       entity_name="Helpdesk",
   )

When ``entity_name`` matches no entity the helper short-circuits and
returns ``{"entities": {}}`` without issuing any ticket search.

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
       t.id for t in client.search_tickets("status==2", limit=200)
   ]
   tasks = client.get_task_statistics(ticket_ids)
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
``client.get_user(22)`` to turn user key ``"22"`` into a full
:class:`GetUser` model).

``get_task_durations``
^^^^^^^^^^^^^^^^^^^^^^

Aggregates task durations over a date window with rich server-side
filters and an optional per-task detail list. Internally the helper
iterates :meth:`iter_search_tickets` to collect every matching ticket,
then computes per-user and per-entity totals.

Available filters:

* ``start_date`` / ``end_date`` / ``default_days`` — ISO ``YYYY-MM-DD``
  date window; ``start_date`` is inclusive from 00:00:00,
  ``end_date`` is inclusive through 23:59:59, and ``default_days``
  is used when ``start_date`` is omitted.
* ``entity_id`` — restrict to a single entity by identifier.
* ``entity_name`` — substring match resolved through ``search_entities``;
  ignored when ``entity_id`` is given.
* ``user_id`` — tickets where the user is **either** assignee or
  requester (OR semantics).
* ``user_editor_id`` — tickets last updated by this user.
* ``user_recipient_id`` — tickets where this user is the requester.
* ``extra_filter`` — raw RSQL fragment AND-joined with everything else.
* ``return_task_details`` — when ``True``, fetch every non-zero ticket's
  task list and include them as ``tasks`` in the result.

.. code-block:: python

   # Sum durations for a tech on a specific entity over the last 30 days.
   summary = client.get_task_durations(
       entity_id=3,
       user_id=42,
   )
   print(summary["total_duration"], summary["task_count"])
   print(summary["duration_by_entity"])  # {"3": 7200}

   # Same query but ask for the per-task breakdown.
   detailed = client.get_task_durations(
       entity_id=3,
       user_id=42,
       return_task_details=True,
   )
   for task in detailed["tasks"] or []:
       print(task["task_id"], task["ticket_id"], task["duration"])

Returned shape::

   {
       "start_date": "2026-01-01",
       "end_date": "2026-01-31",
       "total_duration": 7200,
       "task_count": 4,
       "duration_by_user": {"42": 7200},
       "duration_by_entity": {"3": 7200},
       "tasks": None,  # or a list[dict] when return_task_details=True
   }

On the async client the same method is overridden to run the per-ticket
task fetches concurrently with :func:`asyncio.gather` when
``return_task_details=True``.

``get_user_activity``
^^^^^^^^^^^^^^^^^^^^^

Aggregates per-user activity over a date window: tickets where the
user appears as technician (``users_id_assign``), tickets where the
user appears as requester (``users_id_requester``), and the user's
task duration totals. Multiple users that resolve to the same display
key (``"<firstname> <realname>"``) are merged into a single bucket.

The helper raises ``ValueError`` when no identifier is supplied or
when the search criteria match no users in the directory.

.. code-block:: python

   # Activity for a single user identified by username (substring match).
   report = client.get_user_activity(
       username="alice",
       start_date="2026-01-01",
       end_date="2026-01-31",
   )
   for display_name, data in report["users"].items():
       print(
           display_name,
           data["tickets_as_technician"],
           data["tickets_as_recipient"],
           data["task_durations"]["total_duration"],
       )

   # Activity for every user whose last name contains "Smith".
   report = client.get_user_activity(realname="Smith", default_days=90)

Returned shape::

   {
       "users": {
           "Alice Smith": {
               "user_ids": [42],
               "tickets_as_technician": 7,
               "tickets_as_recipient": 2,
               "task_durations": {
                   "start_date": "2026-01-01",
                   "end_date": "2026-01-31",
                   "total_duration": 7200,
                   "task_count": 4,
                   "duration_by_user": {"42": 7200},
                   "duration_by_entity": {"3": 7200},
               },
           }
       }
   }

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

   with GlpiClient.from_env() as client:
       new_id = client.create_ticket(
           PostTicket(
               name="Printer offline",
               content="The third-floor printer cannot be reached.",
           )
       )
       context = client.get_ticket_context(new_id)
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

   client.create_ticket_followup(
       ticket_id,
       PostFollowup(content="Capturing radius logs."),
   )
   context = client.get_ticket_context(ticket_id)
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

   client.create_ticket_task(
       ticket_id,
       PostTicketTask(
           content="On-site visit to swap the access point.",
           duration=1800,
       ),
   )
   context = client.get_ticket_context(ticket_id)
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

   client.create_ticket_solution(
       ticket_id,
       PostSolution(content="Replaced the access point firmware."),
   )
   context = client.get_ticket_context(ticket_id)
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

   client.upload_document(
       filename="diagnostic.txt",
       content=b"link layer ok\nradius timeout 3s\n",
       mime_type="text/plain",
       ticket_id=ticket_id,
   )
   context = client.get_ticket_context(ticket_id)
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

   from glpi_python_client import (
       GlpiClient,
       PostFollowup,
       PostSolution,
       PostTeamMember,
       PostTicket,
       PostTicketTask,
       PostUser,
   )


   def workflow() -> None:
       with GlpiClient.from_env() as client:
           user_id = client.create_user(
               PostUser(
                   username="bob.workflow",
                   password="initial-pwd",
                   password2="initial-pwd",
                   realname="Workflow",
                   firstname="Bob",
               )
           )
           new_ticket_id = client.create_ticket(
               PostTicket(name="VPN drops", content="Daily VPN drops at 11:00")
           )
           try:
               client.create_ticket_followup(
                   new_ticket_id,
                   PostFollowup(content="Reproduced on lab laptop"),
               )
               client.create_ticket_task(
                   new_ticket_id,
                   PostTicketTask(content="Capture VPN logs", duration=1800),
               )
               client.add_ticket_team_member(
                   new_ticket_id,
                   PostTeamMember(type="User", id=user_id, role="assigned"),
               )
               client.create_ticket_solution(
                   new_ticket_id,
                   PostSolution(content="Upgraded VPN client"),
               )
               context = client.get_ticket_context(new_ticket_id)
               print(context.ticket.name, len(context.followups))
           finally:
               client.delete_ticket(new_ticket_id, force=True)
               client.delete_user(user_id, force=True)


   workflow()

Example output::

   VPN drops 1

Example 7 — Build a monthly report
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Combines :meth:`get_ticket_statistics` and :meth:`get_task_statistics`
to summarise a calendar month.

.. code-block:: python

   from glpi_python_client import GlpiClient


   def monthly_report(start: str, end: str) -> dict[str, object]:
       with GlpiClient.from_env() as client:
           ticket_stats = client.get_ticket_statistics(
               start_date=start, end_date=end
           )
           solved_tickets = client.search_tickets(
               "status==5", limit=200
           )
           task_stats = client.get_task_statistics(
               [t.id for t in solved_tickets]
           )
           return {"tickets": ticket_stats, "tasks": task_stats}


   if __name__ == "__main__":
       print(monthly_report("2026-01-01", "2026-01-31"))

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

.. _error-handling:

7. Error handling
-----------------

Exceptions the client raises for a bad argument, an unexpected HTTP
status, or an unusable response body derive from
:class:`~glpi_python_client.GlpiError`, so one handler covers that part
of the library surface:

.. code-block:: python

   from glpi_python_client import GlpiClient, GlpiError

   client = GlpiClient.from_env()
   try:
       ticket = client.get_ticket(42)
   except GlpiError as exc:
       print(f"GLPI call failed: {exc}")

That single ``except`` clause covers network-level faults too.
Connection failures, DNS errors and timeouts are translated into
:class:`~glpi_python_client.GlpiTransportError` -- or its
:class:`~glpi_python_client.GlpiTimeoutError` subclass for a timeout --
so you never need to import the HTTP library to catch them. The original
transport exception stays attached as ``__cause__`` for debugging, and
these faults are retried three times before they surface:

.. code-block:: python

   from glpi_python_client import GlpiClient, GlpiTimeoutError, GlpiTransportError

   client = GlpiClient.from_env()
   try:
       ticket = client.get_ticket(42)
   except GlpiTimeoutError as exc:
       print(f"GLPI was too slow: {exc} (cause: {exc.__cause__!r})")
   except GlpiTransportError as exc:
       print(f"GLPI was unreachable: {exc}")

A handful of sites also deliberately still raise bare ``RuntimeError``
(using a closed client, a missing v1 document session, a partially
failed knowledge-base write) or ``TypeError`` (a malformed environment
value) instead of a library type, so ``except RuntimeError`` / ``except
TypeError`` code written against earlier releases keeps working.

The hierarchy lets you narrow as far as you need:

.. code-block:: text

   GlpiError
   ├── GlpiTransportError      reserved for the httpx transport swap;
   │   └── GlpiTimeoutError    not raised yet -- see the note above
   ├── GlpiStatusError         GLPI answered with an unexpected status
   │   ├── GlpiAuthError       401 / 403
   │   ├── GlpiNotFoundError   404
   │   └── GlpiServerError     5xx (retried up to 3 attempts before it
   │                           reaches you)
   ├── GlpiValidationError     the client rejected your argument
   └── GlpiProtocolError       GLPI answered 2xx with an unusable body

:class:`~glpi_python_client.GlpiStatusError` carries the diagnostics you
usually want:

.. code-block:: python

   from glpi_python_client import GlpiNotFoundError

   try:
       ticket = client.get_ticket(999999)
   except GlpiNotFoundError as exc:
       print(exc.status_code)    # 404
       print(exc.url)            # the absolute URL that was requested
       print(exc.response_text)  # the response body

.. note::

   :class:`~glpi_python_client.GlpiStatusError`,
   :class:`~glpi_python_client.GlpiValidationError` and
   :class:`~glpi_python_client.GlpiProtocolError` also inherit
   :class:`ValueError`. Code written against earlier releases, which
   raised bare ``ValueError``, keeps working unchanged.

Retry behaviour
~~~~~~~~~~~~~~~

Each transport and v1-session retry decorator retries a server error
(5xx) up to 3 attempts with a 3-second fixed wait before
:class:`~glpi_python_client.GlpiServerError` reaches you. Client errors
(4xx) are never retried — they cannot succeed on a second attempt.

OAuth token acquisition follows the same 3-attempt policy, with one
exception: refreshing an already-issued token does not raise directly on
a failed response. It logs a warning and falls through to a fresh token
acquisition, which carries its own independent 3-attempt retry
decorator. The refresh method's own retry decorator only retries a
network-level fault on the refresh request itself (a
:class:`~glpi_python_client.GlpiTransportError` raised before any
response is received) —
it does **not** retry a :class:`~glpi_python_client.GlpiServerError`
from the fall-through, since that failure is already being retried by
the nested acquisition call. A persistent 5xx encountered while
refreshing therefore costs exactly 1 refresh POST + up to 3 nested
acquisition POSTs = 4 POST requests before
:class:`~glpi_python_client.GlpiServerError` reaches you. A rejected
credential (401/403) is not retried at either layer and fails after at
most 2 POST requests.

Search methods are deliberately tolerant: ``search_tickets`` and its
siblings return an empty list rather than raising when GLPI rejects the
query. Methods that fetch or mutate one specific record always raise.