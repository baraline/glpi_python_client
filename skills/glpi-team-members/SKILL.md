---
name: glpi-team-members
description: "List, add, and remove GLPI ticket team members with the asynchronous glpi_python_client.GlpiClient and the GetTeamMember/PostTeamMember models. Use when assigning users or groups to tickets, inspecting ticket teams, or removing GLPI ticket participants."
license: MIT
compatibility: "Requires Python 3.10+, glpi-python-client, network access to the GLPI v2 API, and credentials allowed to manage ticket teams."
metadata:
  package: glpi-python-client
  version: "0.3.0"
---

# GLPI Team Members

Ticket team members are exposed under `/Assistance/Ticket/{id}/TeamMember`. The `GlpiClient` exposes three methods: `list_ticket_team_members`, `add_ticket_team_member`, and `remove_ticket_team_member`.

## Procedure

1. Create a `GlpiClient` with the entity/profile scope that can see the ticket.
2. List current membership with `await client.list_ticket_team_members(ticket_id)`.
3. Build `PostTeamMember(type=..., id=..., role=...)`:
   - `type` — GLPI itemtype string such as `"User"` or `"Group"`.
   - `id` — numeric identifier of the user or group to add.
   - `role` — GLPI role name such as `"assigned"`, `"observer"`, or `"requester"`.
4. Add with `await client.add_ticket_team_member(ticket_id, member)`.
5. Remove with `await client.remove_ticket_team_member(ticket_id, member)` where `member` is a `PostTeamMember` describing the entry to drop (same shape as the add call).

## Examples

List members:

```python
members = await client.list_ticket_team_members(321)
```

Add a user:

```python
from glpi_python_client import PostTeamMember

await client.add_ticket_team_member(
    321,
    PostTeamMember(type="User", id=42, role="assigned"),
)
```

Remove an existing membership entry:

```python
from glpi_python_client import PostTeamMember

await client.remove_ticket_team_member(
    321,
    PostTeamMember(type="User", id=42, role="assigned"),
)
```

## Gotchas

- The OpenAPI contract marks `PostTeamMember.id` as read-only, but the live GLPI server requires it on the `POST` body. The client honours the live behaviour and exposes `id` as a writable field; this is a deliberate "behaviour wins over the contract" decision.
- The server returns extra fields such as `display_name`, `firstname`, `realname`, and `href` on `GetTeamMember`. These flow into `member.extra_payload`.
- All methods are async; always `await` them.
- If the user provides a name rather than an ID, look the user or group up first with `search_users` (or the equivalent group search) and confirm the ID before changing membership.
