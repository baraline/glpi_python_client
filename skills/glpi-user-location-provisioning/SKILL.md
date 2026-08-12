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
   To resolve a person by e-mail use `await client.find_user_by_email("a@b.test")`, which returns `GetUser | None` and defaults to `skip_entity=True` for the reason just given.
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

- **`search_users`, `search_locations` and `search_entities` raise `GlpiStatusError` on a 4xx.** This changed: they used to check the response status only when the caller passed a `failure_message`, which none of the seven `search_*` helpers does, so a GLPI error body was coerced to `[]` and a malformed RSQL filter, a 403, a missing route and a genuinely empty result set were indistinguishable. `_resource_list` now checks the status on every call, so **an empty list means the server said the result set is empty**. The iterators inherit that: a 4xx raises instead of making the first page short and ending the walk silently. Note the *other* fail-open path is unchanged and still bites -- GLPI v2 ignores a filter field it does not recognise and answers 200 with the whole unfiltered table, so a filter that returns rows is still not proof it was applied. **The find-or-create pattern was the trap this protected against**: `matches[0].id if matches else create(...)` provisioned a duplicate every time the search failed. A 403 now raises there. It is still worth validating anything you interpolate into a filter, because the silent-drop path returns a *non-empty* wrong answer that no status check can catch.
- On `AsyncGlpiClient` every method shown is a coroutine -- always `await` it -- and `iter_search_users` / `iter_search_entities` are async generators consumed with `async for`, not `await`. The generated `GlpiClient` carries the same names and signatures as ordinary blocking calls: no `await`, and a plain `for` over the iterators.
- `PostUser` has **no** client-side required fields: every declared field defaults to `None` (bar `extra_payload`, which defaults to an empty dict) and `model_dump(exclude_none=True)` strips the unset ones, so `PostUser()` validates fine and it is the GLPI server that rejects a create without `username` and enforces the `password`/`password2` pair for local accounts. Tweak according to your auth backend: `authtype` on `PostUser`/`PatchUser`/`GetUser` is typed `GlpiUserAuthType | None`, exported from the package root, with members `LOCAL = 1`, `LDAP = 2`, `MAIL = 3`, `CAS = 4`, `X509 = 5`, `EXTERNAL = 6` -- pass the member (`authtype=GlpiUserAuthType.LDAP`) rather than a bare integer. Like every public enum in the package it subclasses `GlpiEnum`, itself an `IntEnum`, so it serialises as its number and compares equal to one. `password`/`password2` are `SecretStr` (plain `str` is coerced) and are masked in `repr` and logs, unmasked only when the request body is serialised.
- Search filters are raw RSQL strings. `search_*` pages manually with `limit` and `start`, but all three resources now have a batch iterator that drives pagination for you: `iter_search_users(rsql_filter, batch_size=50, skip_entity=False)`, `iter_search_entities(rsql_filter, batch_size=50)` and `iter_search_locations(rsql_filter, batch_size=50)` yield successive pages and stop on the first short page (plain `for` on `GlpiClient`). `iter_search_users` carries the same `skip_entity` flag as `search_users`, so pass `skip_entity=True` there too when paging across every entity; the other two have no such parameter.
- `find_user_by_email("a@b.test")` resolves a person by address and returns `GetUser | None`. It **scans** -- GLPI exposes addresses as the nested array `User.emails`, which the v2 filter engine cannot join -- so narrow it with `rsql_filter="is_active==true"` where you can and cache the id instead of calling it per request. Do not hand-roll an RSQL e-mail filter: v2 ignores a field it does not recognise and answers with the whole table, so the first row would be the wrong person.
- Extra keys returned by the live server (`display_name`, plugin fields, ...) flow into `record.extra_payload` rather than raising.
- `delete_*(force=True)` permanently deletes the record; omit (or `False`/`None`) to move it to the trash.
- If the user provides a name rather than an ID, search first and confirm the ID before changing or deleting records.