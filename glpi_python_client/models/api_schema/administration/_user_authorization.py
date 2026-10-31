"""Schema of one GLPI user authorization (``Profile_User`` row).

A user authorization says that a user holds a profile in an entity, and
whether that profile also applies to the entity's sub-entities. The GLPI v2
API has no route for these rows, so they are read and written through the
legacy v1 REST API, which names the columns ``users_id``, ``profiles_id`` and
``entities_id`` and encodes flags as ``0``/``1``.
"""

from __future__ import annotations

from pydantic import AliasChoices, Field

from glpi_python_client.models._base import GlpiModel


class UserAuthorization(GlpiModel):
    """One profile held by a user in an entity.

    Both the v1 column names (``users_id``, ``profiles_id``, ``entities_id``)
    and the Python field names are accepted on input; the ``0``/``1`` flags
    of the v1 API become booleans.

    Parameters
    ----------
    id : int
        Identifier of the authorization row.
    user_id : int
        Identifier of the user holding the profile.
    profile_id : int
        Identifier of the profile.
    entity_id : int
        Identifier of the entity the profile applies to.
    is_recursive : bool, optional
        Whether the profile also applies to the sub-entities of the entity.
    is_dynamic : bool, optional
        Whether the row was added by a directory rule rather than by hand.
    is_default_profile : bool, optional
        Whether this is the user's default profile.
    """

    id: int
    user_id: int = Field(validation_alias=AliasChoices("user_id", "users_id"))
    profile_id: int = Field(validation_alias=AliasChoices("profile_id", "profiles_id"))
    entity_id: int = Field(validation_alias=AliasChoices("entity_id", "entities_id"))
    is_recursive: bool = False
    is_dynamic: bool = False
    is_default_profile: bool = False
