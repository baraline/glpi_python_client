from __future__ import annotations

from glpi_python_client import GlpiFollowup, GlpiUser


def test_followup_model_copy_returns_updated_model() -> None:
    followup = GlpiFollowup(content="hello")

    updated = followup.model_copy(update={"followup_id": "42"})

    assert followup.followup_id is None
    assert updated.followup_id == "42"


def test_followup_payload_renders_markdown_to_html() -> None:
    followup = GlpiFollowup(content="Observed **again**")

    assert followup.to_api_payload()["content"] == (
        "<p>Observed <strong>again</strong></p>"
    )


def test_followup_payload_preserves_raw_user_ids() -> None:
    followup = GlpiFollowup(
        content="Observed **again**",
        author=GlpiUser(user_id="0012"),
        editor=GlpiUser(user_id=" user-7 "),
    )

    assert followup.to_api_payload()["user"] == {"id": "0012"}
    assert followup.to_api_payload()["user_editor"] == {"id": " user-7 "}
