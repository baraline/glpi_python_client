"""Recorder-based unit tests for the read-only ``KBArticleRevisionMixin``."""

from __future__ import annotations

from typing import Any

import pytest

from glpi_python_client import GlpiClient
from glpi_python_client.testing.utils import FakeResponse, make_client


class _Recorder:
    def __init__(self, *, get_payload: Any = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self._get_payload = get_payload if get_payload is not None else []

    def install(self, client: GlpiClient) -> None:
        def _get(
            endpoint: str,
            params: dict[str, Any] | None = None,
            skip_entity: bool = False,
        ) -> FakeResponse:
            self.calls.append({"method": "GET", "endpoint": endpoint, "params": params})
            return FakeResponse(status_code=200, payload=self._get_payload)

        client._get_request = _get  # type: ignore[method-assign]


@pytest.fixture
def client() -> GlpiClient:
    return make_client()


def test_list_kb_article_revisions_default_language(client: GlpiClient) -> None:
    rec = _Recorder(get_payload=[{"id": 11, "revision": 2}])
    rec.install(client)
    revisions = client.list_kb_article_revisions(5)
    assert revisions[0].revision == 2
    assert rec.calls[0]["endpoint"] == "Knowledgebase/Article/5/Revision"


def test_list_kb_article_revisions_with_language_uses_path_segment(
    client: GlpiClient,
) -> None:
    rec = _Recorder(get_payload=[{"id": 11, "revision": 2}])
    rec.install(client)
    client.list_kb_article_revisions(5, language="fr_FR")
    assert rec.calls[0]["endpoint"] == "Knowledgebase/Article/5/fr_FR/Revision"


def test_get_kb_article_revision_default_language(client: GlpiClient) -> None:
    rec = _Recorder(get_payload={"id": 11, "revision": 2})
    rec.install(client)
    revision = client.get_kb_article_revision(5, 2)
    assert revision.revision == 2
    assert rec.calls[0]["endpoint"] == "Knowledgebase/Article/5/Revision/2"


def test_get_kb_article_revision_with_language(client: GlpiClient) -> None:
    rec = _Recorder(get_payload={"id": 11, "revision": 2})
    rec.install(client)
    client.get_kb_article_revision(5, 2, language="fr_FR")
    assert rec.calls[0]["endpoint"] == "Knowledgebase/Article/5/fr_FR/Revision/2"
