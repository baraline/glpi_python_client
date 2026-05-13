---
name: glpi-team-members
description: "List, add, and remove GLPI ticket team members with glpi_python_client GlpiClient, AsyncGlpiClient, and GlpiTeamMember. Use when assigning users or groups to tickets, inspecting ticket teams, changing team roles, or removing GLPI ticket participants."
license: MIT
compatibility: "Requires Python 3.10+, glpi-python-client, network access to the GLPI high-level API, and credentials allowed to manage ticket teams."
metadata:
  package: glpi-python-client
  version: "0.1.0"
---

# GLPI Team Members

After the team-member refactor, keep imports on the public package root. Ticket-team behavior now lives in `glpi_python_client.clients.v2.sync.team`, `glpi_python_client.clients.v2.async_.team`, and `glpi_python_client.content.records.parsers.team`.

Use this skill for ticket team membership operations. In async code, use the same method names on `AsyncGlpiClient` with `await`.

## Procedure

1. Create a `GlpiClient` or `AsyncGlpiClient` with the entity/profile scope that can see the ticket.
2. Inspect current membership with `get_team_member_records(ticket_id)`.
3. Build `GlpiTeamMember(member_type=..., member_id=..., role=...)` using GLPI values the user supplied or that you looked up.
4. Add the member with `add_team_member(ticket_id, member)`.
5. Remove the member with `remove_team_member(ticket_id, member)`.
6. Refetch with `get_team_member_records(ticket_id)` when the task needs authoritative post-change state.

## Examples

List members:

```python
from glpi_python_client import GlpiClient

with GlpiClient.from_env() as glpi:
    members = glpi.get_team_member_records("321")
```

Add a user to a ticket team:

```python
from glpi_python_client import GlpiClient, GlpiTeamMember

with GlpiClient.from_env() as glpi:
    member = GlpiTeamMember(member_type="User", member_id=42, role="assigned")
    glpi.add_team_member("321", member)
```

Remove a group from a ticket team:

```python
from glpi_python_client import GlpiClient, GlpiTeamMember

with GlpiClient.from_env() as glpi:
    member = GlpiTeamMember(member_type="Group", member_id=7, role="observer")
    glpi.remove_team_member("321", member)
```

## Gotchas

- The package passes `member_type`, `member_id`, and `role` through to GLPI. Use values valid for the target GLPI instance.
- `get_team_member_records()` returns an empty list when the API response is not a successful list payload.
- `add_team_member()` and `remove_team_member()` return `None`; they do not refetch the ticket team.
- `AsyncGlpiClient` exposes the same ticket-team methods with `await`.
- If the user provides a name rather than an ID, search users or groups first and confirm the exact ID before changing membership.
