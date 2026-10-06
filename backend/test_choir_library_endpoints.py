"""Contract tests for the choir library endpoints the browse page is built on.

The library page renders a card count next to each of the 27 categories and asks
the list endpoint for ranked shelves ("most loved", "recently added"). Both are
only trustworthy if they are answers from the database rather than numbers the
UI made up, and only consistent if the counts are produced by the same visibility
predicate the list uses. These tests pin that down.
"""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import app.models.community  # noqa: F401
import app.models.parish  # noqa: F401
import app.models.user  # noqa: F401
from app.db.database import Base, get_db
from app.main import app
from app.auth.security import create_access_token
from app.constants.choir_categories import (
    CHOIR_CATEGORIES,
    CHOIR_CATEGORY_SECTIONS,
)
from app.models.choir import ChoirResource
from app.models.community import ParishMembership
from app.models.locations import Deanery, Diocese
from app.models.parish import Parish
from app.models.user import User

BASE_TIME = datetime(2024, 1, 1, tzinfo=timezone.utc)


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    with Session(engine) as session:
        yield session
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def client(db: Session):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)


def make_resource(
    db: Session,
    title: str,
    category: str,
    *,
    approved: bool = True,
    published: bool = True,
    download_count: int | None = 0,
    rating: int | None = None,
    duration: int | None = None,
    language: str = "English",
    created_at: datetime | None = None,
    parish_id: int | None = None,
) -> ChoirResource:
    resource = ChoirResource(
        title=title,
        category=category,
        language=language,
        file_url=f"/uploads/{title.replace(' ', '-').lower()}.mp3",
        file_type="audio",
        is_approved=approved,
        is_published=published,
        moderation_status="approved" if approved and published else "pending",
        download_count=download_count,
        rating=rating,
        duration=duration,
        created_at=created_at or BASE_TIME,
        parish_id=parish_id,
    )
    db.add(resource)
    db.flush()
    return resource


def counts_of(payload: dict) -> dict[str, int]:
    return payload["counts"]

# --- /categories: shape, ordering and real counts ----------------------------


def test_categories_preserve_the_required_three_section_order(client):
    response = client.get("/api/choir/categories")

    assert response.status_code == 200
    payload = response.json()
    # The catalog contract is unchanged: sections and the flat list are still
    # plain label strings in the required order.
    assert [
        [label for label in section["categories"]] for section in payload["sections"]
    ] == [list(categories) for _title, categories in CHOIR_CATEGORY_SECTIONS]
    assert payload["categories"] == list(CHOIR_CATEGORIES)
    # Counts are additive and cover all 27.
    assert list(counts_of(payload)) == list(CHOIR_CATEGORIES)


def test_categories_report_zero_for_an_empty_library(client, db):
    response = client.get("/api/choir/categories")

    payload = response.json()
    assert payload["total"] == 0
    assert all(count == 0 for count in counts_of(payload).values())


def test_category_counts_match_stored_rows(client, db):
    make_resource(db, "Panis Angelicus", "Communion")
    make_resource(db, "Ave Maria", "Marian")
    make_resource(db, "Another Communion", "Communion")

    payload = client.get("/api/choir/categories").json()
    counts = counts_of(payload)

    assert counts["Communion"] == 2
    assert counts["Marian"] == 1
    assert payload["total"] == 3


def test_counts_fold_legacy_labels_into_the_canonical_category(client, db):
    # Rows uploaded before the canonical catalog can still carry legacy labels.
    # They belong to the category the member actually sees, not to "nothing".
    make_resource(db, "Kyrie Eleison", "Kyrie Eleison")
    make_resource(db, "Gloria in Excelsis", "Gloria")
    make_resource(db, "Canticle of Zechariah", "Triduum")

    counts = counts_of(client.get("/api/choir/categories").json())

    assert counts["Kyrie & Gloria"] == 2
    assert counts["Holy Week"] == 1


def test_counts_exclude_unapproved_or_unpublished_rows(client, db):
    make_resource(db, "Visible", "Exit")
    make_resource(db, "Not approved", "Exit", approved=False, published=True)
    make_resource(db, "Not published", "Exit", approved=True, published=False)

    counts = counts_of(client.get("/api/choir/categories").json())

    assert counts["Exit"] == 1


def test_legacy_rows_are_listed_under_the_category_the_count_reports(client, db):
    make_resource(db, "Gloria", "Gloria")
    make_resource(db, "Kyrie", "Kyrie Eleison")

    listed = client.get("/api/choir/", params={"category": "Kyrie & Gloria"}).json()
    counts = counts_of(client.get("/api/choir/categories").json())

    # The count on the card is the number of rows opening that category.
    assert counts["Kyrie & Gloria"] == len(listed) == 2


# --- /categories: parish visibility -----------------------------------------


def _make_parish_member(db: Session) -> tuple[User, Parish]:
    diocese = Diocese(name="Diocese", code="dio")
    db.add(diocese)
    db.flush()
    deanery = Deanery(name="Deanery", code="dea", diocese_id=diocese.id)
    db.add(deanery)
    db.flush()
    parish = Parish(
        name="Parish", code="par", diocese_id=diocese.id, deanery_id=deanery.id
    )
    user = User(
        full_name="Chooser",
        email="chooser@example.org",
        hashed_password="not-a-real-password-hash",
    )
    db.add_all([parish, user])
    db.flush()
    db.add(
        ParishMembership(
            user_id=user.id,
            parish_id=parish.id,
            status="active",
        )
    )
    db.flush()
    return user, parish


def test_anonymous_counts_exclude_parish_scoped_resources(client, db):
    _user, parish = _make_parish_member(db)
    make_resource(db, "Global song", "Entrance")
    make_resource(db, "Parish song", "Entrance", parish_id=parish.id)

    counts = counts_of(client.get("/api/choir/categories").json())
    listed = client.get("/api/choir/", params={"category": "Entrance"}).json()

    assert counts["Entrance"] == 1
    assert [row["title"] for row in listed] == ["Global song"]


def test_member_counts_include_their_own_parish_resources(client, db):
    user, parish = _make_parish_member(db)
    make_resource(db, "Global song", "Entrance")
    make_resource(db, "Parish song", "Entrance", parish_id=parish.id)

    token = create_access_token({"sub": str(user.id), "type": "access"})
    headers = {"Authorization": f"Bearer {token}"}

    counts = counts_of(client.get("/api/choir/categories", headers=headers).json())
    listed = client.get("/api/choir/", params={"category": "Entrance"}, headers=headers).json()

    assert counts["Entrance"] == 2
    assert len(listed) == 2


# --- /: sorting and limiting for the ranked shelves --------------------------


def test_recent_is_the_default_order(client, db):
    make_resource(db, "Older", "Marian", created_at=BASE_TIME)
    make_resource(db, "Newest", "Marian", created_at=BASE_TIME + timedelta(days=5))
    make_resource(db, "Middle", "Marian", created_at=BASE_TIME + timedelta(days=2))

    listed = client.get("/api/choir/").json()

    assert [row["title"] for row in listed] == ["Newest", "Middle", "Older"]


def test_popular_orders_by_real_download_counts(client, db):
    make_resource(db, "Never downloaded", "Marian", download_count=None)
    make_resource(db, "Most loved", "Marian", download_count=90)
    make_resource(db, "Somewhat loved", "Marian", download_count=12)

    listed = client.get("/api/choir/", params={"sort": "popular"}).json()

    # A null download_count must not sort above a genuinely popular resource.
    assert [row["title"] for row in listed] == [
        "Most loved",
        "Somewhat loved",
        "Never downloaded",
    ]


def test_popular_breaks_ties_deterministically(client, db):
    make_resource(db, "First", "Marian", download_count=5, created_at=BASE_TIME)
    make_resource(db, "Second", "Marian", download_count=5, created_at=BASE_TIME)

    listed = client.get("/api/choir/", params={"sort": "popular"}).json()

    assert len(listed) == 2
    assert [row["title"] for row in listed] == [
        listed[0]["title"],
        listed[1]["title"],
    ]


def test_title_order_is_alphabetical(client, db):
    make_resource(db, "Zambezi", "Marian")
    make_resource(db, "Ave Maria", "Marian")

    listed = client.get("/api/choir/", params={"sort": "title"}).json()

    assert [row["title"] for row in listed] == ["Ave Maria", "Zambezi"]


def test_unknown_sort_is_rejected(client):
    response = client.get("/api/choir/", params={"sort": "whatever"})

    assert response.status_code == 422


@pytest.mark.parametrize("limit", [0, -1, 201])
def test_out_of_range_limit_is_rejected(client, limit):
    response = client.get("/api/choir/", params={"limit": limit})

    assert response.status_code == 422


def test_limit_returns_a_shelf_of_that_size(client, db):
    for index in range(5):
        make_resource(db, f"Song {index}", "Marian", download_count=index)

    listed = client.get(
        "/api/choir/", params={"sort": "popular", "limit": 2}
    ).json()

    assert [row["title"] for row in listed] == ["Song 4", "Song 3"]


def test_limit_combines_with_a_category_filter(client, db):
    make_resource(db, "Communion one", "Communion")
    make_resource(db, "Communion two", "Communion")
    make_resource(db, "Marian one", "Marian")

    listed = client.get(
        "/api/choir/", params={"category": "Communion", "limit": 1}
    ).json()

    assert [row["title"] for row in listed] == ["Communion two"]


def test_duration_is_serialised_as_a_number(client, db):
    # The model stores duration in seconds as an Integer. The client must be able
    # to format it without guessing whether it received 214 or "214".
    make_resource(db, "Timed", "Marian", duration=214)

    assert client.get("/api/choir/").json()[0]["duration"] == 214


def test_metadata_columns_reach_the_client(client, db):
    resource = ChoirResource(
        title="Panis Angelicus",
        category="Communion",
        language="Latin",
        file_url="/uploads/panis.mp3",
        file_type="audio",
        composer="St. Thomas Aquinas",
        arranger="A. Reader",
        author="Traditional",
        alternative_title="Bread of Angels",
        voice_part="SATB",
        season="Easter",
        key_signature="C major",
        tempo="Andante",
        duration=214,
        rating=5,
        download_count=42,
        is_approved=True,
        is_published=True,
        moderation_status="approved",
        created_at=BASE_TIME,
    )
    db.add(resource)
    db.flush()
    db.commit()

    row = client.get("/api/choir/", params={"category": "Communion"}).json()[0]

    assert row["composer"] == "St. Thomas Aquinas"
    assert row["arranger"] == "A. Reader"
    assert row["voice_part"] == "SATB"
    assert row["key_signature"] == "C major"
    assert row["tempo"] == "Andante"
    assert row["season"] == "Easter"
    assert row["duration"] == 214
    # Real popularity comes from the database, never from a number on the client.
    assert row["download_count"] == 42
    assert row["rating"] == 5


def test_categories_param_returns_rows_from_several_labels(client, db):
    make_resource(db, "Entrance hymn", "Entrance")
    make_resource(db, "Communion hymn", "Communion")
    make_resource(db, "Marian hymn", "Marian")

    listed = client.get("/api/choir/", params={"categories": "Entrance,Communion"}).json()

    assert sorted(row["title"] for row in listed) == [
        "Communion hymn",
        "Entrance hymn",
    ]


def test_categories_param_folds_legacy_labels(client, db):
    make_resource(db, "Gloria", "Gloria")
    make_resource(db, "Kyrie", "Kyrie Eleison")
    make_resource(db, "Marian hymn", "Marian")

    listed = client.get("/api/choir/", params={"categories": "Kyrie & Gloria"}).json()

    assert sorted(row["title"] for row in listed) == ["Gloria", "Kyrie"]


def test_categories_param_ignores_unknown_labels(client, db):
    make_resource(db, "Entrance hymn", "Entrance")

    listed = client.get(
        "/api/choir/", params={"categories": "Entrance,Not A Category"}
    ).json()

    assert [row["title"] for row in listed] == ["Entrance hymn"]


def test_categories_param_matches_nothing_when_all_labels_are_unknown(client, db):
    make_resource(db, "Entrance hymn", "Entrance")

    listed = client.get("/api/choir/", params={"categories": "Nope,Also Nope"}).json()

    assert listed == []


def test_categories_param_is_anded_with_the_other_filters(client, db):
    # Every filter narrows. `category` and `categories` both constrain the
    # category column, so supplying both requires a row to carry one label from
    # each -- which no single row can do. Documented rather than unioned so the
    # behaviour is not mistaken for a bug.
    make_resource(db, "Latin entrance", "Entrance", language="Latin")
    make_resource(db, "English entrance", "Entrance")

    listed = client.get(
        "/api/choir/",
        params={"category": "Entrance", "categories": "Communion"},
    ).json()

    assert listed == []


def test_categories_param_combines_with_language(client, db):
    make_resource(db, "Latin entrance", "Entrance", language="Latin")
    make_resource(db, "English entrance", "Entrance")
    make_resource(db, "Latin communion", "Communion", language="Latin")

    listed = client.get(
        "/api/choir/",
        params={"categories": "Entrance,Communion", "language": "Latin"},
    ).json()

    assert sorted(row["title"] for row in listed) == [
        "Latin communion",
        "Latin entrance",
    ]


def test_sort_and_limit_keep_the_existing_filters(client, db):
    make_resource(db, "Latin one", "Latin", download_count=1)
    make_resource(db, "Latin two", "Latin", download_count=9)
    make_resource(db, "English one", "Latin", download_count=50)
    db.commit()

    listed = client.get(
        "/api/choir/",
        params={"sort": "popular", "limit": 1, "query": "Latin two"},
    ).json()

    assert [row["title"] for row in listed] == ["Latin two"]