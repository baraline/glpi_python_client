"""GLPI ``/Knowledgebase/Article/{id}/Comment`` mixin.

The mixin exposes list, fetch, create, update, and delete helpers for the
GLPI knowledge base article comment endpoint using the contract-aligned
``api_schema`` models.
"""

from __future__ import annotations

from glpi_python_client._sync.clients.commons._constants import (
    KB_ARTICLE_ENDPOINT,
    KB_COMMENT_SUFFIX,
    GlpiId,
)
from glpi_python_client._sync.clients.commons._transport import TransportMixin
from glpi_python_client.models.api_schema.knowledgebase._comment import (
    DeleteKBArticleComment,
    GetKBArticleComment,
    PatchKBArticleComment,
    PostKBArticleComment,
)


class KBArticleCommentMixin(TransportMixin):
    """CRUD helpers for KB article comments."""

    def list_kb_article_comments(
        self, article_id: GlpiId
    ) -> list[GetKBArticleComment]:
        """List every comment attached to one knowledge base article."""

        return self._resource_list(
            f"{KB_ARTICLE_ENDPOINT}/{article_id}/{KB_COMMENT_SUFFIX}",
            GetKBArticleComment,
            failure_message=f"Failed to list comments for KB article {article_id}",
        )

    def get_kb_article_comment(
        self, article_id: GlpiId, comment_id: GlpiId
    ) -> GetKBArticleComment:
        """Fetch one knowledge base article comment by identifier."""

        return self._resource_get(
            f"{KB_ARTICLE_ENDPOINT}/{article_id}/{KB_COMMENT_SUFFIX}/{comment_id}",
            GetKBArticleComment,
            failure_message=(
                f"Failed to get comment {comment_id} on KB article {article_id}"
            ),
        )

    def create_kb_article_comment(
        self, article_id: GlpiId, comment: PostKBArticleComment
    ) -> int:
        """Create one comment on a knowledge base article."""

        return self._resource_create(
            f"{KB_ARTICLE_ENDPOINT}/{article_id}/{KB_COMMENT_SUFFIX}",
            comment,
            failure_message=f"Failed to create comment on KB article {article_id}",
            missing_message="GLPI KB comment create response did not include an ID",
            log_message_factory=(
                lambda new_id: (
                    f"GLPI API created comment {new_id} on KB article {article_id}"
                )
            ),
        )

    def update_kb_article_comment(
        self,
        article_id: GlpiId,
        comment_id: GlpiId,
        comment: PatchKBArticleComment,
    ) -> None:
        """Update one knowledge base article comment with a partial body."""

        self._resource_update(
            f"{KB_ARTICLE_ENDPOINT}/{article_id}/{KB_COMMENT_SUFFIX}/{comment_id}",
            comment,
            failure_message=(
                f"Failed to update comment {comment_id} on KB article {article_id}"
            ),
            log_message=(
                f"GLPI API updated comment {comment_id} on KB article {article_id}"
            ),
        )

    def delete_kb_article_comment(
        self,
        article_id: GlpiId,
        comment_id: GlpiId,
        *,
        force: bool | None = None,
    ) -> None:
        """Delete one knowledge base article comment by identifier."""

        self._resource_delete(
            f"{KB_ARTICLE_ENDPOINT}/{article_id}/{KB_COMMENT_SUFFIX}/{comment_id}",
            failure_message=(
                f"Failed to delete comment {comment_id} on KB article {article_id}"
            ),
            log_message=(
                f"GLPI API deleted comment {comment_id} on KB article {article_id}"
            ),
            force=force,
            delete_model_cls=DeleteKBArticleComment,
        )


__all__ = ["KBArticleCommentMixin"]
