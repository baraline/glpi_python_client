"""What a long or a deep body costs: growth, not seconds.

A converter that is quadratic somewhere converts an ordinary body in
milliseconds and a pathological one in minutes, so the cost tests measure
how the time grows: converting a body four times as long should take about
four times as long. A quadratic pass takes about sixteen times as long. The
tests assert ``time(4n) / time(n) < 8``, halfway between the two on a log
scale.

An absolute budget would be the wrong instrument. Up to 0.6.0 this
package's tests gave each long body 20 seconds. That is generous enough
for a shared CI runner, so it catches a quadratic pass only once a body is
long enough to cost 20 seconds, and the tests then spend most of their
time converting. A ratio needs far shorter bodies -- a few thousand items
where those tests had 20,000 -- and the runner's speed cancels out.

Ported from easyvista-python-client 0.4.0, whose converter is this one.
The shapes are 0.6.0's four long bodies, in this form; three bodies dense
with syntax from that package's earlier tests; and one per fix that
removed a quadratic. Measured 2026-10-02, timed the way :func:`growth`
times, at these sizes, three readings per shape: this converter grew by
3.0 to 7.5 on CPython 3.12.3 and by 2.6 to 5.7 on 3.13.14. On 3.12.3,
0.6.0 grew by 10.3 and 10.4 on the ordered list, 14.2 and 15.5 on bold
holding line breaks and 30.9 and 34.4 on the unfinished-tag tail (two
readings each), and reverting fix 12, 13 or 15 alone grew by 10.4, 14.1
and 33.2 on its shape (one reading each).

A ratio between 8 and 10 is measured once more and the second reading
decides, so that one burst of load cannot fail a linear pass; a reading of
10 or more fails at once.
"""

from __future__ import annotations

import gc
import math
import time
from collections.abc import Callable

import pytest

from glpi_python_client.content.conversion import GlpiContentConverter

read = GlpiContentConverter.from_transport
render = GlpiContentConverter.to_transport

#: ``time(4n) / time(n)`` at or above this fails: linear reads about 4,
#: quadratic about 16.
_LIMIT = 8

#: The shortest reading worth trusting: a body that converts faster is read
#: again until the clock has run this long, and the time is the average.
_SHORTEST = 0.02


def _timed(html: str) -> float:
    """Seconds to read ``html`` once, with the cyclic collector out of the way.

    A collection starting mid-conversion is charged to whichever body
    happens to be converting, so the heap is collected before the clock
    starts and the collector stays off until it stops. A body read in a few
    milliseconds is read again until :data:`_SHORTEST` has passed, so that
    the scheduler's tick does not decide the ratio.
    """

    gc.collect()
    gc.disable()
    try:
        reads = 0
        started = time.perf_counter()
        while True:
            read(html)
            reads += 1
            took = time.perf_counter() - started
            if took >= _SHORTEST:
                return took / reads
    finally:
        gc.enable()


def growth(make: Callable[[int], str], n: int, rounds: int = 3) -> float:
    """Return ``time(make(4n)) / time(make(n))``, each the best of ``rounds``.

    The two sizes alternate, so a burst of load on a shared machine slows
    both rather than one; the best of several runs drops the runs it hit.
    """

    small, large = make(n), make(4 * n)
    best_small = best_large = math.inf
    for _ in range(rounds):
        best_small = min(best_small, _timed(small))
        best_large = min(best_large, _timed(large))
    return best_large / best_small


def assert_linear(make: Callable[[int], str], n: int) -> None:
    ratio = growth(make, n)
    if _LIMIT <= ratio < 1.25 * _LIMIT:  # near the line: see the module docstring
        ratio = growth(make, n)
    assert ratio < _LIMIT, (
        f"converting a body four times as long took {ratio:.1f} times as long"
    )


@pytest.mark.parametrize(
    ("make", "n"),
    [
        pytest.param(
            lambda n: "<p>" + "ligne<br>" * n + "</p>", 1500, id="line-breaks"
        ),
        pytest.param(
            lambda n: "<ul>" + "<li>x</li>" * n + "</ul>", 1000, id="list-items"
        ),
        pytest.param(
            lambda n: "<ul>" + "<li></li>" * n + "</ul>", 2000, id="empty-items"
        ),
        pytest.param(
            lambda n: "<p>" + "<b>gras</b> mot " * n + "</p>", 750, id="emphasis"
        ),
    ],
)
def test_a_long_body_converts_in_linear_time(
    make: Callable[[int], str], n: int
) -> None:
    """0.6.0's long bodies: each pass mdformat makes is linear."""

    assert_linear(make, n)


@pytest.mark.parametrize(
    ("make", "n"),
    [
        pytest.param(
            lambda n: "<p>" + "[a " * n + "</p>", 2500, id="unclosed-brackets"
        ),
        pytest.param(
            lambda n: "<p>" + "_a " * n + "</p>", 2500, id="underscores-opening-words"
        ),
        pytest.param(lambda n: "<p>" + "``` " * n + "</p>", 2000, id="backtick-runs"),
    ],
)
def test_a_body_dense_with_syntax_converts_in_linear_time(
    make: Callable[[int], str], n: int
) -> None:
    """One paragraph packed with what CommonMark scans for, each escaped.

    From easyvista-python-client's earlier tests, where 20,000 of each
    took from 8 to 117 seconds before the passes of that package's
    converter of the day were made linear. This converter is not quite
    linear on them either: that package measured the ratio at about 4.3 at
    these sizes and about 7 at eight times them (2026-10-02, CPython
    3.12.11), a superlinear term it traced to markdown-it-py 3.0 joining
    the text of one long escape-dense line. So the sizes are kept small:
    the test catches a pass that turns quadratic, not that term.
    """

    assert_linear(make, n)


def test_a_long_ordered_list_converts_in_linear_time() -> None:
    """Fix 12: each item takes its number from the item before it.

    markdownify counted every sibling before each item, which was quadratic.
    On 5,000 items 0.6.0 took 3.9 seconds against 0.8 with the fix
    (measured 2026-10-02, CPython 3.12.3, best of three). The list is
    written one item per line, as an editor writes it: each newline is one
    more sibling to count, which makes the quadratic easier to see.
    """

    assert_linear(lambda n: "<ol>\n" + "<li>x</li>\n" * n + "</ol>", 1250)


def test_bold_holding_a_long_run_of_line_breaks_converts_in_linear_time() -> None:
    """Fix 13: the regex that moves an element's edge breaks outside it is greedy.

    The lazy one rescanned the run after it at every step.
    """

    assert_linear(lambda n: "<p><b>a" + "<br>\n" * n + "b</b></p>", 2000)


def test_a_tail_of_unfinished_tags_converts_in_linear_time() -> None:
    """Fix 15: no ``<`` after the last ``>`` reaches the parser as a ``<``.

    CPython's ``html.parser`` before 3.11.14, 3.12.12 and 3.13.6 rescanned
    to the end of the input for each one (CVE-2025-6069). On a patched
    interpreter the parser is linear anyway, so there this test cannot see
    the guard go; on an unpatched one it fails within seconds without it.
    """

    assert_linear(lambda n: "<p>r</p>" + "x <a " * n, 500)


def test_a_body_too_deep_to_convert_keeps_its_text() -> None:
    """markdownify recurses per nesting level; past the stack, the text is kept."""

    html = "<div>" * 3000 + "<p>__init__ au fond</p>" + "</div>" * 3000

    markdown = read(html)

    assert "init" in markdown
    assert "au fond" in render(markdown)
