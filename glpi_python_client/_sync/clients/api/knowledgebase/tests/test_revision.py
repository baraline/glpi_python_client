"""Recorder-based unit tests for the read-only ``KBArticleRevisionMixin``."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from glpi_python_client._sync._testing import FailingTransportRecorder
from glpi_python_client.testing.utils import FakeResponse


class _Recorder:
    def __init__(self, *, get_payload: Any = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self._get_payload = get_payload if get_payload is not None else []

    def install(self, client: Any) -> None:
        def _get(
            endpoint: str,
            params: dict[str, Any] | None = None,
            skip_entity: bool = False,
        ) -> FakeResponse:
            self.calls.append({"method": "GET", "endpoint": endpoint, "params": params})
            return FakeResponse(status_code=200, payload=self._get_payload)

        client._get_request = _get  # type: ignore[method-assign]


def test_list_kb_article_revisions_default_language(client: Any) -> None:
    rec = _Recorder(get_payload=[{"id": 11, "revision": 2}])
    rec.install(client)
    revisions = client.list_kb_article_revisions(5)
    assert revisions[0].revision == 2
    assert rec.calls[0]["endpoint"] == "Knowledgebase/Article/5/Revision"


def test_list_kb_article_revisions_with_language_uses_path_segment(
    client: Any,
) -> None:
    rec = _Recorder(get_payload=[{"id": 11, "revision": 2}])
    rec.install(client)
    client.list_kb_article_revisions(5, language="fr_FR")
    assert rec.calls[0]["endpoint"] == "Knowledgebase/Article/5/fr_FR/Revision"


def test_get_kb_article_revision_default_language(client: Any) -> None:
    rec = _Recorder(get_payload={"id": 11, "revision": 2})
    rec.install(client)
    revision = client.get_kb_article_revision(5, 2)
    assert revision.revision == 2
    assert rec.calls[0]["endpoint"] == "Knowledgebase/Article/5/Revision/2"


def test_get_kb_article_revision_with_language(client: Any) -> None:
    rec = _Recorder(get_payload={"id": 11, "revision": 2})
    rec.install(client)
    client.get_kb_article_revision(5, 2, language="fr_FR")
    assert rec.calls[0]["endpoint"] == "Knowledgebase/Article/5/fr_FR/Revision/2"


# ---------------------------------------------------------------------------
# Generic error handling (this mixin's share of the shared failure suites)
#
# The revision mixin is read-only, so it takes only the read share of the
# shared failure suites; there is no create, update, or delete call to take.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.list_kb_article_revisions(1),
        lambda c: c.get_kb_article_revision(1, 2),
    ],
)
def test_read_helpers_raise_on_failure(
    client: Any, call: Callable[[Any], Any]
) -> None:
    FailingTransportRecorder(404).install(client)
    with pytest.raises(ValueError):
        call(client)
