---
name: glpi-user-location-provisioning
description: "Search and create GLPI users and locations with glpi_python_client GlpiClient, AsyncGlpiClient, GlpiUser, and GlpiLocation. Use for user lookup, user provisioning, location lookup, location creation, GLPI entity defaults, notification defaults, and RSQL user filters."
license: MIT
compatibility: "Requires Python 3.10+, glpi-python-client, network access to the GLPI high-level API, and credentials allowed to read or create users and locations."
metadata:
  package: glpi-python-client
  version: "0.1.0"
---

# GLPI User And Location Provisioning

After the directory refactor, keep imports on the public package root. User and location behavior now lives in `glpi_python_client.clients.v2.sync.directory`, `glpi_python_client.clients.v2.async_.directory`, and `glpi_python_client.content.records.parsers.directory`.

Use this skill when the task is about GLPI users or locations rather than ticket records. In async code, use the same method names on `AsyncGlpiClient` with `await`.

## Procedure

1. Create a `GlpiClient` or `AsyncGlpiClient` with the correct entity/profile scope.
2. Search existing users with `search_users(rsql_filter, limit=..., start=..., skip_entity=...)` before creating duplicates.
3. Create users with `GlpiUser` and `create_user(user)`. The method returns the created `user_id`.
4. Search locations with `search_locations(name)` before creating duplicates.
5. Create locations with `GlpiLocation` and `create_location(location)`. The method returns the created `location_id`.
6. Re-search after writes when the task needs hydrated models instead of the created IDs.

## Examples

Search for a user by email:

```python
from glpi_python_client import GlpiClient

with GlpiClient.from_env() as glpi:
    users = glpi.search_users('email=="jane.doe@example.com"', limit=5)
```

Create a user:

```python
from glpi_python_client import GlpiClient, GlpiUser

with GlpiClient.from_env() as glpi:
    user_id = glpi.create_user(
        GlpiUser(
            email="jane.doe@example.com",
            firstname="Jane",
            realname="Doe",
            entity_id=1,
            default_is_notifications_enabled=True,
        )
    )
    print(user_id)
```

Find or create a location:

```python
from glpi_python_client import GlpiClient, GlpiLocation

with GlpiClient.from_env() as glpi:
    matches = glpi.search_locations("Paris HQ")
    location_id = matches[0].location_id if matches else glpi.create_location(
        GlpiLocation(name="Paris HQ", entity_id=1)
    )
    print(location_id)
```

## Gotchas

- `GlpiUser` creation requires at least a name or email; email becomes the username when present.
- `search_users()` defaults to `limit=1`. Increase `limit` when the task expects multiple matches.
- `create_user()` and `create_location()` return IDs, not hydrated models.
- Use `skip_entity=True` for user searches only when the user explicitly needs a global lookup outside entity/profile routing.
- `search_locations(name)` performs a name-fragment lookup and strips double quotes from the search text.
- `AsyncGlpiClient` exposes the same directory methods with `await`.
