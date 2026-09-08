API Reference
=============

This reference documents the public package surface exported by
``glpi_python_client``. Internal implementation modules and
underscore-prefixed helpers are intentionally omitted.

.. currentmodule:: glpi_python_client

Clients
-------

The package exposes two clients with identical endpoint surfaces. The
asynchronous one is hand-written and the synchronous one is generated
from it, so neither wraps the other and the two cannot drift apart.

.. autoclass:: GlpiClient
   :members:
   :inherited-members:
   :show-inheritance:

.. autoclass:: AsyncGlpiClient
   :members:
   :inherited-members:
   :show-inheritance:

Exceptions
----------

Exceptions raised for a bad argument, an unexpected HTTP status, an
unusable response body, or content that cannot be converted derive from
:class:`GlpiError`. :class:`GlpiStatusError`, :class:`GlpiValidationError`
and :class:`GlpiProtocolError` also inherit :class:`ValueError` for
backwards compatibility with releases that raised bare ``ValueError``;
:class:`GlpiContentError` and :class:`GlpiTransportError` do not, because
nothing was passed in wrongly in either case.

Network-level faults (connection failures, DNS errors, timeouts) are
raised as :class:`GlpiTransportError`, or its :class:`GlpiTimeoutError`
subclass for a timeout, with the underlying transport exception attached
as ``__cause__``. Catching :class:`GlpiError` is therefore sufficient for
the library's failure surface -- you never need to import the HTTP
library. A handful of sites do still deliberately raise bare
``RuntimeError`` or ``TypeError`` instead
of a library type, so existing ``except RuntimeError`` / ``except
TypeError`` code keeps working. See :ref:`error-handling` in the user
guide for the full picture, including which methods raise which type.

.. autoexception:: GlpiError
   :members:
   :show-inheritance:

.. autoexception:: GlpiTransportError
   :members:
   :show-inheritance:

.. autoexception:: GlpiTimeoutError
   :members:
   :show-inheritance:

.. autoexception:: GlpiStatusError
   :members:
   :show-inheritance:

.. autoexception:: GlpiAuthError
   :members:
   :show-inheritance:

.. autoexception:: GlpiNotFoundError
   :members:
   :show-inheritance:

.. autoexception:: GlpiServerError
   :members:
   :show-inheritance:

.. autoexception:: GlpiValidationError
   :members:
   :show-inheritance:

.. autoexception:: GlpiProtocolError
   :members:
   :show-inheritance:

.. autoexception:: GlpiContentError
   :members:
   :show-inheritance:

Rich-text content
-----------------

GLPI exchanges ticket, followup, task, solution and knowledge-base bodies
as HTML. The package's surface is Markdown in both directions, but the two
directions work differently, and the difference is visible.

A **write** model (``Post*``, ``Patch*``) takes Markdown in ``content`` and
renders it to HTML when the request is built. Nothing to think about.

A **read** model (``Get*``) keeps two views of the same body:

``content_html``
   what GLPI sent, verbatim. Also accepts the wire spelling ``content`` on
   construction.

``content``
   the same body as Markdown, converted on the first read and cached.
   :class:`GetKBArticle` has ``description`` / ``description_html`` as
   well.

Reading ``.content`` is what a caller wants and what earlier releases
returned, so no read-side code needs changing. What changed is *when* the
conversion happens, which buys two things: listing records costs nothing
per body, and a body that cannot be converted no longer stops the rest of
its page being read.

Very deeply nested HTML is the case worth knowing about.
``markdownify`` walks the document recursively and runs out of stack at
around 494 levels of nesting, so past
:data:`glpi_python_client.content.conversion.MAX_HTML_DEPTH` (200) the
converter strips tags instead of parsing. It degrades, it never
truncates, and it does not raise: every character the normal rendering
would have produced still appears. What is lost is structure rather than
words — link targets and image alt text, code fencing and ``<pre>``
indentation, ``&nbsp;`` alignment. Anything else that goes wrong in
either direction raises :class:`GlpiContentError`.

Because the conversion is cached on first read, a read model should be
treated as immutable afterwards: assigning to ``content_html``, or
``model_copy(update={"content_html": ...})``, leaves the cached Markdown
in place. Rebuild through ``model_validate`` if you need to change it.

Aggregated Models
-----------------

.. autoclass:: GlpiTicketContext
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: TicketMarkdownOptions
   :members:
   :undoc-members:
   :show-inheritance:

Common Reference Models
-----------------------

.. autoclass:: IdRef
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: IdNameRef
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: IdNameCompletenameRef
   :members:
   :undoc-members:
   :show-inheritance:

Tickets
-------

.. autoclass:: GetTicket
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: PostTicket
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: PatchTicket
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: DeleteTicket
   :members:
   :undoc-members:
   :show-inheritance:

Ticket Timeline — Followups
---------------------------

.. autoclass:: GetFollowup
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: PostFollowup
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: PatchFollowup
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: DeleteFollowup
   :members:
   :undoc-members:
   :show-inheritance:

Ticket Timeline — Tasks
-----------------------

.. autoclass:: GetTicketTask
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: PostTicketTask
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: PatchTicketTask
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: DeleteTicketTask
   :members:
   :undoc-members:
   :show-inheritance:

Ticket Timeline — Solutions
---------------------------

.. autoclass:: GetSolution
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: PostSolution
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: PatchSolution
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: DeleteSolution
   :members:
   :undoc-members:
   :show-inheritance:

Ticket Timeline — Documents
---------------------------

.. autoclass:: GetTimelineDocument
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: PostTimelineDocument
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: PatchTimelineDocument
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: DeleteTimelineDocument
   :members:
   :undoc-members:
   :show-inheritance:

Ticket Team Members
-------------------

.. autoclass:: GetTeamMember
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: PostTeamMember
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: PatchTeamMember
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: DeleteTeamMember
   :members:
   :undoc-members:
   :show-inheritance:

Documents
---------

.. autoclass:: GetDocument
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: PostDocument
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: PatchDocument
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: DeleteDocument
   :members:
   :undoc-members:
   :show-inheritance:

Users
-----

.. autoclass:: GetUser
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: PostUser
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: PatchUser
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: DeleteUser
   :members:
   :undoc-members:
   :show-inheritance:

Locations
---------

.. autoclass:: GetLocation
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: PostLocation
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: PatchLocation
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: DeleteLocation
   :members:
   :undoc-members:
   :show-inheritance:

Knowledge Base — Articles
-------------------------

.. autoclass:: GetKBArticle
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: PostKBArticle
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: PatchKBArticle
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: DeleteKBArticle
   :members:
   :undoc-members:
   :show-inheritance:

Knowledge Base — Article Comments
---------------------------------

.. autoclass:: GetKBArticleComment
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: PostKBArticleComment
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: PatchKBArticleComment
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: DeleteKBArticleComment
   :members:
   :undoc-members:
   :show-inheritance:

Knowledge Base — Article Revisions
----------------------------------

.. autoclass:: GetKBArticleRevision
   :members:
   :undoc-members:
   :show-inheritance:

Knowledge Base — Categories
---------------------------

.. autoclass:: GetKBCategory
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: PostKBCategory
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: PatchKBCategory
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: DeleteKBCategory
   :members:
   :undoc-members:
   :show-inheritance:

Entities
--------

.. autoclass:: GetEntity
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: PostEntity
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: PatchEntity
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: DeleteEntity
   :members:
   :undoc-members:
   :show-inheritance:

Plugin: Fields (custom fields)
------------------------------

Schemas returned by the GLPI ``Fields`` plugin (legacy v1 REST endpoints).
The companion mixin methods are exposed on :class:`GlpiClient` /
:class:`AsyncGlpiClient` as ``list_plugin_fields_containers``,
``list_plugin_fields_fields``, ``list_item_plugin_field_rows``,
``create_item_plugin_field_row``, ``update_item_plugin_field_row``,
``get_ticket_custom_fields`` and ``set_ticket_custom_fields``.

.. autoclass:: GetPluginFieldsContainer
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: GetPluginFieldsField
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: GetPluginFieldsValueRow
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: PostPluginFieldsValueRow
   :members:
   :undoc-members:
   :show-inheritance:

Enums
-----

.. autoclass:: GlpiEnum
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: GlpiTicketStatus
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: GlpiTicketType
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: GlpiPriority
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: GlpiTaskState
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: GlpiSolutionStatus
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: GlpiTimelinePosition
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: GlpiUserAuthType
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: GlpiGlobalValidation
   :members:
   :undoc-members:
   :show-inheritance:

Package Metadata
----------------

.. autodata:: __version__
