"""Normalize existing choir_resources.category values to the canonical 27-label catalog.

Revision 13 is a **data-only, idempotent** migration. It reconciles the historical
free-form ``category`` column with the canonical catalog defined in
``app.constants.choir_categories`` (the 27 ordered categories used by the choir
library). It:

* maps every known legacy label to its canonical home via the same alias map
  used by the API layer (``normalize_category``);
* leaves rows that already hold a canonical label untouched;
* falls back to ``"Others"`` for anything unrecognised — preserving every row
  and never misclassifying or deleting data.

Because it is a pure ``UPDATE`` built from the constant alias map (no schema
introspection), it renders cleanly in offline SQL mode and is safe to re-run:
once all rows are canonical the ``WHERE`` clause matches nothing.

The downgrade is intentionally a no-op. Normalisation is a one-way lossy
collapse of many legacy labels into few canonical ones, so there is no faithful
reverse mapping. Canonical values are stable, therefore re-applying
normalisation (the "downgrade") leaves the data unchanged — the migration is
safe to run more than once in either direction and never corrupts state.
"""

from alembic import op
from sqlalchemy import text

from app.constants.choir_categories import CHOIR_CATEGORIES, CATEGORY_ALIASES

# revision identifiers, used by Alembic.
revision = "20261003_01"
down_revision = "20261002_13"  # chained after the legacy-alias normalize
branch_labels = None
depends_on = None


def _normalize_sql() -> str:
    """Build the idempotent UPDATE from the canonical alias map (no DB access)."""
    # Canonical values that are already correct: skip them in the WHERE clause so
    # re-running the migration is a no-op once normalization has settled.
    canonical_listing = ", ".join(f"{value!r}" for value in CHOIR_CATEGORIES)
    whens = " ".join(
        f"WHEN {alias!r} THEN {canonical!r}"
        for alias, canonical in CATEGORY_ALIASES.items()
    )
    return (
        "UPDATE choir_resources "
        "SET category = CASE TRIM(COALESCE(category, '')) "
        f"{whens} ELSE 'Others' END "
        f"WHERE TRIM(COALESCE(category, '')) NOT IN ({canonical_listing})"
    )


def upgrade() -> None:
    op.execute(text(_normalize_sql()))


def downgrade() -> None:
    # Idempotent normalization is not reversible (many legacy labels collapse to
    # a canonical one). Canonical values are stable, so this no-op downgrade is
    # safe to run repeatedly without altering or losing data.
    pass
