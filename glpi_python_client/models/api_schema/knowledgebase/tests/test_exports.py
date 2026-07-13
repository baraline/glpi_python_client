"""Assert the KB models are re-exported from the package roots."""

from __future__ import annotations

import glpi_python_client
import glpi_python_client.models as models

_KB_MODELS = (
    "GetKBArticle",
    "PostKBArticle",
    "PatchKBArticle",
    "DeleteKBArticle",
    "GetKBCategory",
    "PostKBCategory",
    "PatchKBCategory",
    "DeleteKBCategory",
    "GetKBArticleComment",
    "PostKBArticleComment",
    "PatchKBArticleComment",
    "DeleteKBArticleComment",
    "GetKBArticleRevision",
)


def test_kb_models_exported_from_top_level() -> None:
    """Every KB model is importable from ``glpi_python_client``."""

    for name in _KB_MODELS:
        assert hasattr(glpi_python_client, name), name
        assert name in glpi_python_client.__all__, name


def test_kb_models_exported_from_models_package() -> None:
    """Every KB model is importable from ``glpi_python_client.models``."""

    for name in _KB_MODELS:
        assert hasattr(models, name), name
        assert name in models.__all__, name
