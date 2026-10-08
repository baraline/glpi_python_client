"""The read's ``rewrite_link`` hook, and the document image helpers built beside it.

A caller that mirrors bodies between systems has to recognise an image a body
embeds -- one of GLPI's documents, served by ``front/document.send.php`` -- and
say what it becomes, without parsing the HTML or the Markdown itself. The hook
hands it each link and image as the reader meets it; ``document_image`` writes
the native form back. ``easyvista-python-client`` 0.4.3 carries the same hook,
with EasyVista's own embedded form.
"""

from __future__ import annotations

import threading

import pytest

from glpi_python_client import GlpiValidationError
from glpi_python_client.content import GlpiContentConverter, Link, RewriteLink
from glpi_python_client.content.tests.test_round_trip import (
    E_MAIL_SHAPES,
    EARLIER_REGRESSIONS,
    REALISTIC,
)

read = GlpiContentConverter.from_transport
render = GlpiContentConverter.to_transport
document_image = GlpiContentConverter.document_image
document_id_of = GlpiContentConverter.document_id_of

#: What every rendered link carries: GLPI's editor writes it on a link it makes.
NEW_WINDOW = ' target="_blank" rel="noopener noreferrer"'

#: The shape GLPI's editor writes for a pasted image (synthetic ids).
DOCUMENT = "/front/document.send.php?docid=7310&itemtype=Ticket&items_id=4211"
PASTED = (
    f'<p><a href="{DOCUMENT.replace("&", "&amp;")}" target="_blank">'
    f'<img src="{DOCUMENT.replace("&", "&amp;")}" alt="5f1a-upload-tag" width="480" />'
    "</a></p>"
)


def offered(html: str) -> list[Link]:
    """Read ``html`` with a callback that keeps everything, and return what it saw."""

    seen: list[Link] = []

    def keep(link: Link) -> None:
        seen.append(link)

    read(html, rewrite_link=keep)
    return seen


# ---------------------------------------------------------------------------
# What the callback is offered
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "html",
    REALISTIC
    + E_MAIL_SHAPES
    + [html for bodies in EARLIER_REGRESSIONS.values() for html in bodies],
)
def test_a_callback_answering_none_changes_nothing(html: str) -> None:
    assert read(html, rewrite_link=lambda link: None) == read(html)


def test_each_link_and_image_is_offered_once_an_image_before_its_link() -> None:
    html = (
        '<p><a href="https://x.example/p" title="t">'
        '<img src="https://x.example/i.png" alt=" un  logo " title="it"></a>'
        ' et <a href="https://y.example">le &amp; site</a></p>'
    )

    assert offered(html) == [
        Link(
            "https://x.example/i.png",
            "un logo",
            "it",
            image=True,
            enclosing_href="https://x.example/p",
        ),
        Link("https://x.example/p", "", "t"),
        Link("https://y.example", "le & site"),
    ]


def test_the_editors_pasted_image_is_offered_as_one_document_twice() -> None:
    assert offered(PASTED) == [
        Link(
            DOCUMENT,
            "5f1a-upload-tag",
            image=True,
            document_id=7310,
            enclosing_href=DOCUMENT,
        ),
        Link(DOCUMENT, "", document_id=7310),
    ]


@pytest.mark.parametrize(
    "url",
    [
        "/front/document.send.php?docid=4820",
        "front/document.send.php?docid=4820",
        "/glpi/front/document.send.php?docid=4820",
        "https://glpi.example.org/front/document.send.php?itemtype=Ticket&docid=4820",
        "https://glpi.example.org/glpi/front/document.send.php?items_id=1&docid=4820&x=y",
    ],
)
def test_a_document_url_names_its_document_wherever_glpi_is_served(url: str) -> None:
    assert document_id_of(url) == 4820


@pytest.mark.parametrize(
    "url",
    [
        "",
        "https://x.example/i.png",
        "/front/document.send.php",
        "/front/document.send.php?docid=",
        "/front/document.send.php?docid=0",
        "/front/document.send.php?docid=12a",
        "/front/document.send.php?docid=٣",
        "/front/document.send.php?docid=1&docid=2",
        "/front/xdocument.send.php?docid=4820",
        "/xfront/document.send.php?docid=4820",
        "/front/document.send.php/x?docid=4820",
        "/front/ticket.form.php?docid=4820",
        "http://[::1/front/document.send.php?docid=4820",
    ],
)
def test_any_other_url_names_no_document(url: str) -> None:
    assert document_id_of(url) is None


def test_an_image_or_link_elsewhere_carries_no_document_id() -> None:
    links = offered(
        '<p><a href="https://x.example">x</a><img src="https://x.example/i.png"></p>'
    )
    assert [link.document_id for link in links] == [None, None]


@pytest.mark.parametrize(
    "html",
    [
        f'<pre><a href="{DOCUMENT}">x</a><img src="{DOCUMENT}"></pre>',
        '<p><code><a href="https://x.example">x</a></code></p>',
    ],
)
def test_nothing_inside_code_is_offered(html: str) -> None:
    # Code is displayed as written: what looks like a link there is not one.
    assert offered(html) == []


def test_nothing_is_offered_for_markdown_passed_through() -> None:
    assert offered("[x](https://x.example)") == []
    read("[x](https://x.example)", plain_text_is_markdown=True, rewrite_link=_fail)


def _fail(link: Link) -> None:
    raise AssertionError(f"offered {link!r}")


# ---------------------------------------------------------------------------
# What the answer writes
# ---------------------------------------------------------------------------


def test_a_link_answered_with_a_link_is_written_with_its_href_and_title() -> None:
    markdown = read(
        '<p><a href="https://a.example">le <b>site</b></a></p>',
        rewrite_link=lambda link: Link("https://b.example", title="T"),
    )

    assert markdown == '[le **site**](https://b.example "T")'


def test_a_link_answered_with_no_href_is_dropped_and_its_content_kept() -> None:
    markdown = read(
        '<p>voir <a href="https://a.example">le <b>site</b></a> ici</p>',
        rewrite_link=lambda link: Link(""),
    )

    assert markdown == "voir le **site** ici"


def test_an_image_answered_with_a_link_is_written_with_its_src_alt_and_title() -> None:
    markdown = read(
        '<p><img src="https://a.example/i.png" alt="a"></p>',
        rewrite_link=lambda link: Link("https://b.example/j.png", "b", "t", image=True),
    )

    assert markdown == '![b](https://b.example/j.png "t")'


def test_an_image_answered_with_no_href_is_written_as_its_text() -> None:
    markdown = read(
        '<p>voir <img src="https://a.example/i.png" alt="a"> ici</p>',
        rewrite_link=lambda link: Link("", "capture_1.png", image=True),
    )

    assert markdown == "voir capture_1.png ici"


@pytest.mark.parametrize(
    "html",
    ['<p><a href="https://a.example">x</a></p>', '<p><img src="i.png" alt="x"></p>'],
)
def test_a_string_answer_is_literal_text(html: str) -> None:
    # Escaped as the reader escapes a text node, so it displays as it is and
    # cannot become markup -- whatever the callback hands back.
    text = "**pas gras** [x](javascript:alert(1)) <b>"

    markdown = read(html, rewrite_link=lambda link: text)

    assert render(markdown) == "<p>**pas gras** [x](javascript:alert(1)) &lt;b&gt;</p>"
    assert read(render(markdown)) == markdown


def test_the_editor_wrap_collapses_to_the_image_alone() -> None:
    # The image is rewritten, then the link around it -- to the same document
    # -- dropped, its content, the new image, kept.
    def rewrite(link: Link) -> Link | None:
        if link.document_id is None:
            return None
        if link.image:
            return Link(f"https://files.example/{link.document_id}", image=True)
        return Link("")

    assert read(PASTED, rewrite_link=rewrite) == "![](https://files.example/7310)"


# ---------------------------------------------------------------------------
# What a callback raises, and where its state lives
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "error", [ValueError("bad id"), RecursionError(), KeyError("k")]
)
def test_what_the_callback_raises_reaches_the_caller_unchanged(
    error: Exception,
) -> None:
    # A ValueError above all: the reader answers markdownify's by reading the
    # body as its text, and a callback's must not pass for one and quietly
    # cost the body its formatting.
    def fail(link: Link) -> None:
        raise error

    with pytest.raises(type(error)) as caught:
        read('<p><b>gras</b> <a href="https://x.example">x</a></p>', rewrite_link=fail)

    assert caught.value is error


def test_an_answer_of_another_type_is_a_type_error() -> None:
    with pytest.raises(TypeError, match="rewrite_link returned int"):
        read('<p><a href="https://x.example">x</a></p>', rewrite_link=lambda link: 1)  # type: ignore[arg-type,return-value]


def test_the_callback_is_gone_once_the_read_ends_however_it_ends() -> None:
    with pytest.raises(ValueError):
        read(
            '<p><a href="https://x.example">x</a></p>', rewrite_link=_raise_value_error
        )

    assert read('<p><a href="https://x.example">x</a></p>') == "[x](https://x.example)"


def _raise_value_error(link: Link) -> None:
    raise ValueError(link.href)


def test_a_read_inside_a_callback_has_its_own_callback() -> None:
    # And the outer read gets its own back: it is asked about its second link
    # after the nested read has ended.
    calls: list[str] = []

    def outer(link: Link) -> None:
        calls.append(f"outer {link.href}")
        read(
            f'<p><a href="{link.href}/inner">i</a></p>',
            rewrite_link=lambda seen: calls.append(f"inner {seen.href}"),  # type: ignore[func-returns-value]
        )

    read(
        '<p><a href="https://one.example">1</a> <a href="https://two.example">2</a></p>',
        rewrite_link=outer,
    )

    assert calls == [
        "outer https://one.example",
        "inner https://one.example/inner",
        "outer https://two.example",
        "inner https://two.example/inner",
    ]


def test_each_thread_reads_with_its_own_callback() -> None:
    # Both reads are inside their callbacks at once: a callback held on the
    # shared converter would be the other thread's by the time it is called.
    barrier = threading.Barrier(2, timeout=10)
    seen: dict[str, list[str]] = {"a": [], "b": []}
    failures: list[BaseException] = []

    def reader(name: str) -> None:
        def note(link: Link) -> None:
            barrier.wait()
            seen[name].append(link.href)

        try:
            read(f'<p><a href="https://{name}.example/1">1</a></p>', rewrite_link=note)
        except BaseException as exc:
            failures.append(exc)

    threads = [threading.Thread(target=reader, args=(name,)) for name in ("a", "b")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert failures == []
    assert seen == {"a": ["https://a.example/1"], "b": ["https://b.example/1"]}


# ---------------------------------------------------------------------------
# Document images
# ---------------------------------------------------------------------------


def test_document_image_renders_as_the_editor_writes_a_pasted_image() -> None:
    url = DOCUMENT.replace("&", "&amp;")

    assert render(
        document_image(7310, alt="capture.png", itemtype="Ticket", items_id=4211)
    ) == (
        f'<p><a href="{url}"{NEW_WINDOW}><img src="{url}" alt="capture.png" /></a></p>'
    )


def test_document_image_without_an_item_names_the_document_alone() -> None:
    url = "/front/document.send.php?docid=7310"

    assert render(document_image(7310)) == (
        f'<p><a href="{url}"{NEW_WINDOW}><img src="{url}" alt="" /></a></p>'
    )


@pytest.mark.parametrize(
    "alt", ["", "capture.png", "a_b*c [d] `e` <f> !", "  deux   mots  "]
)
def test_document_image_is_what_the_reader_writes_for_the_native_image(
    alt: str,
) -> None:
    markdown = document_image(7310, alt=alt, itemtype="Ticket", items_id=4211)

    assert read(render(markdown)) == markdown
    image, link = offered(render(markdown))
    assert (image.document_id, image.text, link.document_id) == (
        7310,
        " ".join(alt.split()),
        7310,
    )


@pytest.mark.parametrize(
    ("document_id", "itemtype", "items_id", "message"),
    [
        (0, None, None, "not a GLPI document id"),
        (-1, None, None, "not a GLPI document id"),
        (True, None, None, "not a GLPI document id"),
        ("7310", None, None, "not a GLPI document id"),
        (7310, "Ticket", None, "give both or neither"),
        (7310, None, 4211, "give both or neither"),
        (7310, "Ticket&x=1", 4211, "not a GLPI item type"),
        (7310, "", 4211, "not a GLPI item type"),
        (7310, "Ticket", 0, "not a GLPI item id"),
        (7310, "Ticket", "4211", "not a GLPI item id"),
    ],
)
def test_document_image_refuses_what_is_not_a_document(
    document_id: object, itemtype: str | None, items_id: object, message: str
) -> None:
    with pytest.raises(GlpiValidationError, match=message):
        document_image(document_id, itemtype=itemtype, items_id=items_id)  # type: ignore[arg-type]


def test_document_image_is_not_rewritten_by_a_read_in_progress() -> None:
    written: list[str] = []

    def rewrite(link: Link) -> None:
        written.append(document_image(7310, alt="x"))

    read('<p><a href="https://x.example">x</a></p>', rewrite_link=rewrite)

    url = "/front/document.send.php?docid=7310"
    assert written == [f"[![x]({url})]({url})"]


def test_rewrite_link_is_a_public_type() -> None:
    callback: RewriteLink = lambda link: None  # noqa: E731
    assert read("<p>x</p>", rewrite_link=callback) == "x"
