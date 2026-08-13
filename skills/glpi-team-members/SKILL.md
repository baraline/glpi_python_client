---
name: glpi-team-members
description: "List, add, and remove GLPI ticket team members with the synchronous glpi_python_client.GlpiClient or the asynchronous AsyncGlpiClient, and the GetTeamMember/PostTeamMember models. Use when assigning users or groups to tickets, inspecting ticket teams, or removing GLPI ticket participants."
license: MIT
compatibility: "Requires Python 3.10+, glpi-python-client, network access to the GLPI v2 API, and credentials allowed to manage ticket teams."
metadata:
  package: glpi-python-client
  version: "0.4.3"
---

# GLPI Team Members
> The snippets below use `AsyncGlpiClient` (`async with` + `await`). Every method shown also exists on the synchronous `GlpiClient` with the same signature -- replace `async with` with `with`, drop the `await` keyword, and skip the surrounding `async def`/`asyncio.run` scaffolding.

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
- **There is no update method, and `PatchTeamMember` is dead surface for callers.** The family is exactly three methods -- `list_ticket_team_members(ticket_id)`, `add_ticket_team_member(ticket_id, member: PostTeamMember)`, `remove_ticket_team_member(ticket_id, member: PostTeamMember)` -- and both writers take a `PostTeamMember`, never a `PatchTeamMember`. `PatchTeamMember` *is* exported from `glpi_python_client` (it subclasses `PostTeamMember` and declares the same three optional fields, `id`, `type`, `role`, plus `extra_payload`), but no client method accepts or returns it, so building one and handing it to the client neither type-checks nor works. To change someone's role, remove the old entry and add the new one.
- The server returns extra fields such as `display_name`, `firstname`, `realname`, and `href` on `GetTeamMember`. These flow into `member.extra_payload`.
- The three methods are coroutines on `AsyncGlpiClient` and must be awaited; on the synchronous `GlpiClient` they are ordinary blocking methods with identical signatures (`_sync/` is generated from `_async/`, so the two surfaces cannot drift). Do not `await` the synchronous client.
- If the user provides a name rather than an ID, resolve it first with `await client.search_users(rsql_filter)` (or page through `client.iter_search_users(...)`) and confirm the ID before changing membership. The client exposes **no group search endpoint** — a `type="Group"` member's `id` has to come from elsewhere (a known id, or the GLPI UI); `search_users` only covers `type="User"`.