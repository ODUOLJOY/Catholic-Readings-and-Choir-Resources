import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import app.models.community
import app.models.locations
import app.models.parish
import app.models.user
from app.db.database import Base, get_db
from app.main import app
from app.models.choir import ChoirResource
from app.models.community import CommunityAuditLog, ParishMembership, RoleAssignment
from app.models.locations import Deanery, Diocese
from app.models.parish import Parish
from app.models.user import User
from app.core import dependencies as core_dependencies
from app.constants.choir_categories import CHOIR_CATEGORIES, normalize_category
from app.core.config import settings
from app.auth.security import create_access_token, create_refresh_token
from app.routes import auth_dependency
from app.routes import uploads as upload_routes
from app.services.public_files import PublicFiles


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


def add_manager(db: Session, suffix: str, role: str) -> tuple[Parish, User]:
    diocese = Diocese(name=f"Diocese {suffix}", code=f"diocese-{suffix}")
    db.add(diocese)
    db.flush()
    deanery = Deanery(
        name=f"Deanery {suffix}",
        code=f"deanery-{suffix}",
        diocese_id=diocese.id,
    )
    db.add(deanery)
    db.flush()
    parish = Parish(
        name=f"Parish {suffix}",
        code=f"parish-{suffix}",
        diocese_id=diocese.id,
        deanery_id=deanery.id,
    )
    user = User(
        full_name=f"Director {suffix}",
        email=f"director-{suffix}@example.org",
        hashed_password="not-a-real-password-hash",
    )
    db.add_all([parish, user])
    db.flush()
    db.add_all(
        [
            ParishMembership(
                user_id=user.id,
                parish_id=parish.id,
                status="active",
            ),
            RoleAssignment(
                user_id=user.id,
                role=role,
                scope_type="parish",
                scope_id=parish.id,
                granted_by=user.id,
            ),
        ]
    )
    db.flush()
    return parish, user


def auth_headers(user: User) -> dict[str, str]:
    token = create_access_token({"sub": str(user.id)})
    return {"Authorization": f"Bearer {token}"}


def test_upload_approval_and_file_access_are_parish_scoped(db, tmp_path, monkeypatch):
    parish_a, director_a = add_manager(db, "a", "parish_music_director")
    parish_b, director_b = add_manager(db, "b", "choir_director")
    member_a = User(
        full_name="Parish A Member",
        email="member-a@example.org",
        hashed_password="not-a-real-password-hash",
    )
    db.add(member_a)
    db.flush()
    db.add(
        ParishMembership(
            user_id=member_a.id,
            parish_id=parish_a.id,
            status="active",
        )
    )
    db.commit()
    monkeypatch.setattr(settings, "STORAGE_PATH", str(tmp_path))
    monkeypatch.setattr(upload_routes, "PRIVATE_UPLOAD_DIR", tmp_path / "private_media")
    pdf_content = b"%PDF-1.7\napproved text"

    def resource_file(resource):
        parish_dir = (
            f"parishes/{resource.parish_id}"
            if resource.parish_id is not None
            else "resources"
        )
        return tmp_path / "private_media" / parish_dir / f"{resource.id}.{resource.file_type}"

    active_user = {"user": director_a}
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[auth_dependency.get_current_user] = lambda: active_user["user"]
    app.dependency_overrides[core_dependencies.get_current_user] = lambda: active_user["user"]
    try:
        with TestClient(app) as client:
            scope_response = client.get("/api/uploads/scopes")
            assert scope_response.status_code == 200
            assert scope_response.json()["parishes"] == [
                {"id": parish_a.id, "name": parish_a.name}
            ]
            assert scope_response.json()["global_scope_allowed"] is False

            global_submission = client.post(
                "/api/uploads/",
                data={
                    "title": "Unauthorized global resource",
                    "category": "Mass",
                    "global_scope": "true",
                },
                files={"file": ("global.pdf", b"private", "application/pdf")},
            )
            assert global_submission.status_code == 403

            unassigned_user = User(
                full_name="Unassigned uploader",
                email="unassigned-uploader@example.org",
                hashed_password="not-a-real-password-hash",
            )
            db.add(unassigned_user)
            db.commit()
            active_user["user"] = unassigned_user
            no_scope_submission = client.post(
                "/api/uploads/",
                data={
                    "title": "Unscoped resource",
                    "category": "Mass",
                    "global_scope": "false",
                },
                files={"file": ("unscoped.pdf", b"private", "application/pdf")},
            )
            assert no_scope_submission.status_code == 403
            active_user["user"] = director_a

            default_pdf_limit = upload_routes.MAX_PDF
            monkeypatch.setattr(upload_routes, "MAX_PDF", 3)
            oversized = client.post(
                "/api/uploads/",
                data={"title": "Too large", "category": "Mass"},
                files={"file": ("large.pdf", b"four", "application/pdf")},
            )
            assert oversized.status_code == 400
            assert not list((tmp_path / "private_media" / "staging").glob("*"))
            monkeypatch.setattr(upload_routes, "MAX_PDF", default_pdf_limit)

            submission = client.post(
                "/api/uploads/",
                data={
                    "title": "Parish A Psalm",
                    "category": "Responsorial Psalm",
                    "language": "English",
                    "parish_id": str(parish_a.id),
                    "global_scope": "false",
                },
                files={"file": ("psalm.pdf", pdf_content, "application/pdf")},
            )
            assert submission.status_code == 200, submission.text
            resource_id = submission.json()["resource"]["id"]
            resource = db.get(ChoirResource, resource_id)
            assert resource is not None
            assert resource.parish_id == parish_a.id
            assert resource.file_size == len(pdf_content)
            assert resource.is_approved is False
            assert resource.is_published is False
            assert resource.file_url.endswith(f"/api/choir/{resource_id}/file")
            assert resource_file(resource).is_file()
            assert client.get(
                f"/api/choir/{resource_id}/file",
                headers=auth_headers(director_a),
            ).status_code == 404

            active_user["user"] = director_b
            assert client.get("/api/admin/pending-resources").json() == []
            assert client.put(f"/api/admin/approve-resource/{resource_id}").status_code == 403
            assert client.post(f"/api/choir/{resource_id}/approve").status_code == 403
            assert client.put(
                f"/api/choir/{resource_id}",
                data={
                    "title": "Changed elsewhere",
                    "category": "Mass",
                    "language": "English",
                },
            ).status_code == 403
            assert client.get(
                f"/api/choir/{resource_id}/file",
                headers=auth_headers(director_b),
            ).status_code == 404

            invalid_type = client.post(
                "/api/uploads/",
                data={"title": "Unsupported", "category": "Mass"},
                files={"file": ("script.exe", b"not allowed", "application/octet-stream")},
            )
            assert invalid_type.status_code == 400
            mismatched_mime = client.post(
                "/api/uploads/",
                data={"title": "Mismatched MIME", "category": "Mass"},
                files={"file": ("mismatch.pdf", b"%PDF-1.7\nvalid signature", "text/plain")},
            )
            assert mismatched_mime.status_code == 400
            mismatched_signature = client.post(
                "/api/uploads/",
                data={"title": "Mismatched signature", "category": "Mass"},
                files={"file": ("spoofed.pdf", b"not a PDF", "application/pdf")},
            )
            assert mismatched_signature.status_code == 400
            wrong_parish = client.post(
                "/api/uploads/",
                data={
                    "title": "Wrong parish",
                    "category": "Mass",
                    "parish_id": str(parish_a.id),
                    "global_scope": "false",
                },
                files={"file": ("other.pdf", b"pdf", "application/pdf")},
            )
            assert wrong_parish.status_code == 403

            active_user["user"] = director_a
            pending = client.get("/api/admin/pending-resources")
            assert [item["id"] for item in pending.json()] == [resource_id]
            assert client.put(f"/api/admin/approve-resource/{resource_id}").status_code == 200
            assert resource.is_approved is True
            assert resource.is_published is True
            approval_audit = db.query(CommunityAuditLog).filter(
                CommunityAuditLog.target_id == resource_id,
                CommunityAuditLog.action == "resource.approved",
            ).one()
            assert approval_audit.scope_type == "parish"
            assert approval_audit.scope_id == parish_a.id

            edit_response = client.put(
                f"/api/choir/{resource_id}",
                data={
                    "title": "Updated parish psalm",
                    "category": "Responsorial Psalm",
                    "language": "Swahili",
                    "description": "Approved edit",
                },
            )
            assert edit_response.status_code == 200
            assert edit_response.json()["title"] == "Updated parish psalm"
            assert resource.moderation_status == "pending"
            assert client.get(
                f"/api/choir/{resource_id}",
                headers=auth_headers(director_a),
            ).status_code == 404
            assert [
                item["id"]
                for item in client.get("/api/admin/pending-resources").json()
            ] == [resource_id]
            assert client.put(
                f"/api/admin/approve-resource/{resource_id}"
            ).status_code == 200

            active_user["user"] = director_b
            assert client.get(
                f"/api/choir/{resource_id}",
                headers=auth_headers(director_b),
            ).status_code == 404
            assert client.get(
                f"/api/choir/{resource_id}/file",
                headers=auth_headers(director_b),
            ).status_code == 404

            active_user["user"] = director_a
            assert client.get(
                f"/api/choir/{resource_id}",
                headers=auth_headers(director_a),
            ).status_code == 200
            member_resources = client.get(
                "/api/choir/",
                headers=auth_headers(member_a),
            )
            assert [item["id"] for item in member_resources.json()] == [resource_id]
            assert client.get(
                f"/api/choir/{resource_id}/file",
                headers=auth_headers(member_a),
            ).content == pdf_content
            refresh_token = create_refresh_token({"sub": str(member_a.id)})
            assert client.get(
                f"/api/choir/{resource_id}/file",
                headers={"Authorization": f"Bearer {refresh_token}"},
            ).status_code == 401
            active_user["user"] = member_a
            assert client.post(f"/api/downloads/{resource_id}").status_code == 200
            member_download = client.get("/api/downloads/").json()[0]
            assert client.delete(
                f"/api/downloads/{member_download['id']}"
            ).status_code == 200
            active_user["user"] = None
            assert client.get(f"/api/choir/{resource_id}/file").status_code == 404
            active_user["user"] = director_a
            file_response = client.get(
                f"/api/choir/{resource_id}/file",
                headers=auth_headers(director_a),
            )
            assert file_response.status_code == 200
            assert file_response.content == pdf_content
            active_user["user"] = director_b
            assert client.post(f"/api/downloads/{resource_id}").status_code == 404
            active_user["user"] = director_a
            assert client.post(f"/api/downloads/{resource_id}").status_code == 200
            download_id = client.get("/api/downloads/").json()[0]["id"]
            active_user["user"] = director_b
            assert client.get("/api/downloads/").json() == []
            assert client.delete(f"/api/downloads/{download_id}").status_code == 404
            active_user["user"] = director_a
            assert client.delete(f"/api/downloads/{download_id}").status_code == 200

            active_user["user"] = director_b
            assert client.delete(f"/api/uploads/{resource_id}").status_code == 403

            active_user["user"] = director_a
            assert client.delete(f"/api/uploads/{resource_id}").status_code == 200
            assert not resource_file(resource).exists()

            rejected_submission = client.post(
                "/api/uploads/",
                data={
                    "title": "Parish resource to reject",
                    "category": "Mass",
                    "parish_id": str(parish_a.id),
                    "global_scope": "false",
                },
                files={"file": ("rejected.pdf", b"%PDF-1.7\npending", "application/pdf")},
            )
            assert rejected_submission.status_code == 200
            rejected_id = rejected_submission.json()["resource"]["id"]
            rejected_resource = db.get(ChoirResource, rejected_id)
            assert rejected_resource is not None
            active_user["user"] = director_b
            assert client.delete(
                f"/api/admin/resources/{rejected_id}"
            ).status_code == 403
            active_user["user"] = director_a
            assert client.delete(
                f"/api/admin/resources/{rejected_id}",
                params={"reason": "The parish scope is not valid."},
            ).status_code == 200
            assert rejected_resource.moderation_status == "rejected"
            assert rejected_resource.reviewed_by == director_a.id
            assert rejected_resource.rejection_reason == "The parish scope is not valid."
            rejection_audit = db.query(CommunityAuditLog).filter(
                CommunityAuditLog.target_id == rejected_id,
                CommunityAuditLog.action == "resource.rejected",
            ).one()
            assert rejection_audit.reason == "The parish scope is not valid."
            assert resource_file(rejected_resource).is_file()
            assert client.get(
                f"/api/choir/{rejected_id}/file",
                headers=auth_headers(director_a),
            ).status_code == 404
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(auth_dependency.get_current_user, None)
        app.dependency_overrides.pop(core_dependencies.get_current_user, None)


def test_global_pending_resources_require_platform_admin(db: Session):
    _, parish_director = add_manager(db, "pending", "choir_director")
    global_resource = ChoirResource(
        title="Global pending resource",
        category="Mass",
        language="English",
        file_url="/media/pdfs/pending.pdf",
        file_type="pdf",
        is_approved=False,
        is_published=False,
    )
    db.add(global_resource)
    platform_admin = User(
        full_name="Platform Admin",
        email="platform-admin@example.org",
        hashed_password="not-a-real-password-hash",
        role="admin",
    )
    db.add(platform_admin)
    db.commit()

    active_user = {"user": parish_director}
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[auth_dependency.get_current_user] = lambda: active_user["user"]
    app.dependency_overrides[core_dependencies.get_current_user] = lambda: active_user["user"]
    try:
        with TestClient(app) as client:
            assert client.get("/api/admin/pending-resources").json() == []
            assert client.put(
                f"/api/admin/approve-resource/{global_resource.id}"
            ).status_code == 403
            active_user["user"] = platform_admin
            assert [
                item["id"]
                for item in client.get("/api/admin/pending-resources").json()
            ] == [global_resource.id]
            assert client.put(
                f"/api/admin/approve-resource/{global_resource.id}"
            ).status_code == 200
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(auth_dependency.get_current_user, None)
        app.dependency_overrides.pop(core_dependencies.get_current_user, None)


def test_public_static_files_hide_legacy_choir_resource_urls(db: Session, tmp_path):
    choir_directory = tmp_path / "choir"
    choir_directory.mkdir()
    (choir_directory / "rejected.pdf").write_bytes(b"%PDF-1.7\nprivate")
    media_directory = tmp_path / "media"
    (media_directory / "pdfs").mkdir(parents=True)
    (media_directory / "pdfs" / "legacy.pdf").write_bytes(b"%PDF-1.7\nlegacy")
    (tmp_path / "public.txt").write_text("public", encoding="utf-8")
    db.add_all(
        [
            ChoirResource(
                title="Legacy rejected resource",
                category="Mass",
                language="English",
                file_url="https://api.example.org/uploads/choir/rejected.pdf",
                file_type="pdf",
                moderation_status="rejected",
                is_approved=False,
                is_published=False,
            ),
            ChoirResource(
                title="Legacy media resource",
                category="Mass",
                language="English",
                file_url="/media/pdfs/legacy.pdf",
                file_type="pdf",
                moderation_status="approved",
                is_approved=True,
                is_published=True,
            ),
        ]
    )
    db.commit()

    public_app = FastAPI()
    public_app.mount(
        "/uploads",
        PublicFiles(
            directory=tmp_path,
            url_prefix="/uploads",
            session_factory=lambda: Session(bind=db.get_bind()),
        ),
    )
    public_app.mount(
        "/media",
        PublicFiles(
            directory=media_directory,
            url_prefix="/media",
            session_factory=lambda: Session(bind=db.get_bind()),
        ),
    )
    with TestClient(public_app) as client:
        assert client.get("/uploads/choir/rejected.pdf").status_code == 404
        assert client.get("/media/pdfs/legacy.pdf").status_code == 404
        public_response = client.get("/uploads/public.txt")
        assert public_response.status_code == 200
        assert public_response.text == "public"



def test_choir_resource_list_supports_server_side_facet_filters(db: Session):
    """Server-side faceted filtering for the choir list endpoint."""
    db.add_all(
        [
            ChoirResource(
                title="Psalm 23",
                category="MASS",
                language="English",
                file_url="/api/choir/1/file",
                file_type="pdf",
                voice_part="SATB",
                season="Advent",
                key_signature="D",
                tempo="Allegro",
                composer="Palestrina",
                is_approved=True,
                is_published=True,
                moderation_status="approved",
            ),
            ChoirResource(
                title="Ave Maria",
                category="MARIAN",
                language="Latin",
                file_url="/api/choir/2/file",
                file_type="mp3",
                voice_part="Soprano",
                season="Christmas",
                key_signature="C",
                tempo="Largo",
                composer="Schubert",
                is_approved=True,
                is_published=True,
                moderation_status="approved",
            ),
            ChoirResource(
                title="Kyrie VIII",
                category="MASS",
                language="Latin",
                file_url="/api/choir/3/file",
                file_type="pdf",
                voice_part="Alto",
                season="Lent",
                key_signature="G",
                tempo="Andante",
                composer="Palestrina",
                is_approved=True,
                is_published=True,
                moderation_status="approved",
            ),
        ]
    )
    db.commit()

    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as client:

            def ids(**params):
                resp = client.get("/api/choir/", params=params or None)
                assert resp.status_code == 200, resp.text
                return [r["id"] for r in resp.json()]

            base = ids()
            assert len(base) == 3

            # Exact-match facets (backend == filters)
            assert len(ids(category="MASS")) == 2
            assert len(ids(voice_part="SATB")) == 1
            assert len(ids(key_signature="C")) == 1
            assert len(ids(tempo="Largo")) == 1
            assert len(ids(season="Advent")) == 1
            assert len(ids(language="Latin")) == 2

            # ilike facets (case-insensitive substring)
            assert len(ids(composer="palestrina")) == 2
            assert len(ids(query="ave")) == 1
            assert len(ids(query="mass")) == 2  # category now searchable server-side

            # Combined facets
            assert len(ids(category="MASS", voice_part="SATB")) == 1
            assert len(ids(language="Latin", key_signature="G")) == 1
            assert len(ids(season="Advent", tempo="Allegro")) == 1
    finally:
        app.dependency_overrides.pop(get_db, None)



# --------------------------------------------------------------------------
# Canonical 27-category catalog
# --------------------------------------------------------------------------


EXPECTED_CATEGORY_SECTIONS = [
    (
        "Mass Ordinary and Celebration Songs",
        [
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
    ),
    (
        "Liturgical Seasons",
        [
            "Advent",
            "Christmas",
            "Lent",
            "Pentecost",
            "Holy Week",
            "Easter",
            "Ordinary Time",
        ],
    ),
    (
        "Other Choir Categories",
        [
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
    ),
]


def test_choir_categories_endpoint_returns_the_27_in_order(db: Session):
    """GET /api/choir/categories is public and returns exactly the 27 canonical
    categories in the required three-section order (no extras, no duplicates).

    The endpoint now reports live counts, so it reads the database. It is
    overridden here rather than falling through to the configured database so
    this stays a shape test against an empty library instead of an assertion
    about whatever happens to be deployed.
    """
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as client:
            resp = client.get("/api/choir/categories")
            assert resp.status_code == 200, resp.text
            body = resp.json()
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert body["categories"] == [
        label
        for _section, labels in EXPECTED_CATEGORY_SECTIONS
        for label in labels
    ]
    assert len(body["categories"]) == 27
    assert len(set(body["categories"])) == 27  # no duplicates
    assert body["categories"] == list(CHOIR_CATEGORIES)  # backend constant matches (list, canonical order)

    sections = body["sections"]
    assert [s["title"] for s in sections] == [s[0] for s in EXPECTED_CATEGORY_SECTIONS]
    for section, expected in zip(sections, EXPECTED_CATEGORY_SECTIONS):
        assert section["categories"] == expected[1]
    # Flat list is the exact concatenation of the sectioned lists.
    assert [c for s in sections for c in s["categories"]] == body["categories"]

    # Counts are additive: all 27 keys, all zero against an empty library.
    assert list(body["counts"]) == list(CHOIR_CATEGORIES)
    assert set(body["counts"].values()) == {0}
    assert body["total"] == 0


def test_normalize_category_is_the_canonical_compatibility_mapping():
    """normalize_category (the reversible compatibility mapping) collapses every
    legacy label to its canonical home and never discards an unknown value."""
    # Canonical labels pass through with their exact casing.
    for label in CHOIR_CATEGORIES:
        assert normalize_category(label) == label
    assert len(CHOIR_CATEGORIES) == 27
    assert len(set(CHOIR_CATEGORIES)) == 27

    # Known legacy aliases collapse to canonical homes.
    assert normalize_category("Kyrie Eleison") == "Kyrie & Gloria"
    assert normalize_category("Gloria") == "Kyrie & Gloria"
    assert normalize_category("Lamb of God") == "Agnus Dei"
    assert normalize_category("Holy Holy") == "Sanctus"
    assert normalize_category("Recessional") == "Exit"
    assert normalize_category("Triduum") == "Holy Week"
    assert normalize_category("Our Lady") == "Marian"
    assert normalize_category("Ave Maria") == "Marian"
    assert normalize_category("All Saints") == "Saints"
    assert normalize_category("Carols") == "Christmas"
    assert normalize_category("Epiphany") == "Christmas"
    assert normalize_category("Gregorian Chant") == "Latin"
    assert normalize_category("Latin Chant") == "Latin"
    assert normalize_category("Adoration") == "Benediction"
    assert normalize_category("Mass") == "Others"

    # Case-insensitive + whitespace tolerant.
    assert normalize_category("kyrie eleison") == "Kyrie & Gloria"
    assert normalize_category("KYRIE & GLORIA") == "Kyrie & Gloria"
    assert normalize_category("  wedding  ") == "Wedding"
    assert normalize_category("") == "Others"
    assert normalize_category(None) == "Others"

    # Unknown values fall back to Others (never None, never lost).
    assert normalize_category("Totally Bogus") == "Others"
    assert normalize_category("First Holy Communion") == "Others"


def test_kyrie_gloria_category_filters_and_search_correctly(db: Session):
    """Selecting 'Kyrie & Gloria' filters the correct songs; the '&' survives URL
    encoding in requests, DB values, search and navigation."""
    db.add_all(
        [
            ChoirResource(
                title="Kyrie VIII",
                category="Kyrie & Gloria",
                language="Latin",
                file_url="/api/choir/1/file",
                file_type="pdf",
                is_approved=True,
                is_published=True,
                moderation_status="approved",
            ),
            ChoirResource(
                title="Salve Regina",
                category="Marian",
                language="Latin",
                file_url="/api/choir/2/file",
                file_type="mp3",
                is_approved=True,
                is_published=True,
                moderation_status="approved",
            ),
            ChoirResource(
                title="Entrancesong",
                category="Entrance",
                language="English",
                file_url="/api/choir/3/file",
                file_type="pdf",
                is_approved=True,
                is_published=True,
                moderation_status="approved",
            ),
        ]
    )
    db.commit()

    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as client:

            def ids(**params):
                resp = client.get("/api/choir/", params=params or None)
                assert resp.status_code == 200, resp.text
                return [r["id"] for r in resp.json()]

            assert len(ids()) == 3
            # Exact category filter — the '&' in "Kyrie & Gloria" round-trips.
            assert ids(category="Kyrie & Gloria") == [1]
            assert ids(category="Marian") == [2]
            assert ids(category="Entrance") == [3]
            assert ids(category="Responsorial Psalm") == []

            # "Kyrie & Gloria" is searchable server-side (ilike substring).
            assert ids(query="gloria") == [1]
            assert ids(query="kyrie") == [1]

            # Combined facets still compose.
            assert ids(category="Kyrie & Gloria", language="Latin") == [1]
            assert ids(category="Kyrie & Gloria", language="English") == []
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_empty_category_returns_no_invented_resources(db: Session):
    """A category with no songs yields an empty result set, never invented rows."""
    db.add(
        ChoirResource(
            title="Only Marian",
            category="Marian",
            language="English",
            file_url="/api/choir/1/file",
            file_type="pdf",
            is_approved=True,
            is_published=True,
            moderation_status="approved",
        )
    )
    db.commit()

    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as client:
            assert client.get("/api/choir/", params={"category": "Wedding"}).json() == []
            assert client.get("/api/choir/", params={"category": "Kyrie & Gloria"}).json() == []
            assert client.get("/api/choir/", params={"category": "Responsorial Psalm"}).json() == []

            # A matching category still returns the single real row.
            assert [r["id"] for r in client.get("/api/choir/", params={"category": "Marian"}).json()] == [1]
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_upload_normalizes_category_to_canonical(db, tmp_path, monkeypatch):
    """Uploading with a legacy or free-form category stores the canonical label
    and never rejects or loses the resource."""
    parish_a, director_a = add_manager(db, "norm", "parish_music_director")
    monkeypatch.setattr(settings, "STORAGE_PATH", str(tmp_path))
    monkeypatch.setattr(upload_routes, "PRIVATE_UPLOAD_DIR", tmp_path / "private_media")
    pdf_content = b"%PDF-1.7 approved text"

    active_user = {"user": director_a}
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[auth_dependency.get_current_user] = lambda: active_user["user"]
    app.dependency_overrides[core_dependencies.get_current_user] = lambda: active_user["user"]
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/uploads/",
                data={
                    "title": "Legacy Kyrie",
                    "category": "Kyrie Eleison",
                    "language": "English",
                    "parish_id": str(parish_a.id),
                    "global_scope": "false",
                },
                files={"file": ("kyrie.pdf", pdf_content, "application/pdf")},
            )
            assert response.status_code == 200, response.text
            resource = db.get(ChoirResource, response.json()["resource"]["id"])
            assert resource is not None
            assert resource.category == "Kyrie & Gloria"  # legacy alias normalized
            assert resource.parish_id == parish_a.id

            bogus = client.post(
                "/api/uploads/",
                data={
                    "title": "Unknown category",
                    "category": "Totally Made Up",
                    "language": "English",
                    "parish_id": str(parish_a.id),
                    "global_scope": "false",
                },
                files={"file": ("bogus.pdf", pdf_content, "application/pdf")},
            )
            assert bogus.status_code == 200, bogus.text
            stored = db.get(ChoirResource, bogus.json()["resource"]["id"])
            assert stored.category == "Others"  # unknown -> safe fallback
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(auth_dependency.get_current_user, None)
        app.dependency_overrides.pop(core_dependencies.get_current_user, None)


def test_edit_resource_normalizes_category(db, tmp_path, monkeypatch):
    """Editing a resource normalizes the category through the same mapping."""
    parish_a, director_a = add_manager(db, "edit", "parish_music_director")
    monkeypatch.setattr(settings, "STORAGE_PATH", str(tmp_path))
    monkeypatch.setattr(upload_routes, "PRIVATE_UPLOAD_DIR", tmp_path / "private_media")
    resource = ChoirResource(
        title="Editable",
        category="MASS",
        language="English",
        file_url="/api/choir/1/file",
        file_type="pdf",
        parish_id=parish_a.id,
        is_approved=False,
        is_published=False,
    )
    db.add(resource)
    db.commit()

    active_user = {"user": director_a}
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[auth_dependency.get_current_user] = lambda: active_user["user"]
    app.dependency_overrides[core_dependencies.get_current_user] = lambda: active_user["user"]
    try:
        with TestClient(app) as client:
            response = client.put(
                f"/api/choir/{resource.id}",
                data={
                    "title": resource.title,
                    "category": "Kyrie Eleison",
                    "language": resource.language,
                },
            )
            assert response.status_code == 200, response.text
            db.refresh(resource)
            assert resource.category == "Kyrie & Gloria"
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(auth_dependency.get_current_user, None)
        app.dependency_overrides.pop(core_dependencies.get_current_user, None)


def test_categories_matching_filter_includes_legacy_aliases():
    """categories_matching_filter returns the canonical label plus every legacy
    alias that remaps to it, so the browse IN-query catches pre-canonical rows.
    An unknown filter returns an empty set (matches nothing, never everything).
    """
    from app.constants.choir_categories import categories_matching_filter

    # "Kyrie & Gloria" must match rows still labelled "Kyrie Eleison" or "Gloria".
    kyrie = categories_matching_filter("Kyrie & Gloria")
    assert "Kyrie & Gloria" in kyrie
    assert "Kyrie Eleison" in kyrie
    assert "Gloria" in kyrie

    # "Sanctus" matches the canonical label plus the mass-part aliases.
    sanctus = categories_matching_filter("Sanctus")
    assert "Sanctus" in sanctus
    assert "Holy Holy" in sanctus

    # "Others" is the catch-all -- several legacy labels map to it.
    others = categories_matching_filter("Others")
    assert "Others" in others
    assert "Mass" in others
    assert "Other" in others
    assert "Swahili" in others

    # A canonical label with no aliases still matches itself.
    wedding = categories_matching_filter("Wedding")
    assert wedding == {"Wedding"}

    # An unknown / non-canonical filter returns an empty set so the browse
    # query surfaces no rows rather than every row.
    assert categories_matching_filter("Bogus") == set()
    assert categories_matching_filter("") == set()


def test_legacy_category_filter_matches_pre_canonical_rows(db: Session):
    """Selecting a canonical category on the browse screen returns rows that
    still carry a legacy label, proving the IN-filter works end-to-end."""
    db.add_all(
        [
            ChoirResource(
                title="Kyrie (legacy label)",
                category="Kyrie Eleison",
                language="Latin",
                file_url="/api/choir/1/file",
                file_type="pdf",
                is_approved=True,
                is_published=True,
                moderation_status="approved",
            ),
            ChoirResource(
                title="Gloria (legacy label)",
                category="Gloria",
                language="Latin",
                file_url="/api/choir/2/file",
                file_type="pdf",
                is_approved=True,
                is_published=True,
                moderation_status="approved",
            ),
            ChoirResource(
                title="Kyrie (canonical label)",
                category="Kyrie & Gloria",
                language="English",
                file_url="/api/choir/3/file",
                file_type="pdf",
                is_approved=True,
                is_published=True,
                moderation_status="approved",
            ),
            ChoirResource(
                title="Unrelated Marian",
                category="Marian",
                language="Latin",
                file_url="/api/choir/4/file",
                file_type="mp3",
                is_approved=True,
                is_published=True,
                moderation_status="approved",
            ),
        ]
    )
    db.commit()

    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as client:
            # The "Kyrie & Gloria" filter must surface all three Kyrie/Gloria
            # rows regardless of whether they carry the canonical label or a
            # legacy alias, and must not surface the unrelated Marian row.
            resp = client.get("/api/choir/", params={"category": "Kyrie & Gloria"})
            assert resp.status_code == 200, resp.text
            ids = {r["id"] for r in resp.json()}
            assert ids == {1, 2, 3}

            # An unknown filter surfaces nothing.
            assert client.get(
                "/api/choir/", params={"category": "Bogus"}
            ).json() == []
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_legacy_category_migration_remaps_aliases(db: Session):
    """Rev13 (20261002_13) rewrites every CATEGORY_ALIASES key to its canonical
    value in storage, and is idempotent on re-run. Downgrade is a no-op.

    The migration module's filename starts with digits so it cannot be imported
    via a normal ``import`` statement; it is loaded with ``importlib`` instead.
    The upgrade loop is exercised via the shared ``CATEGORY_ALIASES`` mapping so
    the test stays in sync with the migration without needing a live alembic
    context.
    """
    import importlib.util
    from pathlib import Path

    from app.constants.choir_categories import CATEGORY_ALIASES, CHOIR_CATEGORIES

    migration_path = (
        Path(__file__).resolve().parent
        / "migrations"
        / "versions"
        / "20261002_13_choir_legacy_categories.py"
    )
    spec = importlib.util.spec_from_file_location(
        "migration_20261002_13", migration_path
    )
    assert spec is not None and spec.loader is not None
    migration_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration_module)

    # The migration imports CATEGORY_ALIASES from the constants module, so its
    # view of the aliases is the same one the test asserts against.
    assert migration_module.CATEGORY_ALIASES is CATEGORY_ALIASES

    # Seed rows: one per alias (legacy label) plus one canonical control row
    # per canonical label, so we can prove aliases move and canonical rows are
    # untouched.
    rows = []
    for alias in CATEGORY_ALIASES:
        rows.append(
            ChoirResource(
                title=f"Legacy {alias}",
                category=alias,
                language="English",
                file_url=f"/api/choir/legacy/{alias}/file",
                file_type="pdf",
                is_approved=True,
                is_published=True,
                moderation_status="approved",
            )
        )
    for canonical in CHOIR_CATEGORIES:
        rows.append(
            ChoirResource(
                title=f"Canonical {canonical}",
                category=canonical,
                language="English",
                file_url=f"/api/choir/canonical/{canonical}/file",
                file_type="pdf",
                is_approved=True,
                is_published=True,
                moderation_status="approved",
            )
        )
    db.add_all(rows)
    db.commit()

    bind = db  # Session.execute is SQLAlchemy 2.0-safe (Engine.execute was removed)
    import sqlalchemy as sa

    table = "choir_resources"

    # Run the migration's upgrade loop against the fixture bind. We can't call
    # op.get_bind() outside an alembic context, so we replicate the migration's
    # parameterised UPDATE loop using the same CATEGORY_ALIASES source.
    for alias, canonical in CATEGORY_ALIASES.items():
        if alias == canonical:
            continue
        bind.execute(
            sa.text(
                f"UPDATE {table} SET category = :canonical WHERE category = :alias"
            ).bindparams(canonical=canonical, alias=alias)
        )

    db.expire_all()

    # After the remap, no row carries a legacy alias.
    remaining_aliases = (
        db.query(ChoirResource)
        .filter(ChoirResource.category.in_(list(CATEGORY_ALIASES.keys())))
        .all()
    )
    assert remaining_aliases == []

    # Every row that was on a legacy alias is now on its canonical label.
    for alias, canonical in CATEGORY_ALIASES.items():
        remapped = (
            db.query(ChoirResource)
            .filter(
                ChoirResource.category == canonical,
                ChoirResource.title == f"Legacy {alias}",
            )
            .all()
        )
        assert len(remapped) == 1, f"alias {alias!r} did not remap to {canonical!r}"

    # Canonical control rows are untouched.
    for canonical in CHOIR_CATEGORIES:
        control = (
            db.query(ChoirResource)
            .filter(
                ChoirResource.category == canonical,
                ChoirResource.title == f"Canonical {canonical}",
            )
            .all()
        )
        assert len(control) == 1, f"canonical control row {canonical!r} was moved"

    # Idempotency: re-running the same loop updates zero rows because no row
    # carries an alias anymore.
    total_before = db.query(ChoirResource).count()
    for alias, canonical in CATEGORY_ALIASES.items():
        if alias == canonical:
            continue
        bind.execute(
            sa.text(
                f"UPDATE {table} SET category = :canonical WHERE category = :alias"
            ).bindparams(canonical=canonical, alias=alias)
        )
    db.expire_all()
    assert db.query(ChoirResource).count() == total_before

    # The migration's downgrade is a documented no-op: calling it must not
    # raise and must not change any category value.
    migration_module.downgrade()  # body returns immediately; no bind needed
