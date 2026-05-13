User Guide
==========

.. _create-a-client:

Create a Client
---------------

The main synchronous entry point is :class:`glpi_python_client.GlpiClient`.
Async applications can use :class:`glpi_python_client.AsyncGlpiClient` with the
same constructor options. Use clients as context managers when possible so
cached OAuth tokens are cleared and HTTP sessions are released automatically.

Provide the GLPI API URL and at least one complete auth pair directly when
creating the client.

Required constructor argument:

* ``glpi_api_url``: high-level GLPI API URL, usually ending in ``/api.php``.

The correct auth combination is dependent on your GLPI instance configuration. We support:

* ``client_id`` and ``client_secret``
* ``username`` and ``password``
* both pairs together

The example below uses both pairs because that is the most explicit setup for a
user-scoped confidential OAuth client.

Optional constructor arguments used in the examples below:

* ``glpi_entity``: numeric GLPI entity ID sent as the ``GLPI-Entity`` header.
    Omit it when the API user should keep its server-side default entity.
* ``glpi_profile``: numeric GLPI profile ID sent as the ``GLPI-Profile``
    header. Omit it when the API user already starts in the correct profile.
* ``auth_token_refresh``: optional number of seconds between proactive OAuth
    token refreshes. Use ``None`` to disable interval-based refresh.

.. code-block:: python

   from glpi_python_client import GlpiClient

   with GlpiClient(
       glpi_api_url="https://glpi.example.com/api.php",
       client_id="oauth-client-id",
       client_secret="oauth-client-secret",
       username="api-user",
       password="api-password",
       glpi_entity=1,
       glpi_profile=4,
   ) as glpi:
       tickets = glpi.search_ticket_records()

``search_ticket_records()`` returns a full list by default. Pass
``batch_size`` to iterate over batches instead when you want to stream a larger
result set.

Deleted tickets are excluded by default from ``search_ticket_records()`` and
``get_ticket_record()``. Pass ``include_deleted_ticket=True`` when you need GLPI
tickets marked as deleted.

::

   for batch in glpi.search_ticket_records(batch_size=200):
       for ticket in batch:
           print(ticket.id)

.. code-block:: python

   from glpi_python_client import AsyncGlpiClient

   async with AsyncGlpiClient(
       glpi_api_url="https://glpi.example.com/api.php",
       client_id="oauth-client-id",
       client_secret="oauth-client-secret",
       username="api-user",
       password="api-password",
       auth_token_refresh=900,
   ) as glpi:
       tickets = await glpi.search_ticket_records()

The async client currently wraps the shared ``requests`` transport so
applications can await client methods without changing the sync transport
behavior.

Field-Validated Models and Content Formatting
---------------------------------------------

Public GLPI records are represented by field-validated Pydantic models such as
:class:`glpi_python_client.GlpiTicket`, :class:`glpi_python_client.GlpiFollowup`,
:class:`glpi_python_client.GlpiSolution`, :class:`glpi_python_client.GlpiTask`,
:class:`glpi_python_client.GlpiDocument`, :class:`glpi_python_client.GlpiUser`, and
:class:`glpi_python_client.GlpiLocation`. Use those models when creating, updating, or
working with fetched GLPI data instead of building raw dictionaries in
application code.

Textual ticket content is canonical Markdown in Python. When the client fetches
GLPI ticket descriptions, followups, tasks, or solutions, GLPI HTML is converted
to Markdown before it is placed on the model. When the client sends those same
fields back to GLPI, Markdown is rendered to HTML for the API payload.

.. code-block:: python

   ticket = GlpiTicket(
       name="Laptop cannot join corporate Wi-Fi",
       content=(
           "User sees **certificate rejected** during 802.1X authentication.\n"
           "- Device: Latitude 7450\n"
           "- Location: Paris office"
       ),
   )

   ticket_id = glpi.create_ticket(ticket)
   fetched_ticket = glpi.get_ticket_record(ticket_id)
   print(fetched_ticket.content)  # Markdown, even though GLPI stores HTML.

Create operations return the created GLPI identifier. Update, add, remove, and
other mutation-only operations return ``None`` and raise on error.

The client only forwards fields that you set explicitly on the model. It does
not inject package-owned defaults for ticket status, priority, type, or
category. If your GLPI workflow requires any of those values, set them on
:class:`glpi_python_client.GlpiTicket` before calling ``create_ticket()`` or
``update_ticket()``.
``create_ticket()`` requires a non-empty ticket ``name``.

``GlpiTicket`` uses GLPI ticket field names directly, including ``id``,
``status``, ``type``, ``category``, ``location``, ``date_creation``,
``date_mod``, ``date_close``, ``user_recipient``, ``user_editor``, and
``team``.

Binary document content is the exception: :class:`glpi_python_client.GlpiDocument.content`
remains ``bytes`` so uploads and downloads preserve the original file content.
Public client methods accept GLPI identifiers as either ``str`` or ``int`` and
normalize them into request paths as needed.

Custom Payload Keys for a GLPI Instance
---------------------------------------

Many GLPI deployments add plugin fields, custom dropdowns, or instance-specific
payload keys. Use the public ``extra_payload`` field on the model you send
through the client when you need to include those raw GLPI keys.

The example below sends two instance-specific ticket fields without relying on
private modules or overriding protected methods.

.. code-block:: python

   from glpi_python_client import GlpiTicket
   custom_ticket = GlpiTicket(
       name="Access badge reader offline",
       content="Reader in **Paris / 3rd floor** is unreachable.",
       extra_payload={
           "_room_code": "PAR-3F-12",
           "_asset_tag": "BADGE-READER-044",
       },
   )
   glpi.create_ticket(custom_ticket)

Replace ``_room_code`` and ``_asset_tag`` with the field names expected by your
GLPI instance or plugin. The same ``extra_payload`` pattern works with the
other public payload-backed models.

Utility Constructor
-------------------

If an application already stores the same configuration in environment
variables, :meth:`glpi_python_client.GlpiClient.from_env` can assemble the client for you.
The default prefix is ``GLPI_``.

Required variables:

* ``GLPI_API_URL``
* At least one complete auth pair:
    ``GLPI_CLIENT_ID`` and ``GLPI_CLIENT_SECRET``,
    ``GLPI_USERNAME`` and ``GLPI_PASSWORD``, or both pairs.

Optional variables:

* ``GLPI_ENTITY``
* ``GLPI_PROFILE``
* ``GLPI_ENTITY_RECURSIVE``
* ``GLPI_LANGUAGE``
* ``GLPI_VERIFY_SSL``
* ``GLPI_AUTH_TOKEN_REFRESH``
* ``GLPI_V1_BASE_URL``
* ``GLPI_V1_USER_TOKEN``
* ``GLPI_V1_APP_TOKEN``

``GLPI_V1_BASE_URL`` and ``GLPI_V1_USER_TOKEN`` must be supplied together when
legacy v1 document upload support is needed. ``GLPI_V1_APP_TOKEN`` remains
optional for instances that do not require an app token. Set
``GLPI_V1_BASE_URL`` explicitly to the v1 endpoint your instance exposes, such
as ``/api.php/v1`` or ``/apirest.php``.

.. code-block:: python

   from glpi_python_client import GlpiClient

   client = GlpiClient.from_env()

End-to-End Incident Workflow
----------------------------

This workflow covers a common help-desk path: make sure the requester exists,
create the ticket, capture internal triage, attach diagnostic evidence, and
mark the incident as solved once the fix is confirmed.

Some GLPI instances still require legacy v1 credentials for document upload, so
the client below is constructed with both the high-level API URL and the v1
document-upload settings.

In this example:

* ``HELPDESK_ENTITY_ID`` is optional and only needed when requests must be
    routed to one explicit GLPI entity.
* ``TECHNICIAN_PROFILE_ID`` is optional and only needed when the API user must
    switch to a specific GLPI profile.
* ``V1_DOCUMENT_BASE_URL``, ``V1_DOCUMENT_USER_TOKEN``, and
    ``V1_DOCUMENT_APP_TOKEN`` are only required when your GLPI instance uses a
    separate v1 document-upload endpoint.

.. code-block:: python

   from glpi_python_client import (
       GlpiClient,
       GlpiDocument,
       GlpiFollowup,
       GlpiLocation,
       GlpiSolution,
       GlpiTicket,
       GlpiUser,
   )

   HELPDESK_ENTITY_ID = 1
   TECHNICIAN_PROFILE_ID = 4
    V1_DOCUMENT_BASE_URL = "https://glpi.example.com/api.php/v1"
    V1_DOCUMENT_USER_TOKEN = "v1-user-token"
    V1_DOCUMENT_APP_TOKEN = "v1-app-token"
   SOLVED_STATUS_ID = 5  # Replace with the status used by your GLPI workflow.

   with GlpiClient(
       glpi_api_url="https://glpi.example.com/api.php",
       client_id="oauth-client-id",
       client_secret="oauth-client-secret",
       username="api-user",
       password="api-password",
       glpi_entity=HELPDESK_ENTITY_ID,
       glpi_profile=TECHNICIAN_PROFILE_ID,
    v1_base_url=V1_DOCUMENT_BASE_URL,
    v1_user_token=V1_DOCUMENT_USER_TOKEN,
    v1_app_token=V1_DOCUMENT_APP_TOKEN,
   ) as glpi:
       requester_email = "jane.doe@example.com"
       requester_firstname = "Jane"
       requester_realname = "Doe"

       matching_users = glpi.search_users(
           f'email=="{requester_email}"',
           limit=1,
       )
       requester = matching_users[0] if matching_users else None
       requester_id = (
           requester.user_id
           if requester is not None and requester.user_id is not None
           else glpi.create_user(
               GlpiUser(
                   email=requester_email,
                   firstname=requester_firstname,
                   realname=requester_realname,
               )
           )
       )

       matching_locations = glpi.search_locations("Paris office")
       location = matching_locations[0] if matching_locations else None
       location_id = (
           location.location_id
           if location is not None and location.location_id is not None
           else glpi.create_location(GlpiLocation(name="Paris office"))
       )

       ticket_id = glpi.create_ticket(
           GlpiTicket(
               name="Laptop cannot join corporate Wi-Fi",
               content=(
                   f"Requester: {requester_firstname} {requester_realname} "
                   f"<{requester_email}>\n"
                   f"Requester ID: {requester_id}\n"
                   "Device: Latitude 7450\n"
                   "Symptom: certificate warning during 802.1X authentication."
               ),
               urgency=3,
               impact=3,
               location=location_id,
           )
       )

       glpi.create_followup(
           ticket_id,
           GlpiFollowup(
               content="Collected logs and started first-line network checks.",
               is_private=True,
           ),
       )

       diagnostic_document = glpi.upload_document_to_ticket(
           GlpiDocument(
               ticket_id=ticket_id,
               filename="wifi-diagnostics.txt",
               content=(
                   b"Adapter: Intel AX211\n"
                   b"Signal: -48 dBm\n"
                   b"Error: EAP certificate rejected"
               ),
               mime_type="text/plain",
           )
       )

       if diagnostic_document.document_id is not None:
           glpi.create_followup(
               ticket_id,
               GlpiFollowup(
                   content=(
                       "Attached the diagnostic capture as document "
                       f"{diagnostic_document.document_id}."
                   )
               ),
           )

       glpi.create_solution(
           ticket_id,
           GlpiSolution(
               content=(
                   "Reissued the workstation certificate and re-enrolled the "
                   "Wi-Fi profile."
               )
           ),
       )

       glpi.update_ticket(
           ticket_id,
           GlpiTicket(status=SOLVED_STATUS_ID),
           field_mask=("status",),
       )

       final_ticket = glpi.get_ticket_record(ticket_id)
       ticket_documents = glpi.get_document_records(ticket_id)

The same workflow works for hardware issues, onboarding requests, or site
service interruptions. The key pattern is to build the ticket payload from
business data your application already owns, then use followups, solutions, and
documents to preserve the operational history in GLPI.

Queue Review and Escalation
---------------------------

Another common workflow is a triage pass over the active queue: search the open
tickets, load their surrounding context, and post a focused followup when the
attachment content confirms a likely root cause.

``HELPDESK_ENTITY_ID`` and ``TECHNICIAN_PROFILE_ID`` are the same optional
 routing values described in :ref:`Create a Client <create-a-client>`: set them
 only when your API user must override its default entity or profile.

.. code-block:: python

   from glpi_python_client import GlpiClient, GlpiFollowup

   HELPDESK_ENTITY_ID = 1
   TECHNICIAN_PROFILE_ID = 4

   with GlpiClient(
       glpi_api_url="https://glpi.example.com/api.php",
       client_id="oauth-client-id",
       client_secret="oauth-client-secret",
       username="api-user",
       password="api-password",
       glpi_entity=HELPDESK_ENTITY_ID,
       glpi_profile=TECHNICIAN_PROFILE_ID,
   ) as glpi:
       queue = glpi.search_ticket_records(
           query='status.id=in=(1,2)',
           fields=("location", "priority", "request_type"),
           sort="date_mod:desc",
       )

       for ticket in queue:
           if ticket.id is None:
               continue

           details = glpi.get_ticket_record(ticket.id)
           followups = glpi.get_followup_records(ticket.id)
           tasks = glpi.get_task_records(ticket.id)
           documents = glpi.get_document_records(ticket.id)

           latest_document = next(
               (
                   document
                   for document in documents
                   if document.document_id is not None
               ),
               None,
           )
           if latest_document is None:
               continue

           content = glpi.download_document_content(latest_document.document_id)
           latest_note = followups[-1].content.casefold() if followups else ""

           if (
               details.priority is not None
               and details.priority >= 4
               and not tasks
               and b"certificate" in content.lower()
               and "certificate" not in latest_note
           ):
               glpi.create_followup(
                   ticket.id,
                   GlpiFollowup(
                       content=(
                           "Attachment analysis points to an expired or missing "
                           "certificate. Please route to the endpoint management "
                           "team if re-enrolment is required."
                       ),
                       is_private=True,
                   ),
               )

This pattern keeps the queue logic in your application while using GLPI as the
system of record for triage notes, ticket state, and supporting evidence.

Error Handling
--------------

Client methods raise :class:`ValueError` when GLPI returns an unsuccessful
response that cannot be represented as a normal return value. Server-side
transport failures are retried with ``tenacity`` before surfacing to callers.
