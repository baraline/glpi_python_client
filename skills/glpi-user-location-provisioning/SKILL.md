---
name: glpi-user-location-provisioning
description: "Search GLPI users, locations, and entities, or create, update, and delete users and locations and entities with the synchronous glpi_python_client.GlpiClient or the asynchronous AsyncGlpiClient, and the matching Get/Post/Patch/Delete models. Use for user lookup, entity lookup, location lookup, user provisioning, location creation, GLPI entity defaults, or RSQL filters."
license: MIT
compatibility: "Requires Python 3.10+, glpi-python-client, network access to the GLPI v2 API, and credentials allowed to read or write users, locations, and entities."
metadata:
  package: glpi-python-client
  version: "0.4.0"
---

# GLPI User, Location, And Entity Provisioning
> The snippets below use `AsyncGlpiClient` (`async with` + `await`). Every method shown also exists on the synchronous `GlpiClient` with the same signature -- replace `async with` with `with`, drop the `await` keyword, and skip the surrounding `async def`/`asyncio.run` scaffolding.

Users live under `/Administration/User`, entities under `/Administration/Entity`, and locations under `/Dropdown/Location`. Each resource family is exposed by the same `search_/get_/create_/update_/delete_` shape on `GlpiClient` with matching `Get`/`Post`/`Patch`/`Delete` Pydantic models.

## Procedure

1. Create a `GlpiClient` with the correct entity/profile scope.
2. Search before creating duplicates: `search_users(rsql_filter, limit=..., start=...)`, `search_locations(rsql_filter, limit=..., start=...)`, `search_entities(rsql_filter, limit=..., start=...)`.
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

Find or create a location:

```python
from glpi_python_client import PostLocation

matches = await client.search_locations('name=="Paris HQ"')
location_id = (
    matches[0].id
    if matches
    else await client.create_location(PostLocation(name="Paris HQ"))
)
```

Look entities up by name fragment:

```python
entities = await client.search_entities("name=like=*acme*", limit=10)
for entity in entities:
    print(entity.id, entity.name, entity.completename)
```

## Gotchas

- All methods are async; always `await` them.
- `PostUser` requires `username` and the GLPI server enforces the `password`/`password2` pair when creating local users. Tweak according to your auth backend.
- Search filters are raw RSQL strings; pagination is via `limit` and `start`.
- Extra keys returned by the live server (`display_name`, plugin fields, ...) flow into `record.extra_payload` rather than raising.
- `delete_*(force=True)` permanently deletes the record; omit (or `False`/`None`) to move it to the trash.
- If the user provides a name rather than an ID, search first and confirm the ID before changing or deleting records.