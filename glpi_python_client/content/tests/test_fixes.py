"""One regression test per reader fix ported from easyvista-python-client 0.4.0.

That package's converter is this package's 0.6.0 converter (commit
``917f030``) plus fifteen fixes, each verified there on 2026-10-02 against
synthetic generators and against its own earlier test corpus. 0.6.1 ports
them, so that the two readers give the same Markdown. Each section below
pins one, numbered as in both packages' changelogs:

1. an image's alt keeps its escapes and entities;
2. ``~~~`` opening a line stays text, not a code fence;
3. a ``!`` ending a text right before a link does not make it an image;
4. an alt opening with ``^`` stays an image;
5. a second ``<`` after an escaped one does not open an autolink.

Every word is invented and every URL is under ``example.org``.
"""

from __future__ import annotations

import pytest
from bs4 import BeautifulSoup

from glpi_python_client.content.conversion import GlpiContentConverter
from glpi_python_client.content.tests.test_round_trip import assert_survives

read = GlpiContentConverter.from_transport
render = GlpiContentConverter.to_transport


def _alts(html: str) -> list[str]:
    """The alt of every image, as the HTML parser reads it."""

    soup = BeautifulSoup(html, "html.parser")
    return [str(image.get("alt")) for image in soup.find_all("img")]


# ---------------------------------------------------------------------------
# 1. An image's alt keeps its escapes and entities
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "alt",
    [
        pytest.param("a_b C:\\Temp *x* [y] &amp; `z`", id="syntax"),
        pytest.param("R&amp;amp;D &amp;copy;", id="literal-entities"),
        pytest.param("\\_ et \\*", id="backslashes"),
        pytest.param("x &lt; y", id="less-than"),
    ],
)
def test_1_an_image_alt_keeps_its_escapes_and_entities(alt: str) -> None:
    """markdown-it-py 3 leaves an escape or an entity in alt text as a
    ``text_special`` token, which mdformat rendered as nothing."""

    html = f'<p><img src="https://example.org/i.png" alt="{alt}"></p>'

    markdown = assert_survives(html)

    assert _alts(render(markdown)) == _alts(html)


# ---------------------------------------------------------------------------
# 2. '~~~' opening a line stays text
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "html",
    [
        pytest.param("<p>~~~</p>", id="paragraph"),
        pytest.param("<p>intro<br>~~~<br>suite</p>", id="after-a-break"),
        pytest.param("<ul><li>a<br>~~~~ b</li></ul>", id="in-a-list-item"),
        pytest.param("<blockquote><p>a<br>~~~ x</p></blockquote>", id="quoted"),
    ],
)
def test_2_a_tilde_run_opening_a_line_stays_text(html: str) -> None:
    """CommonMark reads ``~~~`` at a line start as a fence, which swallowed
    the rest of the body; mdformat has no guard for it."""

    markdown = assert_survives(html)

    assert "\\~~~" in markdown


def test_2_a_tilde_run_inside_a_line_is_not_escaped() -> None:
    """The control: only a run that opens a line is a fence, so only it is escaped."""

    assert assert_survives("<p>a ~~~ b</p>") == "a ~~~ b"


# ---------------------------------------------------------------------------
# 3. A trailing '!' before a link
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "html",
    [
        pytest.param(
            '<p>Attention!<a href="https://example.org/u">voir</a></p>', id="link"
        ),
        pytest.param(
            '<p>a!<a href="https://example.org/u">'
            '<img src="https://example.org/i.png" alt="x"></a></p>',
            id="linked-image",
        ),
        pytest.param(  # the control: "!<url>" was never an image
            '<p>a!<a href="https://example.org/u">https://example.org/u</a></p>',
            id="autolink",
        ),
    ],
)
def test_3_a_bang_before_a_link_does_not_make_an_image(html: str) -> None:
    """``!`` then ``[text](url)`` is an image in Markdown."""

    assert_survives(html)


def test_3_only_a_trailing_bang_is_escaped() -> None:
    """A ``!`` meets a ``[`` only at a text's end, so no other is escaped.

    A pin on the output, not a guard on the fix's narrow form. mdformat
    re-renders from the syntax tree and drops an escape that changes
    nothing, so escaping every ``!`` gives this same Markdown: a review on
    2026-10-02 found no body, among 3,414 from this suite's generators, on
    which the two forms differ. The narrow form was kept as the smaller
    change.
    """

    assert assert_survives("<p>Hi! there! ok</p>") == "Hi! there! ok"


# ---------------------------------------------------------------------------
# 4. An alt opening with '^'
# ---------------------------------------------------------------------------


def test_4_an_alt_opening_with_a_caret_stays_an_image() -> None:
    """cmark-gfm never opens an image on ``![^``, the footnote syntax."""

    html = '<p><img src="https://example.org/i.png" alt="^x"> fin</p>'

    markdown = assert_survives(html)

    assert markdown.startswith("![\\^x]")


def test_4_in_code_the_caret_is_not_escaped() -> None:
    """Inside code nothing is syntax, so a backslash there would show.

    This guards the fix's correction, not the fix.
    """

    markdown = read(
        '<p><code>x<img src="https://example.org/i.png" alt="^x"></code></p>'
    )

    assert "\\^" not in markdown


# ---------------------------------------------------------------------------
# 5. A second '<' does not open an autolink
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "html",
    [
        pytest.param("<p>&lt;&lt;a@b.c&gt; et &lt;&lt;b&gt; c</p>", id="address"),
        pytest.param("<p>&lt;&lt;https://example.org&gt;</p>", id="url"),
    ],
)
def test_5_a_second_less_than_stays_text(html: str) -> None:
    """mdformat's escape pattern ate the character after an escaped ``<``,
    so ``<<a@b.c>`` became ``\\<<a@b.c>``: an autolink."""

    markdown = assert_survives(html)

    assert "\\<\\<" in markdown
