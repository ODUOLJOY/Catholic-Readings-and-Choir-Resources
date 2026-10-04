"""Universalis parser tests, plus an opt-in live endpoint check.

The previous version of this file was a single ``test_universalis_api`` function
that called ``requests.get`` against ``universalis.com`` and returned
``True``/``False``. pytest records a returning test as passing with a
``PytestReturnNotNoneWarning``, so every failure mode - timeout, HTTP error,
malformed body - was reported as a success, and the suite depended on a network
round trip to pass.

Coverage is now split in two:

* deterministic offline tests for ``UniversalisParser``, the code this repository
  actually owns, which previously had none at all;
* a live endpoint probe that is skipped unless ``RUN_LIVE_UNIVERSALIS_TESTS=1``
  is set, so the default suite stays offline and deterministic while the network
  behaviour remains verifiable on demand.
"""

import json
import os
from datetime import date

import pytest

from app.services.universalis_parser import UniversalisParser

TEST_DATE = date(2026, 10, 10)

# The documented Kenya propers format: https://universalis.com/africa.kenya/YYYYMMDD/
def universalis_url(day: date, propers: str = "mass") -> str:
    return f"https://universalis.com/africa.kenya/{day.strftime('%Y%m%d')}/{propers}.htm"


def test_url_is_built_for_the_kenya_propers_calendar():
    assert universalis_url(TEST_DATE) == (
        "https://universalis.com/africa.kenya/20261010/mass.htm"
    )


def test_url_uses_the_compact_date_form():
    url = universalis_url(date(2026, 1, 5))
    assert "/20260105/" in url


def test_url_supports_other_propers():
    assert universalis_url(TEST_DATE, propers="office").endswith("/office.htm")


# --------------------------------------------------------------------------
# Reading reference parsing
# --------------------------------------------------------------------------


def test_simple_reference_is_split_into_book_chapter_and_verses():
    parsed = UniversalisParser.parse_reference("Galatians 3:22-29")

    assert parsed["book"] == "Galatians"
    assert parsed["chapter_start"] == 3
    assert parsed["chapter_end"] == 3
    assert parsed["verse_start"] == "22-29"
    assert parsed["verse_end"] == "22-29"
    assert parsed["display_reference"] == "Galatians 3:22-29"
    assert parsed["psalm_number_variant"] is None


def test_psalm_variant_is_captured_separately():
    parsed = UniversalisParser.parse_reference("Psalm 104(105):2-7")

    assert parsed["book"] == "Psalm"
    assert parsed["chapter_start"] == 104
    assert parsed["psalm_number_variant"] == "105"
    assert parsed["verse_start"] == "2-7"
    assert parsed["chapter_end"] == 104


def test_comma_separated_verse_list_is_preserved_verbatim():
    parsed = UniversalisParser.parse_reference("Daniel 7:9-10,13-14")

    assert parsed["book"] == "Daniel"
    assert parsed["chapter_start"] == 7
    assert parsed["verse_start"] == "9-10,13-14"
    assert parsed["verse_end"] == "9-10,13-14"


def test_numbered_books_are_parsed_correctly():
    parsed = UniversalisParser.parse_reference("1 Corinthians 13:4-7")

    assert parsed["book"] == "1 Corinthians"
    assert parsed["chapter_start"] == 13
    assert parsed["verse_start"] == "4-7"


def test_second_numbered_book_is_parsed_correctly():
    parsed = UniversalisParser.parse_reference("2 Timothy 1:5-7")

    assert parsed["book"] == "2 Timothy"
    assert parsed["chapter_start"] == 1


def test_single_verse_is_parsed():
    parsed = UniversalisParser.parse_reference("John 1:1")

    assert parsed["book"] == "John"
    assert parsed["chapter_start"] == 1
    assert parsed["verse_start"] == "1"
    assert parsed["verse_end"] == "1"


def test_display_reference_is_always_preserved():
    """The original string is kept even when parsing finds nothing."""
    parsed = UniversalisParser.parse_reference("Some unparseable text")

    assert parsed["display_reference"] == "Some unparseable text"


def test_chapter_only_reference_leaves_verses_unset():
    parsed = UniversalisParser.parse_reference("Isaiah 53")

    assert parsed["book"] == "Isaiah"
    assert parsed["chapter_start"] is None
    assert parsed["verse_start"] is None


def test_every_result_carries_the_same_keys():
    """Callers rely on a stable key set, so a new key must not appear silently."""
    expected = {
        "book",
        "chapter_start",
        "verse_start",
        "chapter_end",
        "verse_end",
        "display_reference",
        "psalm_number_variant",
    }
    for reference in ("Galatians 3:22-29", "Psalm 104(105):2-7", "Isaiah 53"):
        assert set(UniversalisParser.parse_reference(reference)) == expected


# --------------------------------------------------------------------------
# Rank normalisation
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Solemnity", "Solemnity"),
        ("Solemnity of the Lord", "Solemnity"),
        ("Feast", "Feast"),
        ("Feast of Christ the King", "Feast"),
        ("Memorial", "Memorial"),
        ("Obligatory Memorial", "Memorial (Obligatory)"),
        ("Required Memorial", "Memorial (Obligatory)"),
        ("Feria", "Feria"),
        ("Sunday", "Sunday"),
        ("Sunday in Ordinary Time", "Sunday"),
        ("Commemoration", "Commemoration"),
    ],
)
def test_celebration_ranks_are_normalised(text, expected):
    assert UniversalisParser.parse_celebration_rank(text) == expected


def test_rank_matching_is_case_insensitive():
    assert UniversalisParser.parse_celebration_rank("SOLEMNITY") == "Solemnity"
    assert UniversalisParser.parse_celebration_rank("memorial") == "Memorial"


def test_feast_wins_over_memorial_when_both_words_appear():
    """Rank precedence is asserted so reordering the branches is caught."""
    assert (
        UniversalisParser.parse_celebration_rank("Solemnity and Memorial")
        == "Solemnity"
    )
    assert UniversalisParser.parse_celebration_rank("Feast and Memorial") == "Feast"


# --------------------------------------------------------------------------
# Live endpoint probe, opt-in
# --------------------------------------------------------------------------

live_required = pytest.mark.skipif(
    os.getenv("RUN_LIVE_UNIVERSALIS_TESTS") != "1",
    reason="set RUN_LIVE_UNIVERSALIS_TESTS=1 to call universalis.com",
)


@live_required
def test_universalis_endpoint_returns_a_body():
    """Network-dependent; only runs when explicitly enabled."""
    import requests

    url = universalis_url(TEST_DATE)
    response = requests.get(url, timeout=15)

    assert response.status_code == 200, response.status_code
    assert response.text.strip(), "empty response body"


@live_required
def test_universalis_response_is_either_json_or_html():
    """The endpoint serves HTML; it must never be silently treated as JSON."""
    import requests

    content = requests.get(universalis_url(TEST_DATE), timeout=15).text
    is_html = content.lstrip()[:9].lower().startswith(("<!doctype", "<html"))

    if not is_html:
        # If it ever becomes JSON, it must actually parse as JSON.
        json.loads(content)
