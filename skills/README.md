# glpi-python-client Agent Skills

This folder contains Agent Skills for common operations exposed by the public `glpi_python_client` API. Each child directory is a standalone skill that follows the Agent Skills specification: the directory name matches the `name` frontmatter field, and the main instructions live in `SKILL.md`.

These skills are source-tree project material. They are included in source
distributions for contributors and source consumers, but they are not part of
the installed runtime wheel, which only ships the `glpi_python_client`
package.

## Skills

| Skill | Use when the agent needs to | Main public API |
| --- | --- | --- |
| `glpi-client-setup` | Build and configure authenticated clients | `GlpiClient`, `GlpiClient.from_env()` |
| `glpi-ticket-workflow` | Search, fetch, create, or update tickets | `GlpiClient`, `GlpiTicket` |
| `glpi-ticket-timeline` | Read timeline records or add notes and solutions | `GlpiFollowup`, `GlpiTask`, `GlpiSolution`, `GlpiDocument` |
| `glpi-document-workflow` | Upload, fetch, or download documents | `GlpiDocument`, `GlpiClient`, `GLPIV1Session` |
| `glpi-user-location-provisioning` | Search users, locations, and entities or create users and locations | `GlpiUser`, `GlpiLocation`, `GlpiEntity` |
| `glpi-reporting-and-context` | Search entities and tasks, aggregate durations and ticket stats, inspect user activity, or load one ticket context bundle | `GlpiClient`, `GlpiEntity`, `GlpiTask`, `GlpiTicketContext` |
| `glpi-team-members` | List, add, or remove ticket team members | `GlpiTeamMember` |

Validate individual skills with the reference validator when available:

```bash
skills-ref validate ./skills/glpi-client-setup
```
