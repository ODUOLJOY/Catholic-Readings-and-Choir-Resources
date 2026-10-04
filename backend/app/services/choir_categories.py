"""Backwards-compatibility shim.

The canonical choir-category configuration lives in
:mod:`app.constants.choir_categories`. This module previously held a duplicate
copy; it now re-exports the names that routes, migrations and tests may still
reference so existing imports keep working while callers migrate to the
constants module.

New code should import from :mod:`app.constants.choir_categories` directly.
"""
from __future__ import annotations

from app.constants.choir_categories import (  # noqa: F401
    CATEGORY_ALIASES,
    CHOIR_CATEGORIES,
    CHOIR_CATEGORY_SECTIONS,
    VALID_CATEGORIES,
    categories_matching_filter,
    normalize_category,
)

# Legacy alias for the constants module's CATEGORY_ALIASES, kept so any caller
# (or migration) written against the old name continues to resolve.
LEGACY_CATEGORY_MAP = CATEGORY_ALIASES


def is_valid_category(value):
    """Backwards-compatible alias for ``value in VALID_CATEGORIES``."""
    return value in VALID_CATEGORIES


def canonicalise_category(stored):
    """Backwards-compatible alias for :func:`normalize_category`.

    Returns the canonical label, or ``"Others"`` for anything unknown (the
    constants module never loses a resource). The previous ``None``-on-unknown
    behaviour is intentionally not preserved: callers that branched on
    ``None`` should switch to checking ``VALID_CATEGORIES`` directly.
    """
    return normalize_category(stored)


def assert_valid_category(value):
    """Kept for import compatibility only.

    The canonical design accepts legacy labels and normalises them via
    :func:`normalize_category` rather than rejecting them at the API boundary,
    so this function is no longer used by the routes. It returns ``value`` if
    it is a canonical label and raises ``ValueError`` otherwise, matching the
    previous behaviour, but callers should prefer :func:`normalize_category`.
    """
    if value not in VALID_CATEGORIES:
        raise ValueError(
            f"Invalid category. Must be one of: {', '.join(CHOIR_CATEGORIES)}"
        )
    return value
