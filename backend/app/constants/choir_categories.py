"""Canonical choir-resource category catalog.

This module is the single source of truth for the 27 choir-resource categories
displayed in the library and accepted on upload/edit. The user-facing labels
ARE the stable internal identifiers: every label is unique, short, and is the
exact value stored on ``ChoirResource.category``. No separate surrogate ids are
used, so a category label is identical over the wire, in the database, in search
and in navigation (the ``&`` in ``Kyrie & Gloria`` is URL-safe once encoded).

The ordering here is deliberately neither alphabetical nor insertion-based;
``CHOIR_CATEGORY_SECTIONS`` preserves the required three-section, 27-label
sequence:

    1. Mass Ordinary and Celebration Songs  (11)
    2. Liturgical Seasons                    (7)
    3. Other Choir Categories                (9)

``normalize_category`` is the reversible compatibility mapping that reconciles
free-form / legacy category values with the canonical catalog. It never loses a
resource: anything it cannot place falls back to ``"Others"``.
"""

from __future__ import annotations

# A section is ``(section_title, ordered_labels)``. Section order and label order
# within a section are both significant.
CHOIR_CATEGORY_SECTIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "Mass Ordinary and Celebration Songs",
        (
            "Entrance",
            "Kyrie & Gloria",
            "Responsorial Psalm",
            "Sadaka",
            "Offertory",
            "Sanctus",
            "Agnus Dei",
            "Communion",
            "Benediction",
            "Thanksgiving",
            "Exit",
        ),
    ),
    (
        "Liturgical Seasons",
        (
            "Advent",
            "Christmas",
            "Lent",
            "Pentecost",
            "Holy Week",
            "Easter",
            "Ordinary Time",
        ),
    ),
    (
        "Other Choir Categories",
        (
            "Marian",
            "Rosary",
            "Wedding",
            "Funeral",
            "Baptism",
            "Saints",
            "Latin",
            "Choir Practice",
            "Others",
        ),
    ),
)

# Flat ordered list of all 27 canonical categories.
CHOIR_CATEGORIES: tuple[str, ...] = tuple(
    category
    for _section_title, categories in CHOIR_CATEGORY_SECTIONS
    for category in categories
)

# Fast lookup collections kept in sync with CHOIR_CATEGORIES.
VALID_CATEGORIES: frozenset[str] = frozenset(CHOIR_CATEGORIES)
CATEGORY_ORDER: dict[str, int] = {
    category: index for index, category in enumerate(CHOIR_CATEGORIES)
}

# Legacy / free-form values that have entered the catalog historically and the
# canonical category each should be normalised to. These are the values a
# deployed database may already hold; anything not listed here resolves to
# "Others" (never dropped, never misclassified).
CATEGORY_ALIASES: dict[str, str] = {
    # Mass ordinary / celebration (formerly split across several labels).
    "Kyrie Eleison": "Kyrie & Gloria",
    "Gloria": "Kyrie & Gloria",
    "Lamb of God": "Agnus Dei",
    "Holy Holy": "Sanctus",
    "Recessional": "Exit",
    "Mass": "Others",
    "Eucharistic": "Others",
    # Liturgical seasons.
    "Triduum": "Holy Week",
    # Marian / devotional.
    "Our Lady": "Marian",
    "Ave Maria": "Marian",
    "Marian Feasts": "Marian",
    "Adoration": "Benediction",
    "Divine Mercy": "Others",
    "Praise and Worship": "Others",
    # Sacraments & feasts (no single canonical home — safe fallback).
    "Confirmation": "Others",
    "First Holy Communion": "Others",
    "Ordination": "Others",
    "Anointing of the Sick": "Others",
    # Saints and feasts.
    "All Saints": "Saints",
    "All Souls": "Saints",
    "Feast Day": "Saints",
    # Christmas-related.
    "Carols": "Christmas",
    "Epiphany": "Christmas",
    "Holy Family": "Christmas",
    "Christ the King": "Others",
    # Languages / peoples mistakenly used as categories.
    "Swahili": "Others",
    "English": "Others",
    "Other": "Others",
    "Children": "Others",
    "Youth": "Others",
    # Chant.
    "Gregorian Chant": "Latin",
    "Latin Chant": "Latin",
}


def normalize_category(value: str | None) -> str:
    """Return the canonical category for ``value``.

    * ``None`` / blank / whitespace-only -> ``"Others"``.
    * Already-canonical labels pass through unchanged (canonical casing).
    * Known legacy labels resolve to their canonical home (case-insensitive).
    * Any other value -> ``"Others"`` so a resource is never left uncategorised.

    This function is the reversible compatibility layer between the historical
    free-form ``category`` column and the canonical 27-label catalog. It is pure
    and side-effect free, so it is safe to call from the API layer, migrations
    and tests.
    """
    if value is None:
        return "Others"
    stripped = value.strip()
    if not stripped:
        return "Others"
    # Exact canonical label (preferred casing).
    if stripped in VALID_CATEGORIES:
        return stripped
    lower = stripped.lower()
    # Case-insensitive alias resolution (e.g. "mass" -> "Others").
    for alias, canonical in CATEGORY_ALIASES.items():
        if alias.lower() == lower:
            return canonical
    # Case-insensitive canonical resolution (e.g. "KYLIE & GLORIA" -> ...).
    for canonical in CHOIR_CATEGORIES:
        if canonical.lower() == lower:
            return canonical
    return "Others"


def categories_matching_filter(canonical_filter: str) -> set[str]:
    """All stored labels a browse filter should match.

    When a user selects ``"Kyrie & Gloria"``, rows still labelled
    ``"Kyrie Eleison"`` or ``"Gloria"`` (legacy values that
    :func:`normalize_category` maps to ``"Kyrie & Gloria"``) must appear
    alongside rows already on the canonical label. This returns the canonical
    label plus every legacy alias that resolves to it, so the choir list query
    can use a single ``IN`` filter.

    Always includes the canonical label itself. Returns an empty set for an
    unknown filter so an invalid selection surfaces no rows rather than every
    row.
    """
    if canonical_filter not in VALID_CATEGORIES:
        return set()
    matches = {canonical_filter}
    for alias, canonical in CATEGORY_ALIASES.items():
        if canonical == canonical_filter:
            matches.add(alias)
    return matches
