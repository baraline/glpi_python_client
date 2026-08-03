---
name: glpi-user-location-provisioning
description: "Search GLPI users, locations, and entities, or create, update, and delete users and locations and entities with the synchronous glpi_python_client.GlpiClient or the asynchronous AsyncGlpiClient, and the matching Get/Post/Patch/Delete models. Use for user lookup, entity lookup, location lookup, user provisioning, location creation, GLPI entity defaults, or RSQL filters."
license: MIT
compatibility: "Requires Python 3.10+, glpi-python-client, network access to the GLPI v2 API, and credentials allowed to read or write users, locations, and entities."
metadata:
  package: glpi-python-client
  version: "0.4.1"
---

# GLPI User, Location, And Entity Provisioning
> The snippets below use `AsyncGlpiClient` (`async with` + `await`). Every method shown also exists on the synchronous `GlpiClient` with the same signature -- replace `async with` with `with`, drop the `await` keyword, and skip the surrounding `async def`/`asyncio.run` scaffolding.

Users live under `/Administration/User`, entities under `/Administration/Entity`, and locations under `/Dropdowns/Location`. Each resource family is exposed by the same `search_/get_/create_/update_/delete_` shape on `GlpiClient` with matching `Get`/`Post`/`Patch`/`Delete` Pydantic models.

## Procedure

1. Create a `GlpiClient` with the correct entity/profile scope.
2. Search before creating duplicates: `search_users(rsql_filter, limit=..., start=..., skip_entity=False)`, `search_locations(rsql_filter, limit=..., start=...)`, `search_entities(rsql_filter, limit=..., start=...)`. Scope matters here: `search_users` and `search_locations` are narrowed by the client's `GLPI-Entity` / `GLPI-Profile` headers, so pass `skip_entity=True` to `search_users` (the only one of the three `search_*` helpers that has the flag — `iter_search_users` takes it too) to look across every entity the caller can see before deciding a user does not exist; `search_entities` always bypasses those headers.
3. Fetch one record with `get_user(user_id)`, `get_location(location_id)`, or `get_entity(entity_id)`.
4. Create with `create_user(PostUser(...))`, `create_location(PostLocation(...))`, or `create_entity(PostEntity(...))`. Each returns the new ID.
5. Update with `update_user(user_id, PatchUser(...))`, `update_location(location_id, PatchLocation(...))`, or `update_entity(entity_id, PatchEntity(...))`.
6. Delete with `delete_user(user_id, force=True|False|None)` and the matching `delete_location` / `delete_entity` helpers.

## Examples

Search for a user by username:

```python
users = await client.search_users('username=="jane.doe"', limit=5)
```

Create a user:

```python
from glpi_python_client import PostUser

user_id = await client.create_user(
    PostUser(
        username="jane.doe",
        password="initial-pwd",
        password2="initial-pwd",
        firstname="Jane",
        realname="Doe",
    )
)
```

Find or create a location. The obvious spelling -- `matches[0].id if matches else create_location(...)` -- is a duplicate generator, because `search_locations` returns `[]` for a rejected filter or a 403 exactly as it does for "no such location" (see the first gotcha). Two guards close that, and neither is optional. Both fail closed: when they cannot prove the record is absent they raise rather than create, so the one case they refuse -- the very first location on an instance whose dropdown is still empty -- is an explicit opt-in, not a silent duplicate:

```python
from glpi_python_client import AsyncGlpiClient, PostLocation

#: Characters that terminate an RSQL token. A value carrying one produces a
#: filter the server rejects with a 400 -- which `search_locations` turns
#: into `[]`, i.e. into "create a duplicate".
_RSQL_UNSAFE = set("\"'();,=<>!~*")


async def find_or_create_location(
    client: AsyncGlpiClient, name: str, *, dropdown_may_be_empty: bool = False
) -> int:
    """Return the id of the location called `name`, creating it if absent."""
    if not name or _RSQL_UNSAFE & set(name):
        # Guard 1. The canary below cannot catch this case: it does not
        # carry this value, so it would come back healthy while the real
        # query was being rejected. Reject the value here instead.
        raise ValueError(f"value is not safe to interpolate into RSQL: {name!r}")

    matches = await client.search_locations(f'name=="{name}"')
    if matches and matches[0].id is not None:
        return matches[0].id

    # Guard 2. Empty is not proof of absence. Re-run the same route with no
    # filter at all -- same URL, same auth, same entity scope, nothing to
    # reject -- so a swallowed 403/404/5xx shows up here too. An empty
    # answer here has exactly two causes: the search layer failed, or the
    # Locations dropdown is genuinely empty (a fresh GLPI ships it empty).
    # This cannot tell them apart either, so it fails closed and makes the
    # second one something the caller states on purpose.
    if not await client.search_locations("", limit=1) and not dropdown_may_be_empty:
        raise RuntimeError(
            "search_locations returned nothing even unfiltered: assume a failed "
            "search, not a missing location. Pass dropdown_may_be_empty=True "
            "only once you have confirmed this instance has no locations yet."
        )
    return await client.create_location(PostLocation(name=name))
```

Look entities up by name fragment:

```python
entities = await client.search_entities("name=like=*acme*", limit=10)
for entity in entities:
    print(entity.id, entity.name, entity.completename)
```

## Gotchas

- **`search_users`, `search_locations` and `search_entities` swallow 4xx and return `[]`, and this family is where that hurts most.** It is a library-wide contract, not a peculiarity of these three: `_resource_list` checks the response status only when the caller passes a `failure_message`, and none of the seven `search_*` helpers (`search_users`, `search_locations`, `search_entities`, `search_tickets`, `search_documents`, `search_kb_articles`, `search_kb_categories`) passes one -- a GLPI error body is not a JSON list, so it is coerced to `[]`. A malformed RSQL filter, a 403, a missing route and "no such record" are therefore indistinguishable. `iter_search_users` / `iter_search_entities` inherit it: a swallowed 4xx makes the first page short, so the loop ends having yielded nothing. **The find-or-create pattern is the trap**: `matches[0].id if matches else create(...)` provisions a duplicate user or location every time the search fails, and the duplicate is then a data-repair job, not an exception someone sees. Guard both halves as the example above does -- validate anything you interpolate into the filter, and corroborate an empty result with an unfiltered control search or with a `get_user`/`get_location`/`get_entity` on a known id, all of which do pass a `failure_message` and raise `GlpiStatusError` (narrowed to `GlpiAuthError` / `GlpiNotFoundError` / `GlpiServerError`) normally.
- On `AsyncGlpiClient` every method shown is a coroutine -- always `await` it -- and `iter_search_users` / `iter_search_entities` are async generators consumed with `async for`, not `await`. The generated `GlpiClient` carries the same names and signatures as ordinary blocking calls: no `await`, and a plain `for` over the iterators.
- `PostUser` has **no** client-side required fields: every declared field defaults to `None` (bar `extra_payload`, which defaults to an empty dict) and `model_dump(exclude_none=True)` strips the unset ones, so `PostUser()` validates fine and it is the GLPI server that rejects a create without `username` and enforces the `password`/`password2` pair for local accounts. Tweak according to your auth backend: `authtype` on `PostUser`/`PatchUser`/`GetUser` is typed `GlpiUserAuthType | None`, exported from the package root, with members `LOCAL = 1`, `LDAP = 2`, `MAIL = 3`, `CAS = 4`, `X509 = 5`, `EXTERNAL = 6` -- pass the member (`authtype=GlpiUserAuthType.LDAP`) rather than a bare integer. Like every public enum in the package it subclasses `GlpiEnum`, itself an `IntEnum`, so it serialises as its number and compares equal to one. `password`/`password2` are `SecretStr` (plain `str` is coerced) and are masked in `repr` and logs, unmasked only when the request body is serialised.
- Search filters are raw RSQL strings. `search_*` pages manually with `limit` and `start`, but for users and entities the client drives pagination for you: `async for page in client.iter_search_users(rsql_filter, batch_size=50, skip_entity=False)` and `iter_search_entities(rsql_filter, batch_size=50)` yield successive pages and stop on the first short page (plain `for` on `GlpiClient`). `iter_search_users` carries the same `skip_entity` flag as `search_users`, so pass `skip_entity=True` there too when paging across every entity; `iter_search_entities` has no such parameter and always spans them. There is no `iter_search_locations` -- page `search_locations` yourself with `limit`/`start`.
- Extra keys returned by the live server (`display_name`, plugin fields, ...) flow into `record.extra_payload` rather than raising.
- `delete_*(force=True)` permanently deletes the record; omit (or `False`/`None`) to move it to the trash.
- If the user provides a name rather than an ID, search first and confirm the ID before changing or deleting records.