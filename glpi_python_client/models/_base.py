"""Base model contracts for GLPI data objects.

This module defines the common Pydantic base class used by the package's typed
GLPI models.

Notes
-----
The base relaxes Pydantic's ``extra="forbid"`` policy because the live GLPI
v2 server consistently returns helper fields (``href``, ``display_name``,
``firstname``, ``realname``, ``completename``, ...) that are absent from the
OpenAPI contract. Per the project rule that real behaviour wins over the
contract, undeclared fields are accepted and funnelled into the existing
``extra_payload`` escape hatch instead of raising. ``extra_payload`` keys
provided explicitly by callers still take precedence on serialisation.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import (
    AliasChoices,
    AliasPath,
    BaseModel,
    ConfigDict,
    Field,
    SerializationInfo,
    SerializerFunctionWrapHandler,
    ValidationInfo,
    model_serializer,
    model_validator,
)

#: Validation-context key carrying the GLPI server's timezone.
#:
#: Set by ``model_from_payload`` in the client's ``commons._payloads``
#: module from the client's ``server_timezone``. Absent when a model is built
#: outside the client, which is deliberate -- see
#: :meth:`GlpiModel._localise_naive_datetimes`.
SERVER_TIMEZONE_CONTEXT_KEY = "server_timezone"

#: Per-class cache of the payload keys that map onto a declared field.
#:
#: One entry per :class:`GlpiModel` subclass ever validated, computed once.
#: Worth caching rather than recomputing: it is read once per record, so on
#: a page of search results it is read once per row per model.
_PAYLOAD_KEYS: dict[type[BaseModel], frozenset[str]] = {}


def _payload_keys(model_class: type[BaseModel]) -> frozenset[str]:
    """Return every payload key that maps onto a declared field.

    Field *names* are not the whole answer, because a field may be fed by a
    validation alias instead -- the read models take the wire's ``content``
    into a field called ``content_html``. Comparing incoming keys against
    names alone put that ``content`` in ``extra_payload`` before Pydantic
    could resolve the alias, so the body silently arrived as ``None``.

    All three alias shapes are covered. ``alias=`` and ``validation_alias=``
    are both valid spellings of the same thing, an
    :class:`~pydantic.AliasChoices` holds a list of either strings or
    :class:`~pydantic.AliasPath` objects, and only the *first* segment of an
    ``AliasPath`` is a key of the incoming mapping -- the rest index into
    the value.

    Parameters
    ----------
    model_class : type of pydantic.BaseModel
        The concrete model class whose payload keys are wanted.

    Returns
    -------
    frozenset of str
        Field names plus every key any of their aliases can consume.
    """

    cached = _PAYLOAD_KEYS.get(model_class)
    if cached is not None:
        return cached

    keys = set(model_class.model_fields)
    pending: list[str | AliasPath | AliasChoices] = []
    for field in model_class.model_fields.values():
        if field.validation_alias is not None:
            pending.append(field.validation_alias)
        if field.alias is not None:
            pending.append(field.alias)
    while pending:
        candidate = pending.pop()
        if isinstance(candidate, str):
            keys.add(candidate)
        elif isinstance(candidate, AliasChoices):
            pending.extend(candidate.choices)
        else:
            head = candidate.path[0]
            if isinstance(head, str):
                keys.add(head)

    resolved = frozenset(keys)
    _PAYLOAD_KEYS[model_class] = resolved
    return resolved


#: Cache for :func:`_alias_groups`, keyed the same way as
#: :data:`_PAYLOAD_KEYS`.
_ALIAS_GROUPS: dict[type[BaseModel], tuple[tuple[str, ...], ...]] = {}


def _alias_groups(model_class: type[BaseModel]) -> tuple[tuple[str, ...], ...]:
    """Return the payload keys of every field that accepts more than one.

    Each group is one field's accepted spellings **in the order Pydantic
    tries them**, which for ``AliasChoices`` is the order they were
    declared. Fields accepting a single key are left out, since there is
    nothing to choose between.

    Only plain string choices are listed. An ``AliasPath`` addresses a
    position inside a nested structure rather than a key that could
    duplicate another, so it is not a member of any group.

    Parameters
    ----------
    model_class : type[BaseModel]
        The concrete model being validated.

    Returns
    -------
    tuple of tuple of str
        One tuple per multi-spelling field, most-preferred spelling first.
    """

    cached = _ALIAS_GROUPS.get(model_class)
    if cached is not None:
        return cached
    groups: list[tuple[str, ...]] = []
    for field in model_class.model_fields.values():
        keys: list[str] = []
        alias = field.validation_alias
        if isinstance(alias, AliasChoices):
            keys.extend(choice for choice in alias.choices if isinstance(choice, str))
        elif isinstance(alias, str):
            keys.append(alias)
        if field.alias is not None and field.alias not in keys:
            keys.append(field.alias)
        if len(keys) > 1:
            groups.append(tuple(keys))
    resolved = tuple(groups)
    _ALIAS_GROUPS[model_class] = resolved
    return resolved


class GlpiModel(BaseModel):
    """Base class for field-validated GLPI data models.

    The shared base model accepts undeclared fields and routes them into
    the explicit ``extra_payload`` mapping, so instance-specific API
    extensions can still be inspected or forwarded intentionally.
    """

    model_config = ConfigDict(extra="allow")
    extra_payload: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _capture_unknown_fields(cls, data: Any) -> Any:
        """Funnel unknown payload keys into ``extra_payload``.

        The validator only runs when ``data`` is a mapping. Keys that no
        declared field on the concrete subclass can consume (and that are
        not the ``extra_payload`` meta field itself) are removed from the
        incoming mapping and merged into the ``extra_payload`` mapping. Any
        keys the caller already placed in ``extra_payload`` win on
        conflicts.

        "Can consume" means field names *and* validation aliases -- see
        :func:`_payload_keys`. This validator runs before Pydantic resolves
        aliases, so a key it removes is a key the alias never gets to see.

        A payload that spells one field two ways keeps only the spelling
        Pydantic would have used, per :func:`_alias_groups`. The redundant
        one is dropped rather than kept, because keeping it was worse than
        it sounds: Pydantic consumes the winning alias, and ``extra="allow"``
        then files the loser as a model extra, which ``model_dump`` emits
        *over* the field it duplicates. Measured on ``GetTicket`` given both
        ``content`` and ``content_html``, the attribute reported one body
        and the object's own dump reported the other.
        """

        if not isinstance(data, dict):
            return data
        known = _payload_keys(cls)
        for group in _alias_groups(cls):
            present = [key for key in group if key in data]
            for redundant in present[1:]:
                del data[redundant]
        existing_extras = data.get("extra_payload")
        captured: dict[str, Any] = {}
        for key in list(data.keys()):
            if key in known:
                continue
            captured[key] = data.pop(key)
        if captured:
            merged = dict(captured)
            if isinstance(existing_extras, dict):
                merged.update(existing_extras)
            data["extra_payload"] = merged
        return data

    @model_validator(mode="after")
    def _localise_naive_datetimes(self, info: ValidationInfo) -> GlpiModel:
        """Stamp the server's timezone onto timestamps that arrived without one.

        GLPI 11 sends most timestamps with the correct historical offset --
        measured on a live instance, 19 of the 20 datetime fields across
        every resource, and the same article carries ``+02:00`` in summer
        and ``+01:00`` in winter. ``KBArticle.revisions[].date`` is the
        exception and arrives bare, so one response can hold both kinds and
        comparing them raises ``TypeError``. This closes that gap.

        Two rules make it safe:

        * **An offset already on the wire wins.** GLPI's own offset follows
          DST; a single configured zone does not, so overwriting would
          corrupt half the year.
        * **No context means no guess.** A model built outside the client
          keeps its naive values. Stamping an arbitrary offset on an unknown
          timestamp would convert a loud ``TypeError`` into a quietly wrong
          answer, which is strictly worse.

        The stamped values are written onto a copy rather than assigned in
        place, because a ``mode="after"`` validator receives the instance
        itself -- and ``model_validate`` accepts an existing model, so
        mutating would reach back into an object the caller still holds.
        """

        context = info.context
        if not isinstance(context, dict):
            return self
        tzinfo = context.get(SERVER_TIMEZONE_CONTEXT_KEY)
        if tzinfo is None:
            return self

        localised = {
            name: value.replace(tzinfo=tzinfo)
            for name in type(self).model_fields
            if isinstance(value := getattr(self, name, None), datetime)
            and value.tzinfo is None
        }
        if not localised:
            return self
        return self.model_copy(update=localised)

    @model_serializer(mode="wrap")
    def _render_datetimes_on_the_server_clock(
        self,
        handler: SerializerFunctionWrapHandler,
        info: SerializationInfo,
    ) -> Any:
        """Convert aware datetimes to server-local time and drop the offset.

        GLPI 11 does not read the offset it sends. Measured on a live
        Europe/Paris instance, ``12:30:00`` written bare, as ``...Z``, and
        with ``+02:00``, ``+09:00``, ``-08:00`` and ``+14:00`` all store the
        same moment -- 12:30 Paris. The server takes the naive prefix,
        interprets it in its own timezone, and discards the rest. It is not
        ignoring the offset unparsed either: ``+99:99`` answers HTTP 500. So
        the value is read and then thrown away, and ``12:30-08:00`` -- 21:30
        in Paris -- lands nine hours early with a 200 and nothing to read
        back that looks wrong.

        An offset is therefore not something to preserve on the way out. The
        only spelling GLPI cannot misread is one whose naive prefix is
        already server-local, so the offset is spent converting the value
        and then removed.

        The two rules mirror the inbound half:

        * **Naive values are left alone.** A naive datetime already means
          "the server's clock" -- converting it would require guessing which
          zone the caller meant.
        * **No context means no conversion.** A model dumped outside the
          client has no server to be local to.

        Converted values go onto a copy for the same reason the inbound
        validator copies: the caller still holds the model being dumped, and
        serialising is not allowed to change it.
        """

        context = info.context
        if not isinstance(context, dict):
            return handler(self)
        tzinfo = context.get(SERVER_TIMEZONE_CONTEXT_KEY)
        if tzinfo is None:
            return handler(self)

        server_local = {
            name: value.astimezone(tzinfo).replace(tzinfo=None)
            for name in type(self).model_fields
            if isinstance(value := getattr(self, name, None), datetime)
            and value.tzinfo is not None
        }
        if not server_local:
            return handler(self)
        return handler(self.model_copy(update=server_local))
