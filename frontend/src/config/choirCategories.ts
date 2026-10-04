/**
 * Canonical choir category configuration.
 *
 * Single source of truth for the 27 choir-resource categories shown in the
 * browsing screen, upload selector, and edit selector. The backend mirrors
 * this list in `backend/app/constants/choir_categories.py` -- the two must
 * stay in sync.
 *
 * The visible labels and the section/order below are part of the product
 * specification. Do not alphabetise, add extra categories, or duplicate
 * entries. If a category needs to move, update the spec first.
 */

export interface ChoirCategorySection {
  /** Heading rendered above the group, e.g. "Mass Ordinary and Celebration Songs". */
  title: string;
  /** Ordered categories in this section. */
  categories: string[];
}

/**
 * The three ordered sections. The flat category sequence is derived from
 * this in {@link CHOIR_CATEGORIES} so callers never have to re-flatten.
 */
export const CHOIR_CATEGORY_SECTIONS: ChoirCategorySection[] = [
  {
    title: "Mass Ordinary and Celebration Songs",
    categories: [
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
    ],
  },
  {
    title: "Liturgical Seasons",
    categories: [
      "Advent",
      "Christmas",
      "Lent",
      "Pentecost",
      "Holy Week",
      "Easter",
      "Ordinary Time",
    ],
  },
  {
    title: "Other Choir Categories",
    categories: [
      "Marian",
      "Rosary",
      "Wedding",
      "Funeral",
      "Baptism",
      "Saints",
      "Latin",
      "Choir Practice",
      "Others",
    ],
  },
];

/**
 * Flat ordered list of all 27 canonical category labels.
 *
 * ``"All"`` is intentionally NOT included here: it is a browsing filter, not a
 * category a resource can be tagged with. Screens that need the "All" option
 * prepend it themselves.
 */
export const CHOIR_CATEGORIES: string[] = CHOIR_CATEGORY_SECTIONS.flatMap(
  (section) => section.categories
);

/** Total count, asserted by tests. */
export const CHOIR_CATEGORY_COUNT = CHOIR_CATEGORIES.length; // 27

/**
 * Legacy category label -> canonical label.
 *
 * Mirrors ``CATEGORY_ALIASES`` in `backend/app/constants/choir_categories.py`
 * exactly, so a value normalised on the frontend resolves identically to a
 * value normalised on the backend. Anything not recognised here falls back to
 * ``"Others"`` (never dropped, never misclassified).
 */
export const LEGACY_CATEGORY_MAP: Record<string, string> = {
  // Mass ordinary / celebration (formerly split across several labels).
  "Kyrie Eleison": "Kyrie & Gloria",
  "Gloria": "Kyrie & Gloria",
  "Lamb of God": "Agnus Dei",
  "Holy Holy": "Sanctus",
  "Recessional": "Exit",
  "Mass": "Others",
  "Eucharistic": "Others",
  // Liturgical seasons.
  "Triduum": "Holy Week",
  // Marian / devotional.
  "Our Lady": "Marian",
  "Ave Maria": "Marian",
  "Marian Feasts": "Marian",
  "Adoration": "Benediction",
  "Divine Mercy": "Others",
  "Praise and Worship": "Others",
  // Sacraments & feasts (no single canonical home -- safe fallback).
  "Confirmation": "Others",
  "First Holy Communion": "Others",
  "Ordination": "Others",
  "Anointing of the Sick": "Others",
  // Saints and feasts.
  "All Saints": "Saints",
  "All Souls": "Saints",
  "Feast Day": "Saints",
  // Christmas-related.
  "Carols": "Christmas",
  "Epiphany": "Christmas",
  "Holy Family": "Christmas",
  "Christ the King": "Others",
  // Languages / peoples mistakenly used as categories.
  "Swahili": "Others",
  "English": "Others",
  "Other": "Others",
  "Children": "Others",
  "Youth": "Others",
  // Chant.
  "Gregorian Chant": "Latin",
  "Latin Chant": "Latin",
};

/**
 * Returns the canonical category for a stored label, or ``null`` when the
 * label is not a recognised legacy value. Matching mirrors the backend's
 * ``normalize_category``: case-insensitive alias resolution followed by
 * case-insensitive canonical resolution (so a wrongly-cased stored value such
 * as ``"kyrie & gloria"`` still resolves to ``"Kyrie & Gloria"``). Callers
 * that need a non-null value fall back to ``"Others"`` (see ``resources.tsx``).
 */
export function canonicaliseCategory(stored: string): string | null {
  if (CHOIR_CATEGORIES.includes(stored)) {
    return stored;
  }
  const lower = stored.toLowerCase();
  for (const [alias, canonical] of Object.entries(LEGACY_CATEGORY_MAP)) {
    if (alias.toLowerCase() === lower) {
      return canonical;
    }
  }
  for (const canonical of CHOIR_CATEGORIES) {
    if (canonical.toLowerCase() === lower) {
      return canonical;
    }
  }
  return null;
}

/**
 * Strict equivalent of the backend's ``normalize_category``: always returns a
 * usable canonical category (never ``null``), resolving unknown labels to
 * ``"Others"``. Exposed for parity with the backend and for any screen that
 * wants the total-fallback semantics.
 */
export function normalizeCategory(value: string | undefined | null): string {
  if (!value) {
    return "Others";
  }
  const stripped = value.trim();
  if (!stripped) {
    return "Others";
  }
  if (CHOIR_CATEGORIES.includes(stripped)) {
    return stripped;
  }
  const resolved = canonicaliseCategory(stripped);
  return resolved ?? "Others";
}
