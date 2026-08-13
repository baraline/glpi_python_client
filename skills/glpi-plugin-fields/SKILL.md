---
name: glpi-plugin-fields
description: "Discover and read/write GLPI Fields-plugin custom fields with the synchronous glpi_python_client.GlpiClient or the asynchronous AsyncGlpiClient — list_plugin_fields_containers, list_plugin_fields_fields, list_item_plugin_field_rows, create_item_plugin_field_row, update_item_plugin_field_row, and the Ticket-only get_ticket_custom_fields/set_ticket_custom_fields. Use for GLPI custom fields, the Fields plugin, per-instance extra ticket attributes, or reading a ticket's custom-field values."
license: MIT
compatibility: "Requires Python 3.10+, glpi-python-client, the GLPI Fields plugin installed server-side, and a legacy v1 session (v1_base_url + v1_user_token) — every method in this family goes over the v1 API."
metadata:
  package: glpi-python-client
  version: "0.4.3"
---

# GLPI Plugin Fields
> The snippets below use `AsyncGlpiClient` (`async with` + `await`). Every method shown also exists on the synchronous `GlpiClient` with the same signature -- replace `async with` with `with`, drop the `await` keyword, and skip the surrounding `async def`/`asyncio.run` scaffolding.

The GLPI `Fields` plugin adds user-defined custom fields to any itemtype: a *container* is a block of fields attached to one or more itemtypes, and each container stores one value row per item. None of it exists in the GLPI v2 contract, so all seven methods -- `list_plugin_fields_containers`, `list_plugin_fields_fields`, `list_item_plugin_field_rows`, `create_item_plugin_field_row`, `update_item_plugin_field_row`, and the Ticket-only `get_ticket_custom_fields`/`set_ticket_custom_fields` -- talk to the legacy v1 REST API. They are present on both `GlpiClient` and `AsyncGlpiClient` with identical signatures.

Two constraints decide whether any of it works, so settle them first:

- **Every one of the seven methods needs the legacy v1 session.** Build the client with `v1_base_url` *and* `v1_user_token` (or `GLPI_V1_BASE_URL`/`GLPI_V1_USER_TOKEN` for `from_env`). Without them the call raises a plain builtin `RuntimeError`, **not** a `GlpiError` -- `except GlpiError:` will not catch it. The message is `GLPI Fields plugin helpers require the legacy v1 session to be configured (set v1_base_url and v1_user_token).` Supplying exactly one of the pair raises `GlpiValidationError` at client construction instead.
- **Discovery is mandatory, not advisory.** Container and field names are chosen by whoever configured the plugin on that instance, and the plugin itself is optional. There is nothing to hardcode: read `container.name` and `field.name` off the server and reuse them verbatim.

```text
list_plugin_fields_containers(itemtype) → list_plugin_fields_fields(container_id)
    → list_item_plugin_field_rows(itemtype, items_id, container_name)
    → create_item_plugin_field_row(...) / update_item_plugin_field_row(...)
```

The family takes two different `values` shapes and they are not interchangeable -- flat for the low-level row helpers, nested for the two Ticket helpers:

```python
# create_item_plugin_field_row / update_item_plugin_field_row -- FLAT,
# one level, keyed by field.name:
values = {"extrainfofield": "<p>x</p>"}

# get_ticket_custom_fields / set_ticket_custom_fields -- NESTED,
# outer key is container.name:
values = {"extrainfo": {"extrainfofield": "<p>new</p>"}}
```

## Procedure

1. Create a client from the `glpi-client-setup` skill, adding `v1_base_url` and `v1_user_token`.
2. Discover containers with `list_plugin_fields_containers(itemtype="Ticket")`. `itemtype` is optional and filtered client-side. An uninstalled plugin does **not** return `[]`: it raises `GlpiStatusError` with `.status_code == 400` and `ERROR_RESOURCE_NOT_FOUND_NOR_COMMONDBTM` in `.response_text`. An installed-but-unused plugin returns `[]`.
3. Discover fields with `list_plugin_fields_fields(container_id=container.id)`. `field.name` is the key you put in a `values` dict; `field.type` (`string`, `text`, `richtext`, `dropdown`, `yesno`, `date`, `datetime`, `number`, `url`, `header`) tells you the value format.
4. Read the stored row with `list_item_plugin_field_rows(itemtype, items_id, container_name)` -- ordinary parameters, passable positionally or by keyword. It returns zero or one `GetPluginFieldsValueRow`; the values live in `row.extra_payload` and `row.id` is the `row_id` an update needs.
5. Write with `update_item_plugin_field_row(itemtype=..., container_name=..., row_id=..., values=...)` when a row exists, otherwise `create_item_plugin_field_row(itemtype=..., items_id=..., container_id=..., container_name=..., values=..., entities_id=...)`, which returns the new row id. Both are keyword-only.
6. On Tickets only, `get_ticket_custom_fields(ticket_id)` and `set_ticket_custom_fields(ticket_id, values)` fold steps 2-5 into one call each, using the nested mapping. For every other itemtype, drive steps 2-5 yourself.

## Examples

Discovery, including the branch that tells "plugin absent" apart from "plugin configured but empty":

```python
import asyncio

from glpi_python_client import AsyncGlpiClient, GlpiStatusError

# GLPI answers 400 with this marker when the itemtype in the URL is not a
# known CommonDBTM subclass -- which is what an uninstalled plugin looks
# like from the outside.
PLUGIN_ABSENT = "ERROR_RESOURCE_NOT_FOUND_NOR_COMMONDBTM"


async def main() -> None:
    async with AsyncGlpiClient(
        glpi_api_url="https://glpi.example.com/api.php/v2",
        server_timezone="Europe/Paris",
        client_id="oauth-client-id",
        client_secret="oauth-client-secret",
        v1_base_url="https://glpi.example.com/api.php/v1",
        v1_user_token="legacy-user-token",
    ) as client:
        try:
            containers = await client.list_plugin_fields_containers(itemtype="Ticket")
        except GlpiStatusError as exc:
            if exc.status_code == 400 and PLUGIN_ABSENT in (exc.response_text or ""):
                print("the GLPI Fields plugin is not installed on this instance")
                return
            raise

        for container in containers:
            if container.id is None or not container.name:
                continue
            # container.name is the internal key you reuse verbatim;
            # container.label is the UI label and is never a valid key.
            print(container.id, container.name, container.label, container.is_active)
            fields = await client.list_plugin_fields_fields(container_id=container.id)
            for field in fields:
                print("   ", field.name, field.type, field.is_active, field.is_readonly)


asyncio.run(main())
```

Read one ticket's custom fields. The result is the nested mapping, and a container with nothing saved is missing from it entirely:

```python
from glpi_python_client import AsyncGlpiClient


async def ticket_note(client: AsyncGlpiClient, ticket_id: int) -> str | None:
    """Return one ticket's `extrainfo.extrainfofield` value, if it has one."""
    values = await client.get_ticket_custom_fields(ticket_id)
    # {'extrainfo': {'extrainfofield': '<p>test</p>'}}

    # Containers with no persisted row are ABSENT, not empty: `.get`, never [].
    note = values.get("extrainfo", {}).get("extrainfofield")

    # The inner dict is the row's extra_payload -- dynamic columns only, so
    # it carries no row id. For that, drop to the low-level row listing:
    rows = await client.list_item_plugin_field_rows("Ticket", ticket_id, "extrainfo")
    if rows:
        print(rows[0].id, rows[0].items_id, rows[0].extra_payload)
    return note
```

Write to a ticket with the high-level upsert. Values go over the wire verbatim, so a `richtext` field takes raw HTML:

```python
from glpi_python_client import GlpiValidationError

await client.set_ticket_custom_fields(
    1234, {"extrainfo": {"extrainfofield": "<p>Handled by the NOC shift</p>"}}
)
# GET containers, GET fields, GET rows, then PUT {"input": {"id": 1, ...}}
# -- or POST with items_id/itemtype/plugin_fields_containers_id if no row exists.

await client.set_ticket_custom_fields(1234, {})  # empty mapping: zero HTTP calls

# Container names are matched EXACT-CASE against container.name.
try:
    await client.set_ticket_custom_fields(1234, {"ExtraInfo": {"extrainfofield": "x"}})
except GlpiValidationError as exc:
    print(exc)  # Unknown plugin-fields container(s) for Ticket: ExtraInfo

# The call is not atomic across containers, so write one per call when a
# rejected field name must not leave the earlier container already written.
payload = {
    "extrainfo": {"extrainfofield": "<p>a</p>"},
    "secondary": {"othercolumn": "b"},
}
for container_name, columns in payload.items():
    await client.set_ticket_custom_fields(1234, {container_name: columns})
```

Upsert on any other itemtype, with the flat `values` dict and the low-level helpers:

```python
from glpi_python_client import AsyncGlpiClient


async def upsert_plugin_field_row(
    client: AsyncGlpiClient,
    itemtype: str,               # "Computer", "Problem", "Change", ...
    items_id: int,
    container_id: int,           # container.id -- create needs it in the body
    container_name: str,         # container.name -- it builds the URL itemtype
    values: dict[str, object],   # FLAT: {field.name: value}
) -> int:
    """Update this container's row for one item, creating it when absent."""
    # Positional is allowed here (ordinary parameters); the two writers
    # below are keyword-only and raise TypeError if called positionally.
    rows = await client.list_item_plugin_field_rows(itemtype, items_id, container_name)
    if rows and rows[0].id is not None:
        await client.update_item_plugin_field_row(
            itemtype=itemtype,
            container_name=container_name,
            row_id=rows[0].id,
            values=values,  # only these columns are touched
        )
        return rows[0].id
    return await client.create_item_plugin_field_row(
        itemtype=itemtype,
        items_id=items_id,
        container_id=container_id,
        container_name=container_name,
        values=values,
        # `entities_id` is create-only and is omitted from the body unless
        # you pass it, letting the server apply its default scope. Do NOT
        # hardcode 0 here: 0 is not None, so it would pin every row you
        # create to entity 0. Pass a real entity id only when you mean one.
    )
```

## Gotchas

- **The two `values` shapes are the main trap.** `create_item_plugin_field_row` and `update_item_plugin_field_row` take a **flat** `dict[str, object]` of field name to value -- `values={"extrainfofield": "<p>x</p>"}`. `get_ticket_custom_fields` returns, and `set_ticket_custom_fields` accepts, a **nested** `dict[str, dict[str, Any]]` keyed by container name -- `{"extrainfo": {"extrainfofield": "<p>new</p>"}}`. Passing the nested shape to the low-level create sends the inner dict as a column value; passing the flat shape to `set_ticket_custom_fields` makes field names look like container names and raises `GlpiValidationError: Unknown plugin-fields container(s) for Ticket: ...`.
- `container_name` and `container_id` are not interchangeable, and `create_item_plugin_field_row` needs **both**. The name builds the URL itemtype, lowercased (`Ticket` + `extrainfo` gives `PluginFieldsTicketextrainfo`, and `Ticket/1234/PluginFieldsTicketextrainfo` for the row list). The id is a body column, `plugin_fields_containers_id`, and it is also what `list_plugin_fields_fields(container_id=...)` filters on. `update_item_plugin_field_row` needs only the name plus a `row_id`, which identifies the record on its own. `list_item_plugin_field_rows` needs only the name too, and has **no** `row_id` parameter -- its signature is exactly `(itemtype, items_id, container_name)`; it is what you call *to obtain* a `row_id`.
- Container-name matching in `set_ticket_custom_fields` is **exact-case** against `container.name`, while the URL derivation lowercases. So `{"ExtraInfo": {...}}` raises `GlpiValidationError` when the container is actually named `extrainfo`, even though the derived URL would have been identical. Copy `container.name` verbatim from discovery; never retype it and never substitute `container.label`.
- `set_ticket_custom_fields` is **not atomic across multiple containers**, despite a docstring claiming validation happens "before any write to keep the call atomic". Only the unknown-*container* check runs up front for the whole payload; the unknown-*field* check runs per container inside the write loop. With two containers where the second has a typo, the first is already written when the error raises. Write one container per call when you need all-or-nothing.
- `get_ticket_custom_fields` returns **only `extra_payload`** -- every *undeclared* key of the row, not a curated list of the plugin's fields. So the row's `id`, `items_id`, `itemtype`, `plugin_fields_containers_id` and `entities_id` are absent (use `list_item_plugin_field_rows` when you need the `row_id`), and any other bookkeeping column the v1 server returns appears alongside real values. Intersect against `list_plugin_fields_fields` names if you need only declared fields.
- A container that has never had a value saved for that ticket is **silently absent** from the `get_ticket_custom_fields` result -- you do not get `{"container": {}}`. Use `result.get(name, {})`, never `result[name]`. An empty overall dict is **ambiguous**: `get_ticket_custom_fields` builds its result by skipping every container with no persisted row, so `{}` comes back both when the instance declares no Ticket containers at all and when it declares several but this ticket has saved nothing in any of them. The return value cannot tell you which -- call `list_plugin_fields_containers(itemtype="Ticket")` if you need to know.
- Both discovery listings fetch **one fixed page, `range=0-999`**, with no pagination and no server-side filtering. The `itemtype` and `container_id` narrowing happens client-side *after* that cap, so an instance with more than 1000 containers or field declarations silently loses the tail -- possibly including the container you are looking for.
- Neither listing filters on `is_active`, so **disabled containers and disabled or read-only fields come back from discovery looking exactly like live ones**. `set_ticket_custom_fields` accepts a field whose `is_readonly` is `True`, because its guard only checks that the name is declared. Check `container.is_active`, `field.is_active` and `field.is_readonly` yourself.
- Values are transmitted **verbatim -- there is no HTML/Markdown conversion on this path**, unlike ticket and KB article content. A `richtext` field takes raw HTML (`"<p>test</p>"`). Convert yourself if you want Markdown: `GlpiContentConverter` is not exported from the package root, import it from `glpi_python_client.content`.
- The two convenience helpers are **Ticket-only** -- the itemtype is hardcoded. There is no `get_item_custom_fields` and no `set_item_custom_fields`. For Computer, Problem, Change and the rest, drive the generic row helpers.
- Parameter-passing style is inconsistent across the family, and only one half of it is a rule. `list_item_plugin_field_rows(itemtype, items_id, container_name)` declares ordinary `POSITIONAL_OR_KEYWORD` parameters, so both `("Ticket", 1234, "extrainfo")` and `(itemtype="Ticket", items_id=1234, container_name="extrainfo")` are legal -- the examples above pass them positionally by choice, not by requirement. `create_item_plugin_field_row` and `update_item_plugin_field_row` are genuinely **keyword-only** (`*` in the signature): calling either writer positionally is a `TypeError`.
- Error taxonomy on the write path: an unknown container name or an unknown field name raises `GlpiValidationError`; a container the server returned without an `id`, or a create whose v1 reply carries no numeric row id, raises `GlpiProtocolError`. Both inherit `ValueError`. A missing v1 session raises a plain `RuntimeError`, and a non-success v1 status raises `GlpiStatusError` (with `.status_code`, `.url` and `.response_text`).
- `entities_id` exists on **create only**, and is left out of the body unless explicitly passed. `update_item_plugin_field_row` has no such parameter -- its body is exactly `{"input": {"id": row_id, **values}}`. `set_ticket_custom_fields` never passes it, so rows it creates take the GLPI server's default scope.
- Cost is **linear and sequential**; there is no concurrent fan-out in this family. `get_ticket_custom_fields` costs one container list plus one row list per Ticket container. `set_ticket_custom_fields` costs one container list plus, per container in the payload, one field list, one row list and one write -- and it re-reads discovery on every call, with no caching. Cache the container and field listings yourself when writing many tickets in a loop.
- `PostPluginFieldsValueRow` is exported at the package root but is **dead surface for callers**: no client method takes or returns it. `create_item_plugin_field_row` assembles the request body itself from a plain dict. Building this model and handing it to the client neither type-checks nor works.
