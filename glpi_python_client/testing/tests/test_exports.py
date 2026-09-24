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


_ASSET_AND_CONTRACT_MODELS = (
    "GetComputer",
    "PostComputer",
    "PatchComputer",
    "DeleteComputer",
    "GetContractItem",
    "PostContractItem",
    "PatchContractItem",
    "DeleteContractItem",
    "GetContract",
    "PostContract",
    "PatchContract",
    "DeleteContract",
    "GetContractCost",
    "PostContractCost",
    "PatchContractCost",
    "DeleteContractCost",
    "GetContractType",
    "PostContractType",
    "PatchContractType",
    "DeleteContractType",
    "GlpiContractRenewalType",
)


def test_asset_and_contract_models_exported_from_top_level() -> None:
    """Every asset and contract model is importable from the package root."""

    for name in _ASSET_AND_CONTRACT_MODELS:
        assert hasattr(glpi_python_client, name), name
        assert name in glpi_python_client.__all__, name


def test_asset_and_contract_models_exported_from_models() -> None:
    """Every asset and contract model is importable from ``models``."""

    for name in _ASSET_AND_CONTRACT_MODELS:
        assert hasattr(models, name), name
        assert name in models.__all__, name
