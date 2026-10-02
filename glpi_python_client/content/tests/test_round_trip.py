"""Realistic content survives the trip between GLPI's HTML and Markdown, both ways.

The contract, checked with an HTML parser (:mod:`.display`) rather than by eye:

* **HTML first.** ``to_transport(from_transport(html))`` displays what
  ``html`` displays -- the same blocks, words, and bold/italic/code/link on
  each character -- and the Markdown is a fixed point: reading back what it
  renders gives the same Markdown.
* **Markdown first.** Markdown a caller writes renders to HTML that reads
  back as Markdown displaying the same, and that Markdown is a fixed point.

The bodies are the shapes GLPI's editor and the mail collector store, and
the Markdown is what an integrator writes. From easyvista-python-client
0.4.0, whose converter is this one: a body shaped like an e-mail
notification template, two plain-text cases (a CR LF, an entity), a pin on
what ``plain_text_is_markdown=True`` reads as HTML, and the HTML of that
package's earlier regression bodies. The long-body tests are growth tests
in :mod:`.test_cost`.

Adversarial input -- syntax characters packed into every position -- is
:mod:`.test_properties`' subject; this module holds the converter to
realistic content. Every URL is under ``example.org``.
"""

from __future__ import annotations

from typing import cast

import pytest

from glpi_python_client.content.conversion import GlpiContentConverter
from glpi_python_client.content.tests.display import displayed, text_words

read = GlpiContentConverter.from_transport
render = GlpiContentConverter.to_transport


def assert_survives(html: str) -> str:
    """Assert the HTML-first property for one body, and return its Markdown."""

    markdown = read(html)
    rendered = render(markdown)

    assert displayed(rendered) == displayed(html), (
        f"the Markdown does not display what the HTML did\n"
        f"  html:     {html!r}\n  markdown: {markdown!r}\n  rendered: {rendered!r}"
    )
    assert read(rendered) == markdown, (
        f"the Markdown is not a fixed point\n  markdown: {markdown!r}\n"
        f"  again:    {read(rendered)!r}"
    )
    return markdown


# ---------------------------------------------------------------------------
# HTML first
# ---------------------------------------------------------------------------

#: Ticket bodies shaped the way GLPI's editor and mail collector store them.
REALISTIC = [
    "<p>Bonjour,</p><p>Le PC du poste 12 ne démarre plus depuis ce matin.</p>",
    "<p>Bonjour,<br>Le PC ne démarre plus.<br>Cordialement,<br>Jean</p>",
    "<p>Merci de <strong>redémarrer</strong> le serveur <em>avant</em> 18h.</p>",
    "<p>Étapes :</p><ul><li>ouvrir la session</li><li>lancer Outlook</li></ul>",
    "<table><thead><tr><th>Poste</th><th>IP</th></tr></thead>"
    "<tbody><tr><td>PC12</td><td>10.0.0.12</td></tr></tbody></table>",
    "<h2>Contexte</h2><p>Migration du serveur.</p>",
    '<p>Voir <a href="https://example.org/doc">https://example.org/doc</a></p>',
    '<p>Voir <a title="doc" href="https://example.org/doc">la doc</a></p>',
    '<p><a href="https://example.org/wiki/Test_(informatique)">wiki</a></p>',
    "<p>prix 5*3 et note * importante</p>",
    "<p>appuyer sur &lt;Entrée&gt; puis valider</p>",
    "<p>Service R&amp;D, bâtiment A &amp; B</p>",
    "<p>Montant&nbsp;: 12&nbsp;000&nbsp;€</p>",
    # The display oracle cannot see underline. Since fix 11 (test_fixes.py)
    # the <u> is kept as raw HTML in the Markdown, where 0.6.0
    # dropped it; this row checks the words and the fixed point.
    '<p><span style="color: #e03e2d;">URGENT</span> <u>à traiter</u></p>',
    '<p>Cordialement</p><p><img src="https://example.org/logo.png" alt="Logo"></p>',
    "<p>Bonjour</p><blockquote><p>Message d'origine</p></blockquote>",
    '<pre>Traceback (most recent call last):\n  File "x.py", line 1\nError</pre>',
    "<p>Lancer <code>ipconfig /all</code> puis envoyer.</p>",
    "<p>Fichier mon_fichier_final.docx et __init__</p>",
    "<p># pas un titre</p><p>- pas une liste</p>",
    '<p>Contact <a href="mailto:support@example.org">support@example.org</a></p>',
    "<div>Bonjour,</div><div><br></div><div>Le serveur est down.</div>",
    "<p>* point un<br>* point deux</p>",
    "<p>[INFO] tâche [1] terminée</p>",
    "<p>[1]: https://example.org/note</p>",
    r"<p>Chemin C:\Users\jdupont\Desktop</p>",
    r"<p>Accès au partage \\serveur\compta\2026 refusé</p>",
    "<p>Merci 👍</p>",
    "<p>Titre<br>=====</p>",
    "<p>---</p><p>signature</p>",
    "<p>1) un<br>2) deux</p>",
    "<ul><li><p>point un</p><p>suite du point</p></li><li>point deux</li></ul>",
    "<blockquote><ul><li>a</li><li>b</li></ul></blockquote>",
    "<p>Nom : ______ Prénom : ______</p>",
    "<p>a | b | c</p>",
    "<p>&gt; pas une citation</p>",
    "<p>Cordialement,<br>Jean Dupont<br>--<br>Service IT</p>",
    "<p>Merci<br>-----------<br>Jean Dupont</p>",
    "<p>Le 30/09, Jean a écrit :<br>&gt; merci<br>&gt; cordialement</p>",
    "<ul><li>Réseau<ul><li>switch 3</li><li>borne wifi</li></ul></li></ul>",
    "<ol><li>Arrêter</li><li>Sauvegarder<ol><li>la base</li><li>les fichiers</li>"
    "</ol></li><li>Redémarrer</li></ol>",
    '<ol start="3"><li>trois</li><li>quatre</li></ol>',
    "<ul><li>Réseau<ul><li>switch 3</li></ul>à vérifier</li></ul>",
    "<p><b>Important</b> : voir <i>ci-dessous</i></p>",
    "<table><tr><th>Commande</th></tr><tr><td>ps aux | grep java</td></tr></table>",
    "<table><tr><th>Commande</th></tr><tr><td><code>ps aux | grep java</code></td></tr>"
    "</table>",
    "<pre>ligne\n```\nfin</pre>",
    "<p>Suite à la mise à jour, <strong>3 postes</strong> ne se connectent plus :"
    "</p><ul><li>PC12 (salle 3)</li><li>PC14 &ndash; <em>poste d'accueil</em></li>"
    '</ul><p>Voir <a href="https://example.org/kb/42">https://example.org/kb/42</a>'
    ' et le <a href="https://example.org/kb/43" title="KB 43">KB 43</a>.</p>',
]


@pytest.mark.parametrize("html", REALISTIC)
def test_a_realistic_body_displays_the_same_after_the_round_trip(html: str) -> None:
    assert_survives(html)


#: What e-mail clients add: Outlook's blank paragraphs and line breaks made of
#: a non-breaking space, a blank line inside a paragraph, a label in bold
#: right before a figure, and Gmail's quoted reply.
E_MAIL_SHAPES = [
    pytest.param(
        '<p class="MsoNormal">Bonjour,<o:p></o:p></p>'
        '<p class="MsoNormal"><o:p>&nbsp;</o:p></p>'
        '<p class="MsoNormal">Le serveur répond.<o:p></o:p></p>',
        id="outlook-blank-paragraph",
    ),
    pytest.param("<p>Bonjour<br>&nbsp;<br>Texte</p>", id="nbsp-blank-line"),
    pytest.param("<p>Bonjour,<br><br>Texte</p>", id="blank-line-in-a-paragraph"),
    pytest.param("<p><b>Total:</b>12 postes</p>", id="bold-label-before-a-figure"),
    pytest.param(
        '<div dir="ltr">Merci</div><div class="gmail_quote"><div>Le lun. a écrit :'
        "</div><blockquote>Le serveur est down.</blockquote></div>",
        id="gmail-quote",
    ),
    pytest.param("<p>Ligne<br></p><p>Suite</p>", id="break-ending-a-paragraph"),
    pytest.param(
        "<p>Source wrapped\nmid-sentence\nby Outlook.</p>", id="newlines-in-source"
    ),
]


@pytest.mark.parametrize("html", E_MAIL_SHAPES)
def test_an_e_mail_shape_displays_the_same_after_the_round_trip(html: str) -> None:
    assert_survives(html)


# ---------------------------------------------------------------------------
# Bodies from easyvista-python-client's earlier tests
# ---------------------------------------------------------------------------
#
# The HTML of the regression bodies that package's tests held before its
# 0.4.0, when its converter was python-markdown's dialect: a body does not
# depend on which converter reads it, and the fixes this converter carries
# were measured against these. Only the HTML is kept. The Markdown those tests
# expected was python-markdown's, so each body is held to the HTML-first
# property instead -- the same display, and a fixed point. Grouped by the
# test each came from; every body is synthetic, and every URL is under
# example.org. The long bodies dense with syntax are growth tests in
# test_cost.py.

#: The earlier tests' bodies, by the test they came from.
EARLIER_REGRESSIONS: dict[str, list[str]] = {
    "obsolete": [
        '<font color="red">URGENT</font> serveur HS',
        "<strike>ancien</strike> nouveau",
        "<big>gros</big> texte",
        "<tt>code</tt> texte",
        "<nobr>sans coupure</nobr>",
    ],
    "line-break": [
        "<p>a<br> b<br>  c</p>",
        "<p>a <br>b</p>",
        "<p><strong>a<br></strong>b</p>",
    ],
    "pre": [
        "<ul><li>item<pre>#4521 code</pre></li></ul>",
        "<blockquote><pre>#4521 C:\\Temp\n  indenté</pre></blockquote>",
    ],
    "image": [
        '<h2>Titre <img src="https://example.org/i.png" alt="logo"></h2>',
        "<table><tr><th>a</th></tr><tr><td>"
        '<img src="https://example.org/i.png" alt="x"></td></tr></table>',
    ],
    "block-in-item": [
        "<ul><li>Réseau<ul><li>switch 3</li></ul><blockquote>cité</blockquote></li>"
        "</ul>",
        "<ul><li>Réponse :<blockquote>cité</blockquote></li></ul>",
        "<ul><li><blockquote>cité<br>suite</blockquote></li></ul>",
        "<ul><li><ul><li>un</li><li>deux</li></ul></li></ul>",
        "<ul><li><ul><li>un<ul><li>a</li></ul></li></ul></li></ul>",
        "<ul><li><ul><li><ul><li>un</li><li>deux</li></ul></li></ul></li><li>trois"
        "</li></ul>",
    ],
    "code-after-list": [
        "<ul><li>item<ul><li>sous-item</li></ul><pre>#4521 code</pre></li></ul>",
        "<blockquote><ul><li>item</li></ul><pre>#4521 code</pre></blockquote>",
        "<ul><li>item<ul><li>sous-item</li></ul><div><style>p{margin:0}</style>"
        "</div><pre>#4521 code</pre></li></ul>",
    ],
    "literal-syntax": [
        "<p>D:\\logs\\.cache et \\\\srv\\share\\[archive] et HKLM\\SOFTWARE\\#1</p>",
        "<p>fin de ligne \\<br>suite</p>",
        "<h2>Chemin C:\\</h2>",
        "<p>_______</p>",
        "<p>Code : _______ fin</p>",
        "<p>a*b*c et 5*3 <strong>gras</strong></p>",
        "<p><strong>x</strong>* suite</p>",
        "<p>+ un<br>+ deux</p>",
        "<p>- pas une liste</p>",
        "<p>Bonjour<br>#4521 doublon</p>",
        "<p>***</p>",
        "<ul><li>--</li></ul>",
        "<ul><li>___</li></ul>",
        "<ul><li><ul><li>-</li></ul></li></ul>",
        "<ol><li><ul><li>--</li></ul></li></ol>",
        "<ul><li><p>--</p><p>suite</p></li></ul>",
        "<h1>C#</h1>",
        "<h2>Titre ##</h2>",
        "<p>```<br>code<br>```</p>",
        "<p>~~~<br>code<br>~~~</p>",
        "<p>a | b<br>--- | ---</p>",
        "<p>[x](https://example.org/y) et ![x](https://example.org/y.png)</p>",
        '<p><a href="https://example.org/u">rapport [final].pdf</a></p>',
        '<p><a href="https://example.org/u">a]b</a></p>',
        '<p><a href="https://example.org/u">voir [x](y)</a></p>',
        '<p>[a <a href="https://example.org/u">[b</a> ](https://example.org/x)</p>',
        '<p><img src="https://example.org/c.png" alt="capture [1].png"></p>',
        '<p><img src="https://example.org/c.png" alt="a]b"></p>',
        "<p>if x&lt;y then z&gt;0</p>",
        "<p>&lt;https://example.org/x&gt; et &lt;support@example.org&gt;</p>",
        '<p>&lt;3<img src="https://example.org/i.png" alt="a b">@c&gt;</p>',
        '<p><a href="https://example.org/u">&lt;&lt;a@c&gt;</a></p>',
        '<p>&lt;3<a href="https://example.org">https://example.org</a>@c&gt;</p>',
        '<p>&lt;a <a href="https://example.org/T_(x)">wiki</a>b@c&gt;</p>',
        "<p>&lt;!-- note --&gt;</p>",
        "<p>&amp;amp; &amp;lt; &amp;#65; &amp;#4521 &amp;copy; &amp;copy</p>",
        "<p>a`b`c et <code>x</code> puis `</p>",
        "<p><code>x</code>`y</p>",
        "<p>`<code>x</code> y</p>",
        "<table><tr><th>a</th><th>b</th></tr><tr><td>x`y</td><td>`z</td></tr></table>",
    ],
    "nested-list": [
        "<ul><li>Réseau<ul><li>switch 3</li><li>borne wifi</li></ul></li>"
        "<li>Imprimante</li></ul>",
        "<ol><li>Arreter</li><li>Sauvegarder<ol><li>la base</li><li>les fichiers"
        "</li></ol></li><li>Redemarrer</li></ol>",
        "<ol><li>un<ul><li>a</li></ul></li><li>deux</li></ol>",
        "<ul><li>a<ul><li>b<ul><li>c<ul><li>d</li></ul></li></ul></li></ul></li></ul>",
        '<p>intro</p><ol start="3"><li>trois</li><li>quatre</li></ol>',
        "<ul><li>5*3<ul><li>2*4</li></ul></li></ul>",
    ],
    "prose": [
        "<p>Porte-monnaie - un tiret - et -- deux</p>",
        "<p>5 * 3 = 15 et prix 5*3 et note * importante</p>",
        "<p>si a &lt; b et x &lt;= y alors 2 &lt; 3</p>",
        "<p>2 + 2 = 4, +33 6 12 34 56 78, 1) un, 3.14</p>",
        "<p>Pourquoi ? Parce que ! 100 % a/b a=b ~5 minutes</p>",
        "<p>l`imprimante et la variable user_id et _temp</p>",
        "<p>ps aux | grep java</p>",
    ],
    "realistic": [
        "<p>&lt;https://example.org/x&gt;</p>",
        "<p>m<sup>2</sup></p>",
        "<p>&lt;support@example.org&gt;</p>",
        "<p>~~pas barré~~</p>",
        "<p>calcul 5 * 3 * 2 = 30</p>",
        "<p>voir \\\\srv\\partage\\__archive__\\2026</p>",
        "<p>Dossier C:\\_temp\\logs</p>",
        "<p>voir la note [1]</p><p>[1]: https://example.org/note</p>",
        '<p><font color="red">rouge</font> <span style="font-size:14px">texte</span>'
        "</p>",
        "<p>module __init__ et _x_</p>",
        "<p>1) un<br>2) deux</p><pre>ligne 1\n    ligne indentée</pre>",
    ],
    "own-rule": [
        '<p><a name="_MailEndCompose">Bonjour</a> Jean</p>',
        '<p><a href="https://example.org/u"></a>texte</p>',
        "<p><strong></strong>texte</p>",
        '<p><a href="https://example.org/u">un<br>deux</a></p>',
        "<table><tr><th><h3>titre</h3></th></tr><tr><td>x</td></tr></table>",
        "<h2><blockquote>cité</blockquote></h2>",
        '<p><img src="https://example.org/i.png" alt="ligne 1\n\n  ligne 2"></p>',
        "<ul><li><script>x()</script><pre>code</pre></li></ul>",
        "<ul><li><!-- note --><pre>code</pre></li></ul>",
        "<ul><li><ul></ul><pre>code</pre></li></ul>",
        '<ul><li><img src="https://example.org/i.png" alt="i"><pre>code</pre></li>'
        "</ul>",
    ],
    "struck": [
        "<p><s>ancien</s> nouveau</p>",
        "<p><del>ancien</del> nouveau</p>",
        "<p><strike>ancien</strike> nouveau</p>",
    ],
    "hidden": [
        "<style>p.MsoNormal{margin:0cm;font-size:11pt}</style><p>Bonjour</p>",
        "<html><head><title>RE: Imprimante</title><style>"
        "<!-- p.MsoNormal {margin:0cm;} --></style></head><body><p>Bonjour</p>"
        "<script>track()</script></body></html>",
    ],
    "misreading": [
        "<p># pas un titre</p>",
        "<p>#4521 est un doublon</p>",
        "<p>2026. Une annee</p>",
    ],
    "upper-case": [
        "<P>Bonjour</P>",
        "<BR>Bonjour",
        "<DIV><B>Bonjour</B></DIV>",
    ],
}


@pytest.mark.parametrize(
    "html",
    [
        pytest.param(html, id=f"{group}-{index}")
        for group, bodies in EARLIER_REGRESSIONS.items()
        for index, html in enumerate(bodies)
    ],
)
def test_an_earlier_regression_body_survives(html: str) -> None:
    assert_survives(html)


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        pytest.param(
            "<p>Voir fichier_de_test_v2.xlsx et mon_fichier_final.docx</p>",
            "Voir fichier_de_test_v2.xlsx et mon_fichier_final.docx",
            id="file-names",
        ),
        pytest.param(
            r"<p>Chemin C:\Temp\logs et C:\Users\Admin\Documents</p>",
            r"Chemin C:\Temp\logs et C:\Users\Admin\Documents",
            id="windows-paths",
        ),
        pytest.param(
            "<p>Le ticket # 3 et le #4521 sont liés, C# aussi</p>",
            "Le ticket # 3 et le #4521 sont liés, C# aussi",
            id="hashes",
        ),
        pytest.param(
            "<p>Service R&amp;D, bâtiment A &amp; B</p>",
            "Service R&D, bâtiment A & B",
            id="ampersands",
        ),
        pytest.param(
            "<p>[INFO] tâche [1] terminée (voir note)</p>",
            "[INFO] tâche [1] terminée (voir note)",
            id="brackets",
        ),
        pytest.param(
            "<p>Voir https://example.org/doc?a=1&amp;b=2 ou support@example.org</p>",
            "Voir https://example.org/doc?a=1&b=2 ou support@example.org",
            id="bare-url-and-address",
        ),
        pytest.param(
            "<p>Fichier mon_fichier_final.docx et __init__</p>",
            r"Fichier mon_fichier_final.docx et \_\_init\_\_",
            id="dunder",
        ),
    ],
)
def test_ordinary_prose_reads_back_as_typed(html: str, expected: str) -> None:
    """Prose carries no escape, and literal syntax is escaped only to stay text."""

    assert assert_survives(html) == expected


def test_a_table_nested_in_a_cell_keeps_its_text() -> None:
    """A table inside a table keeps every word.

    E-mail signatures and notification templates are often laid out so.
    """

    html = (
        "<table><tr><th>Signature</th></tr><tr><td><table><tr><td>Jean Dupont</td>"
        "<td>Service IT</td></tr></table></td></tr></table>"
    )

    markdown = read(html)

    assert "Jean Dupont" in render(markdown)
    assert "Service IT" in render(markdown)


@pytest.mark.parametrize(
    "html",
    [
        pytest.param(
            "<style>p.MsoNormal{margin:0cm}</style><p>Bonjour</p>", id="style"
        ),
        pytest.param("<p>Bonjour</p><script>track()</script>", id="script"),
        pytest.param(
            "<html><head><title>RE: Imprimante</title></head>"
            "<body><p>Bonjour</p></body></html>",
            id="title",
        ),
    ],
)
def test_what_a_browser_does_not_display_is_dropped(html: str) -> None:
    assert read(html) == "Bonjour"


def test_a_fence_keeps_its_language() -> None:
    markdown = "```powershell\nGet-Service\n```"

    assert read(render(markdown)) == markdown


# ---------------------------------------------------------------------------
# A notification template: a layout table around a table of label/value cells
# ---------------------------------------------------------------------------
#
# From easyvista-python-client 0.4.0. E-mail templates are commonly laid out
# as an outer one-cell table around an inner one-row table: each label in
# bold over its value, spacer cells between them, and here one label in a
# cell of its own beside its value's cell. That shape exercises the
# flattening of a table nested in a cell, fix 9 of test_fixes.py (bold that
# ends on punctuation at a flattened cell's edge still closes -- 0.6.0 lost
# the fixed point there) and <br> in a cell, all at once. Every word below
# is invented.

_LABELS = ["Zorvane", "Plimet", "Quastor", "Brindel"]
_VALUES = ["trelm 4471", "oskar-vint", "maludi pref", "kobra 12/09"]


def _notification_template() -> str:
    cells = []
    for label, value in zip(_LABELS, _VALUES, strict=True):
        cells.append("<td></td>")  # a spacer cell
        cells.append(
            f"<td><span><br><strong>{label}</strong></span><br><br>{value}<br><br></td>"
        )
    cells.append("<td><strong>Velusk :</strong></td><td>sanquo</td>")
    inner = "<table><tr>" + "".join(cells) + "</tr></table>"
    footer = (
        '<a href="https://example.org/suivi?ref=PX-7">Grovak le suivi</a> '
        '<img src="https://example.org/marque.png" alt="Trelune">'
    )
    return f"<table><tr><td>{inner}<br>{footer}</td></tr></table>"


def test_a_notification_template_keeps_every_word_in_order() -> None:
    """Every word, in order, each label still bold and the link still a link.

    The layout does not survive: GFM has no nested table, so the inner row
    becomes one line of text in the outer cell, and a GFM table always has a
    header row, so the outer table gains an empty one. Both are limits of
    the format. Apart from that header row, the display is the same.
    """

    html = _notification_template()

    markdown = read(html)
    rendered = render(markdown)

    assert text_words(rendered) == text_words(html)
    name, rows = cast(tuple[str, tuple[object, ...]], displayed(html)[0])
    empty_header = ((True, ()),)  # the header row GFM requires: one empty cell
    assert displayed(rendered) == ((name, (empty_header, *rows)),)
    for label in [*_LABELS, "Velusk :"]:
        assert f"**{label}**" in markdown
    assert "](https://example.org/suivi?ref=PX-7)" in markdown
    assert "![Trelune](https://example.org/marque.png)" in markdown
    assert "glpi-cell" not in markdown and "data-glpi-" not in markdown
    assert read(rendered) == markdown


# ---------------------------------------------------------------------------
# Plain text and the write path
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "__init__ et _x_",
        "# pas un titre",
        "* point un\n* point deux",
        r"\\serveur\partage",
        "if x<y then z>0",
        "Bonjour,\n\nMerci.",
        pytest.param("Velk ondra\r\nPrastin", id="crlf"),
    ],
)
def test_a_plain_text_body_reads_as_the_text_it_is(text: str) -> None:
    """A body with no HTML element is literal text, its lines lines.

    The ``crlf`` case: a CR LF separates lines as LF does. An HTML reading
    of the same characters would show a space instead.
    """

    markdown = read(text)
    shown = displayed(render(markdown))
    lines = text.replace("<", "&lt;").splitlines()
    expected = displayed("<p>" + "<br>".join(lines) + "</p>")

    assert shown == expected
    assert read(render(markdown)) == markdown


def test_an_entity_in_a_plain_text_body_is_read_literally() -> None:
    """With no element, ``&nbsp;`` is six characters of text, not a space.

    Pinned because it is the consequence of reading a body with no HTML
    element as text, and the one a reviewer would most likely expect the
    other way.
    """

    markdown = read("Trasvel&nbsp;ok")

    assert displayed(render(markdown)) == displayed("<p>Trasvel&amp;nbsp;ok</p>")


@pytest.mark.parametrize(
    "markdown",
    [
        "Run **passwd**, then check `logs`.",
        "| a | b<br>c |\n| --- | --- |",
        "Press <kbd>Ctrl</kbd> + <kbd>C</kbd>.",
        "line one\nline two",
    ],
)
def test_the_write_path_keeps_caller_markdown_verbatim(markdown: str) -> None:
    """The write models' validator never rewrites the caller's Markdown."""

    assert read(markdown, plain_text_is_markdown=True) == markdown


def test_the_write_path_still_converts_an_html_document() -> None:
    assert read("<p>A <b>bold</b> move</p>", plain_text_is_markdown=True) == (
        "A **bold** move"
    )


@pytest.mark.parametrize(
    ("markdown", "expected"),
    [
        pytest.param(
            "<https://example.org> puis<br>suite **gras**",
            "puis\\\nsuite \\*\\*gras\\*\\*",
            id="autolink-first",
        ),
        pytest.param(
            "<Entrée> puis <kbd>Ctrl</kbd> **gras**",
            "puis `Ctrl` \\*\\*gras\\*\\*",
            id="angle-text-first",
        ),
    ],
)
def test_markdown_opening_with_angle_brackets_and_holding_html_is_read_as_html(
    markdown: str, expected: str
) -> None:
    """A limit, pinned so that the documentation stays true.

    ``plain_text_is_markdown=True`` passes a value through unless it starts
    with ``<`` and holds a real HTML element *anywhere*. So Markdown that
    opens with an autolink or with angle-bracketed text, and carries inline
    HTML further on, is read as HTML: the autolink, an unknown element to
    the HTML parser, is dropped, and the Markdown syntax is escaped as text.
    The write models' validator passes ``plain_text_is_markdown=True``, so
    ``PostTicket(content=...)`` reads such a value the same way.
    """

    assert read(markdown, plain_text_is_markdown=True) == expected


# ---------------------------------------------------------------------------
# Markdown first
# ---------------------------------------------------------------------------

#: What an integrator writes into followups, tasks, solutions and articles.
CALLER_MARKDOWN = [
    "The printer is **offline**.",
    "Line one\nline two",
    "# Procédure\n\n1. Arrêter le service\n2. Vider le cache\n3. Redémarrer",
    "- Réseau\n  - switch 3\n  - borne wifi\n- Imprimante",
    "- Réseau\n    - switch 3\n- Imprimante",
    "1. Sauvegarder\n   1. la base\n   2. les fichiers\n2. Redémarrer",
    'Voir [la procédure](https://example.org/kb/42 "KB 42").',
    "Lien direct : <https://example.org/kb/43>",
    "![capture](https://example.org/c.png)",
    "Lancer `ipconfig /all` puis envoyer le résultat.",
    "```powershell\nGet-Service | Where-Object Status -eq Running\n```",
    "> Le 30/09, Jean a écrit :\n> merci",
    "| Poste | IP |\n| :--- | ---: |\n| PC12 | 10.0.0.12 |",
    "| Commande | Effet |\n| --- | --- |\n| `ps aux \\| grep java` | processus |",
    "Fichier `mon_fichier_final.docx` et chemin C:\\Temp\\logs.",
    "Contact : support@example.org, R&D, 5 * 3 = 15.",
    "Résolu ✅ — merci 👍",
    "**Cause :** disque plein.\n\n**Solution :** purge des journaux.",
    "Avant :\n\n---\n\nAprès.",
    "Étapes :\n- ouvrir la session\n- lancer Outlook",
]


@pytest.mark.parametrize("markdown", CALLER_MARKDOWN)
def test_caller_markdown_displays_the_same_after_the_round_trip(markdown: str) -> None:
    html = render(markdown)
    back = read(html)

    assert displayed(render(back)) == displayed(html)
    assert read(render(back)) == back
