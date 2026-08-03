---
name: glpi-knowledge-base
description: "Search, read, create, update, and delete GLPI knowledge base articles, categories, comments, and revisions with the synchronous glpi_python_client.GlpiClient or the asynchronous AsyncGlpiClient, and the GetKBArticle/PostKBArticle/GetKBCategory/GetKBArticleComment/GetKBArticleRevision models. Use for GLPI knowledge base content, FAQ articles, article categories, article comments, article revision history, or assigning categories to a KB article."
license: MIT
compatibility: "Requires Python 3.10+, glpi-python-client, network access to the GLPI v2 API, and — for category writes only — a legacy v1 session (v1_base_url + v1_user_token)."
metadata:
  package: glpi-python-client
  version: "0.4.1"
---

# GLPI Knowledge Base
> The snippets below use `AsyncGlpiClient` (`async with` + `await`). Every method shown also exists on the synchronous `GlpiClient` with the same signature -- replace `async with` with `with`, drop the `await` keyword, and skip the surrounding `async def`/`asyncio.run` scaffolding.

The GLPI knowledge base lives under `/Knowledgebase/*` on the v2 API and covers four resources: articles, their categories, article comments, and article revisions. Eighteen methods expose them, present on both `GlpiClient` and `AsyncGlpiClient` with identical signatures. One operation -- assigning categories to an article -- is not a v2 call at all and needs a legacy v1 session; everything else in the family is pure v2.

## Procedure

1. Create a client from the `glpi-client-setup` skill. Add `v1_base_url` and `v1_user_token` **only** if you will write article categories.
2. Articles: `search_kb_articles(rsql_filter, limit=..., start=..., sort=..., language=...)` for lists and `get_kb_article(article_id)` for one. Write with `create_kb_article(PostKBArticle(...))` (returns the new id), `update_kb_article(article_id, PatchKBArticle(...))` and `delete_kb_article(article_id, force=...)` (both return `None`).
3. Article categories: `set_kb_article_categories(article_id, category_ids)`. The ids **replace** the whole set; an empty sequence clears it. Ids are not validated against the server -- an unknown id is simply not linked.
4. Categories: `search_kb_categories(...)` (same parameters as the article search), `get_kb_category(category_id)`, `create_kb_category(PostKBCategory(...))`, `update_kb_category(category_id, PatchKBCategory(...))`, `delete_kb_category(category_id, force=...)`. `completename` and `level` are server-managed and absent from the write models.
5. Comments: `list_kb_article_comments(article_id)`, `get_kb_article_comment(article_id, comment_id)`, `create_kb_article_comment(article_id, PostKBArticleComment(...))` (returns the new id), `update_kb_article_comment(article_id, comment_id, PatchKBArticleComment(...))`, `delete_kb_article_comment(article_id, comment_id, force=...)`. The parent article comes from the URL, so `PostKBArticleComment` has no `kbarticle` field.
6. Revisions, read-only: `list_kb_article_revisions(article_id, language=...)` then `get_kb_article_revision(article_id, revision, language=...)`.
7. Refetch with `get_kb_article()` when the task needs a populated model after a write.

## Examples

Create a category and a categorised article. `v1_base_url`/`v1_user_token` are required here **only** because the article carries `categories`:

```python
from glpi_python_client import AsyncGlpiClient, IdNameRef, PostKBArticle, PostKBCategory

async with AsyncGlpiClient(
    glpi_api_url="https://glpi.example.com/api.php/v2",
    client_id="oauth-client-id",
    client_secret="oauth-client-secret",
    v1_base_url="https://glpi.example.com/api.php/v1",
    v1_user_token="legacy-user-token",
) as client:
    category_id = await client.create_kb_category(
        PostKBCategory(name="Network", comment="Networking runbooks")
    )
    # content/description are Markdown here and HTML on the wire.
    article_id = await client.create_kb_article(
        PostKBArticle(
            name="Reset a password",
            content="Run **passwd**, then check `logs`.",
            description="A *short* summary.",
            is_faq=True,
            categories=[IdNameRef(id=category_id)],  # IdRef would not validate
        )
    )
```

Recover from the non-atomic create. There is no rollback: on failure the article exists and its id is only available from the message text:

```python
import re

from glpi_python_client import AsyncGlpiClient, PostKBArticle


async def create_with_categories(client: AsyncGlpiClient, article: PostKBArticle) -> int:
    """Create `article`, re-linking its categories if the fallback failed.

    The retry presupposes a configured v1 session: when the missing session
    is itself the cause, `set_kb_article_categories` raises the same
    `RuntimeError` again. It helps only for a transient legacy failure.
    """
    try:
        return await client.create_kb_article(article)
    except RuntimeError as exc:  # plain builtin, NOT a GlpiError
        match = re.search(r"KB article (\d+) was created", str(exc))
        if match is None:
            raise
        article_id = int(match.group(1))
        # The v2 article is intact; retry only the legacy category link.
        # Derive the ids from the model -- they are the same list that
        # triggered the fallback, so the retry cannot link nothing.
        await client.set_kb_article_categories(
            article_id, [c.id for c in article.categories or [] if c.id is not None]
        )
        return article_id
```

Search, and disambiguate an empty result. `language` is a query parameter on both search helpers:

```python
from glpi_python_client import GlpiNotFoundError

faq = await client.search_kb_articles(
    "is_faq==1", limit=25, start=0, sort="date_mod desc", language="fr_FR"
)
categories = await client.search_kb_categories("name==Network", limit=10)
print([(c.id, c.completename) for c in categories])

# A search never raises on a 4xx -- it returns []. To tell 'no matches'
# from 'this GLPI serves no /Knowledgebase routes', probe an article you
# know exists. Only the SUCCEEDING branch is informative: a 404 is raised
# both by an absent route and by an absent id, so it proves nothing.
if not faq:
    known_article_id = 1  # an article known to exist on this instance
    try:
        await client.get_kb_article(known_article_id)
    except GlpiNotFoundError:
        print("inconclusive: no such article, or no /Knowledgebase routes")
    else:
        print("the endpoint is served -- the filter simply matched nothing")
```

Comments and revisions on one article:

```python
from glpi_python_client import PatchKBArticleComment, PostKBArticleComment

# `comment` is plain text -- no Markdown conversion, unlike article content.
comment_id = await client.create_kb_article_comment(
    5, PostKBArticleComment(comment="Confirmed on GLPI 11.")
)
await client.update_kb_article_comment(
    5, comment_id, PatchKBArticleComment(comment="Edited.")
)
one = await client.get_kb_article_comment(5, comment_id)
for listed in await client.list_kb_article_comments(5):
    print(listed.id, listed.comment)
await client.delete_kb_article_comment(5, comment_id, force=True)

# `language` is a PATH SEGMENT here: Knowledgebase/Article/5/fr_FR/Revision
revisions = await client.list_kb_article_revisions(5, language="fr_FR")
if revisions and revisions[0].revision is not None:
    revision = await client.get_kb_article_revision(
        5, revisions[0].revision, language="fr_FR"  # the revision NUMBER
    )
    print(revision.revision, revision.content)  # content comes back as Markdown
```

Category maintenance is pure v2 -- no legacy session is involved:

```python
from glpi_python_client import IdNameRef, PatchKBCategory, PostKBCategory

parent_id = await client.create_kb_category(PostKBCategory(name="IT"))
child_id = await client.create_kb_category(
    PostKBCategory(name="Network", parent=IdNameRef(id=parent_id), is_recursive=True)
)
await client.update_kb_category(child_id, PatchKBCategory(comment="Moved"))
category = await client.get_kb_category(child_id)
print(category.completename, category.level)  # both server-managed

await client.delete_kb_category(child_id, force=True)  # omit force to trash it
await client.delete_kb_article(42, force=True)
```

## Gotchas

- Assigning categories to an article is the only KB operation that needs the legacy v1 session, and it is not a v2 call at all: `set_kb_article_categories` issues a legacy `PUT KnowbaseItem/{article_id}` with the body `{"input": {"_categories": [ids]}}`. Every category CRUD call, every comment call and every revision call is pure v2.
- When no v1 session is configured, that path raises a plain builtin `RuntimeError`, **not** a `GlpiError` -- `except GlpiError:` will not catch it. The message is `GLPI knowledge base category assignments require the legacy v1 session to be configured (set v1_base_url and v1_user_token).` The session is only built when *both* `v1_base_url` and `v1_user_token` are supplied; exactly one of the pair raises `GlpiValidationError` at client construction.
- `create_kb_article` is not atomic and there is no rollback. If the v2 POST succeeds and the category fallback then fails, the article stays on the server: you get an error *and* an uncategorised article. The failure is a `RuntimeError` shaped `KB article 88 was created but assigning its categories failed: ...`, chaining the original as `__cause__` -- so the new id is recoverable only from the message text, and `except GlpiValidationError:` around a create catches nothing.
- `update_kb_article` does not wrap the failure the way create does -- the raw error propagates (`GlpiValidationError` for a category reference with no `id`, `RuntimeError` for a missing v1 session, `GlpiStatusError` for a legacy non-success). The v2 field changes are already applied and are not reverted.
- `categories=[]` means opposite things on create and update. On create it is skipped entirely: no v1 call, no v1 session needed. On update it *clears* every category, which is a legacy write and does need v1. Only `categories=None` (the default) is a no-op on both.
- `categories` is still sent inside the v2 POST/PATCH body and GLPI silently ignores it; the body is never stripped. So a create-with-categories against a client with no v1 session yields an uncategorised article *and* an error, not a clean rejection -- and no code path persists a category through v2 alone.
- **Every `search_*` helper in the library swallows 4xx and returns `[]`. This is a library-wide contract, not a KB peculiarity.** `_resource_list` checks the response status only when the caller passes a `failure_message`, and none of the seven searches -- `search_kb_articles`, `search_kb_categories`, `search_tickets`, `search_users`, `search_locations`, `search_entities`, `search_documents` -- passes one. A GLPI error body is not a JSON list, so it is coerced to `[]`. Every `list_*` and `get_*` helper does pass a `failure_message` and raises normally: here that is `list_kb_article_comments`, `list_kb_article_revisions`, `get_kb_article`, `get_kb_category` and `get_kb_article_revision` (`GlpiNotFoundError` on a 404). So an empty list from a search means "no matches" *or* "bad RSQL filter" *or* "403" *or* "this GLPI serves no `/Knowledgebase` routes at all" (they need High-Level API >= 2.2.0), indistinguishably; an empty list from a list helper is unambiguous. Never treat `[]` from a search as proof a record is absent before creating one.
- `language` has two different mechanics in this family. On `search_kb_articles`/`search_kb_categories` it is a **query parameter**. On `list_kb_article_revisions`/`get_kb_article_revision` it is a **path segment** between the id and `Revision` (`Knowledgebase/Article/5/fr_FR/Revision`). `get_kb_article`, the comment helpers and every write helper take no `language` at all; they inherit the client-level value, sent as `Accept-Language` (default `en_GB`).
- KB write models use `IdNameRef` for every foreign key -- `categories[]`, `entity`, `user`, `parent` -- not `IdRef`. Passing `IdRef(id=4)` raises a pydantic `ValidationError`. (`GetKBArticleComment.parent` is the one KB field genuinely typed `IdRef`, and it is read-only.)
- Article `content`/`description` and revision `content` are Markdown on the Python side and HTML on the wire; the conversion is automatic, so never author HTML. Comment `comment` is a plain `str` with no conversion at all -- the inconsistency is real, not an omission here.
- `force` on `delete_kb_article`, `delete_kb_category` and `delete_kb_article_comment` is keyword-only and is serialised into the JSON request **body** via the matching `Delete*` model, not sent as a query parameter. `force=True` deletes permanently; omitting it or passing `False` moves the record to the GLPI trash.
- Revisions are read-only: there is no create/update/delete helper and no Post/Patch/Delete revision model. A revision appears as a side effect of updating an article. `get_kb_article_revision(article_id, revision)` takes the revision **number** (`GetKBArticleRevision.revision`), not the row `id` -- the two differ on the model.
- `GetKBArticle.revisions` and `.translations` hold two *different* private ref classes (leading underscore, not exported from the package root). Read their attributes; never import them. The two field sets are not interchangeable: a `revisions` entry has `.id`, `.revision`, `.language`, `.date`, while a `translations` entry has `.id`, `.language`, `.name`. `revisions[0].name` raises `AttributeError` -- the models allow unknown keys from the server, but that does not synthesise an attribute that was never sent.
