"""Helpers for parsing GLPI document references in timeline HTML.

GLPI followups and solutions can embed attachments as links or images pointing
to ``document.send.php`` with a ``docid`` query parameter. These helpers keep
that transport-specific HTML parsing isolated from the model parsers.
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

from bs4 import BeautifulSoup


def _glpi_followup_attachment_document_ids(raw_content: object) -> tuple[str, ...]:
    """Return attachment document IDs referenced by followup HTML.

    GLPI timeline content may contain one or more ``a`` or ``img`` tags that
    point at ``document.send.php``. The parser scans both ``href`` and ``src``
    attributes, preserves the order in which document IDs appear, and removes
    duplicates so callers can safely request metadata once per attachment.
    """

    content = str(raw_content or "")
    if "document.send.php" not in content.casefold():
        return ()

    document_ids: list[str] = []
    seen_document_ids: set[str] = set()
    soup = BeautifulSoup(content, features="lxml")
    root = soup.body or soup

    for tag in root.find_all(["a", "img"]):
        if getattr(tag, "attrs", None) is None:
            continue
        for attribute_name in ("href", "src"):
            document_id = _glpi_document_id_from_url(tag.get(attribute_name))
            if document_id is None or document_id in seen_document_ids:
                continue
            seen_document_ids.add(document_id)
            document_ids.append(document_id)

    return tuple(document_ids)


def _strip_glpi_document_references(raw_content: object) -> str:
    """Return followup HTML with GLPI attachment references removed.

    Attachment images are removed completely because their source points at the
    GLPI document endpoint rather than meaningful inline content. Attachment
    links are replaced by their visible text when possible so the human-written
    part of the followup remains readable after document references are split
    into structured attachment IDs.
    """

    content = str(raw_content or "")
    if "document.send.php" not in content.casefold():
        return content

    soup = BeautifulSoup(content, features="lxml")
    root = soup.body or soup

    for tag in list(root.find_all(["a", "img"])):
        if tag.name is None or getattr(tag, "attrs", None) is None:
            continue
        target = tag.get("src") if tag.name == "img" else tag.get("href")
        if _glpi_document_id_from_url(target) is None:
            continue
        if tag.name == "img" or tag.find("img") is not None:
            tag.decompose()
            continue
        replacement = tag.get_text(" ", strip=True)
        if replacement:
            tag.replace_with(replacement)
        else:
            tag.decompose()

    normalized_root = soup.body or soup
    return "".join(str(child) for child in normalized_root.contents)


def _glpi_document_id_from_url(url: object) -> str | None:
    """Extract one GLPI document ID from a document download URL.

    Only GLPI ``document.send.php`` URLs are accepted. Missing URLs, non-string
    values, unrelated paths, missing ``docid`` parameters, and blank document IDs
    all return ``None`` so callers can probe arbitrary HTML attributes without
    handling parsing exceptions.
    """

    if not isinstance(url, str) or not url.strip():
        return None
    parsed = urlsplit(url)
    if not parsed.path.casefold().endswith("document.send.php"):
        return None
    document_ids = parse_qs(parsed.query).get("docid")
    if not document_ids:
        return None
    document_id = str(document_ids[0]).strip()
    return document_id or None
