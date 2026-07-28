# glpi-python-client Agent Skills

This folder contains Agent Skills for common operations exposed by the public `glpi_python_client` API. Each child directory is a standalone skill that follows the Agent Skills specification: the directory name matches the `name` frontmatter field, and the main instructions live in `SKILL.md`.

These skills are source-tree project material. They are included in source distributions for contributors and source consumers, but they are not part of the installed runtime wheel, which only ships the `glpi_python_client` package.

## Skills

| Skill | Use when the agent needs to | Main public API |
| --- | --- | --- |
| `glpi-client-setup` | Build and configure an authenticated client | `GlpiClient`, `AsyncGlpiClient`, `.from_env()` |
| `glpi-ticket-workflow` | Search, fetch, create, update, or delete tickets | `GetTicket`, `PostTicket`, `PatchTicket`, `DeleteTicket` |
| `glpi-ticket-timeline` | Read timeline records or write followups, tasks, solutions, and document links | `PostFollowup`, `PostTicketTask`, `PostSolution`, `PostTimelineDocument` (plus matching Get/Patch/Delete) |
| `glpi-document-workflow` | Manage document metadata, upload binary content, download binaries | `GetDocument`, `PostDocument`, `PatchDocument`, `DeleteDocument` |
| `glpi-user-location-provisioning` | Search and provision users, locations, and entities | `GetUser`, `PostUser`, `GetLocation`, `PostLocation`, `GetEntity`, `PostEntity` |
| `glpi-reporting-and-context` | Aggregate ticket statistics, aggregate task durations, or load one ticket context bundle | `GlpiClient`, `GlpiTicketContext`, public enums |
| `glpi-team-members` | List, add, or remove ticket team members | `GetTeamMember`, `PostTeamMember` |

## Sync and async

The package ships two clients with identical endpoint surfaces:

- `GlpiClient` — synchronous. `with GlpiClient(...) as client`, no `await`.
- `AsyncGlpiClient` — asynchronous, performing real non-blocking I/O. `async with AsyncGlpiClient(...) as client`, `await` every method.

Neither wraps the other: the async tree is hand-written and the synchronous one is generated from it by `unasync_build.py`, so the two cannot drift apart. The snippets in each skill are written against `AsyncGlpiClient`; every skill opens with a note on how to read them for the synchronous client.

When fanning out concurrently on the async client, bound the fan-out with an `asyncio.Semaphore` — see `glpi-client-setup`. An unbounded fan-out is slower, not faster.
