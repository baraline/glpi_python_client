from __future__ import annotations

from glpi_python_client import GlpiUser


def test_user_payload_uses_email_as_username() -> None:
    user = GlpiUser(email="jane@example.test", firstname="Jane", realname="Doe")

    payload = user.to_api_payload()

    assert payload["username"] == "jane@example.test"
    assert payload["name"] == "jane@example.test"


def test_user_payload_preserves_raw_input_text() -> None:
    user = GlpiUser(
        user_id="0012",
        email=" jane@example.test ",
        firstname=" Jane ",
        realname=" Doe ",
    )

    payload = user.to_api_payload()

    assert payload["id"] == "0012"
    assert payload["username"] == " jane@example.test "
    assert payload["firstname"] == " Jane "
    assert payload["realname"] == " Doe "
    assert payload["name"] == " jane@example.test "
