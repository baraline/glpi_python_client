"""Realistic content survives the trip between GLPI's HTML and Markdown, both ways.

The contract, checked with an HTML parser (:mod:`.display`) rather than by eye:

* **HTML first.** ``to_transport(from_transport(html))`` displays what
  ``html`` displays -- the same blocks, words, and bold/italic/code/link on
  each character -- and the Markdown is a fixed point: reading back what it
  renders gives the same Markdown.
* **Markdown first.** Markdown a caller writes renders to HTML that reads
  back as Markdown displaying the same, and that Markdown is a fixed point.

The bodies are the shapes GLPI's editor and the mail collector store, and
the Markdown is what an integrator writes. Adversarial input -- syntax
characters packed into every position -- is out of scope: the converter is a
thin layer over markdownify, mdformat and cmark-gfm, and it is held to
realistic content.
"""

from __future__ import annotations

import pytest

from glpi_python_client.content.conversion import GlpiContentConverter
from glpi_python_client.content.tests.display import displayed

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
    """A signature laid out as a table inside a table keeps every word."""

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
    ],
)
def test_a_plain_text_body_reads_as_the_text_it_is(text: str) -> None:
    """A body with no HTML element is literal text, its lines lines."""

    markdown = read(text)
    shown = displayed(render(markdown))
    expected = displayed(
        "<p>" + text.replace("<", "&lt;").replace("\n", "<br>") + "</p>"
    )

    assert shown == expected
    assert read(render(markdown)) == markdown


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
