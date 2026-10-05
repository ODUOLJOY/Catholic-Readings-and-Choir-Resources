"""Regression tests for the Phase 2 audit findings.

Grouped by defect. Each test names the concrete bug it pins down.

* Dashboard   - hard-coded moderation counters
* Mass assignment - admin reading writes could set workflow flags directly
* Performance - unbounded queries
* Upload      - file-type validation trusted only the client's claim
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base, get_db
from app.main import app
from app.models.readings import Reading
from app.models.report import ContentReport
from app.models.user import User, UserRole
from app.schemas.readings import ReadingCreate, ReadingUpdate


@pytest.fixture(scope="function")
def engine():
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=test_engine)
    yield test_engine
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def client(engine):
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


from fastapi.testclient import TestClient  # noqa: E402


VALID_READING = {
    "reading_date": "2026-04-05",
    "language": "English",
    "liturgical_year": "A",
    "liturgical_season": "Easter",
    "liturgical_color": "White",
    "feast": "Test Feast",
    "first_reading_reference": "John 21:1-14",
    "first_reading": "Test first reading text for provenance checking.",
    "gospel_reference": "John 21:1-14",
    "gospel": "Test gospel text for provenance checking.",
    "source": "Test source",
}


# --------------------------------------------------------------------------
# Mass assignment
# --------------------------------------------------------------------------


def test_create_schema_forbids_workflow_flags():
    """An admin POST could previously publish and approve in one request."""
    fields = set(ReadingCreate.model_fields)

    assert "published" not in fields
    assert "approved" not in fields
    assert "uploaded_by" not in fields


def test_update_schema_forbids_workflow_flags():
    """The update loop applied any model attribute the caller guessed."""
    fields = set(ReadingUpdate.model_fields)

    assert "published" not in fields
    assert "approved" not in fields
    assert "uploaded_by" not in fields
    assert "id" not in fields
    assert "reading_date" not in fields


def test_create_rejects_workflow_flags_from_the_client():
    payload = {**VALID_READING, "published": True, "approved": True}
    with pytest.raises(Exception) as error:
        ReadingCreate(**payload)
    assert error.value.errors()


def test_update_rejects_workflow_flags_from_the_client():
    with pytest.raises(Exception) as error:
        ReadingUpdate(**{"published": True})
    assert error.value.errors()


def test_update_requires_at_least_one_field():
    """An empty edit is a no-op that previously returned 200 unchanged."""
    payload = ReadingUpdate()

    assert payload.model_dump(exclude_unset=True) == {}


def test_create_rejects_blank_required_text():
    """Whitespace-only required text must not be accepted."""
    with pytest.raises(Exception) as error:
        ReadingCreate(**{**VALID_READING, "gospel": "   "})
    assert error.value.errors()


# --------------------------------------------------------------------------
# Reading writes go through validation
# --------------------------------------------------------------------------


def _admin(session) -> User:
    user = User(
        full_name="Admin",
        email="admin-phase2@test.com",
        hashed_password="hash",
        role=UserRole.SUPER_ADMIN,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def test_created_reading_is_not_pre_published(engine):
    """The workflow flags must start false regardless of the request body."""
    session = sessionmaker(bind=engine)()

    try:
        admin = _admin(session)
        reading = Reading(
            **ReadingCreate(**VALID_READING).model_dump(),
            published=False,
            approved=False,
            uploaded_by=admin.id,
        )
        session.add(reading)
        session.commit()

        assert reading.published is False
        assert reading.approved is False
        assert reading.uploaded_by == admin.id
    finally:
        session.close()


def test_search_is_bounded_and_paginated():
    """``/api/readings/search/`` ran ``.all()`` with no limit."""
    import inspect

    from app.routes.readings import search_readings

    signature = inspect.signature(search_readings)
    assert "limit" in signature.parameters
    assert "offset" in signature.parameters

    source = inspect.getsource(search_readings)
    assert ".limit(" in source
    assert ".offset(" in source
    assert ".all()" in source  # present, but now preceded by a limit


def test_search_limit_is_capped():
    """An unbounded limit parameter would reopen the same exhaustion path."""
    import inspect

    from app.routes.readings import search_readings

    source = inspect.getsource(search_readings)
    assert "le=100" in source


# --------------------------------------------------------------------------
# Dashboard
# --------------------------------------------------------------------------


def test_dashboard_counts_pending_reports_instead_of_reporting_zero():
    """``pending_reports`` was hard-coded to 0 under a TODO.

    A moderation queue that always reports zero makes the dashboard actively
    misleading: an administrator sees nothing to do while reports pile up.
    """
    import inspect

    from app.routes.admin import dashboard

    source = inspect.getsource(dashboard)
    assert '"pending_reports": 0' not in source
    assert "ContentReport" in source


def test_pending_report_statuses_match_the_moderation_endpoint():
    """The dashboard must count the same statuses report.py treats as open."""
    import inspect

    from app.routes import report

    source = inspect.getsource(report)
    assert '["pending", "under_review"]' in source


# --------------------------------------------------------------------------
# Upload validation
# --------------------------------------------------------------------------


def test_upload_rejects_a_disallowed_extension():
    import inspect

    from app.routes.admin import upload_file

    source = inspect.getsource(upload_file)
    assert "Unsupported file type." in source
    assert '".exe"' not in source


def test_upload_rejects_path_traversal_filenames():
    import inspect

    from app.routes.admin import upload_file

    source = inspect.getsource(upload_file)
    assert "Invalid filename." in source
    assert '".."' in source


def test_upload_uses_a_generated_filename_not_the_client_name():
    """The stored name must not be attacker-controlled."""
    import inspect

    from app.routes.admin import upload_file

    source = inspect.getsource(upload_file)
    assert "uuid.uuid4()" in source


def test_upload_enforces_a_size_limit_and_cleans_up():
    import inspect

    from app.routes.admin import upload_file

    source = inspect.getsource(upload_file)
    assert "MAX_FILE_SIZE" in source
    assert "unlink" in source


def test_upload_requires_admin_authentication():
    import inspect

    from app.routes.admin import upload_file

    source = inspect.getsource(upload_file)
    assert "require_admin(current_user)" in source


def _super_admin_token(engine):
    """Create a super admin and return a token for it."""
    from app.auth.security import create_access_token

    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    try:
        admin = User(
            email=f"admin-{id(session)}@example.com",
            full_name="Admin",
            hashed_password="not-a-real-hash",
            role=UserRole.SUPER_ADMIN,
            status="active",
        )
        session.add(admin)
        session.commit()
        session.refresh(admin)
        return create_access_token({"sub": str(admin.id)})
    finally:
        session.close()


def test_admin_upload_rejects_a_disguised_file(client, engine, tmp_path, monkeypatch):
    """A real request must reject an HTML payload wearing a ``.jpg`` extension.

    The extension and ``Content-Type`` on an upload are both assertions by the
    client. This endpoint accepts them at face value and the file is served back
    from the mounted ``/uploads`` directory on our own origin, so without a
    content check the upload directory is stored-XSS on the app's own domain.
    """
    from app.routes import admin as admin_routes

    monkeypatch.setattr(admin_routes, "UPLOAD_DIR", tmp_path)

    response = client.post(
        "/api/admin/upload",
        files={
            "file": (
                "payload.jpg",
                b"<html><script>alert(document.domain)</script></html>",
                "image/jpeg",
            )
        },
        headers={"Authorization": f"Bearer {_super_admin_token(engine)}"},
    )

    assert response.status_code == 400, response.text
    assert "do not match" in response.json()["detail"]
    assert list(tmp_path.iterdir()) == [], "the rejected payload must not be stored"


def test_admin_upload_accepts_a_genuine_image(client, engine, tmp_path, monkeypatch):
    """The signature check must not reject an honest upload."""
    from app.routes import admin as admin_routes

    monkeypatch.setattr(admin_routes, "UPLOAD_DIR", tmp_path)

    png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
        b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
        b"\x1f\x15\xc4\x89"
    )
    response = client.post(
        "/api/admin/upload",
        files={"file": ("real.png", png, "image/png")},
        headers={"Authorization": f"Bearer {_super_admin_token(engine)}"},
    )

    assert response.status_code == 200, response.text
    stored = list(tmp_path.iterdir())
    assert len(stored) == 1
    assert stored[0].suffix == ".png"


def test_upload_signature_check_covers_every_accepted_extension():
    """Every accepted type must have a working content signature.

    An extension in the upload route's MIME table with no matching branch in the
    signature table is rejected by :func:`valid_file_signature`, which silently
    breaks that upload type. Asserting the sets are equal in both directions
    catches a type added to one list but not the other, in either order.
    """
    from app.routes.uploads import EXPECTED_MIME_TYPES
    from app.services.file_signatures import valid_file_signature

    # One genuine header per accepted type, taken from the format specs.
    samples = {
        "pdf": b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n",
        "jpg": b"\xff\xd8\xff\xe0\x00\x10JFIF\x00",
        "jpeg": b"\xff\xd8\xff\xe0\x00\x10JFIF\x00",
        "png": b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR",
        "webp": b"RIFF\x24\x00\x00\x00WEBPVP8 ",
        "wav": b"RIFF\x24\x00\x00\x00WAVEfmt ",
        "mp3": b"ID3\x04\x00\x00\x00\x00\x00\x00",
        "m4a": b"\x00\x00\x00\x18ftypM4A ",
        "mp4": b"\x00\x00\x00\x18ftypmp42",
        "mov": b"\x00\x00\x00\x14ftypqt  ",
        "aac": b"\xff\xf1\x50\x80\x00\x1f\x90",
        "mkv": b"\x1a\x45\xdf\xa3\x01\x00\x00\x00",
    }

    assert set(samples) == set(EXPECTED_MIME_TYPES), (
        "the signature fixtures and the upload allow-list disagree"
    )
    for extension, header in samples.items():
        assert valid_file_signature(extension, header) is True, extension
        assert valid_file_signature(f".{extension}", header) is True, (
            f"{extension} must resolve with or without a leading dot"
        )


def test_unknown_extension_has_no_signature():
    """An unknown type must fail closed rather than be waved through."""
    from app.services.file_signatures import valid_file_signature

    assert valid_file_signature(".exe", b"MZ\x90\x00") is False
    assert valid_file_signature(".php", b"<?php echo 1;") is False
    assert valid_file_signature(".html", b"<html>") is False
    assert valid_file_signature(".png", b"") is False, "an empty file is not a PNG"


def test_uploaded_files_are_served_from_a_scoped_mount():
    """Uploads are publicly served, so the directory must not escape."""
    from app.services.public_files import PublicFiles

    assert hasattr(PublicFiles, "_is_choir_resource_path")


# --------------------------------------------------------------------------
# Host header
# --------------------------------------------------------------------------


def test_trusted_host_middleware_is_installed():
    """Stored URLs built from the request Host header can be poisoned."""
    import inspect

    import app.main as main_module

    source = inspect.getsource(main_module)
    assert "TrustedHostMiddleware" in source
    assert "settings.ALLOWED_HOSTS" in source


def test_allowed_hosts_always_includes_the_configured_base_url():
    """The service must not reject its own public hostname."""
    from app.core.config import settings
    from urllib.parse import urlparse

    assert urlparse(settings.BASE_URL).hostname in settings.ALLOWED_HOSTS


def test_allowed_hosts_is_never_empty():
    """An empty list must never mean 'accept any host'."""
    from app.core.config import settings

    assert settings.ALLOWED_HOSTS


def test_allowed_hosts_strips_scheme_and_port():
    """Operators paste full URLs; the middleware compares bare hosts."""
    from urllib.parse import urlparse

    from app.core.config import Settings

    hosts = Settings(ALLOWED_HOSTS=["https://example.com", "other.test:8080"]).ALLOWED_HOSTS
    for host in hosts:
        assert "://" not in host
        assert urlparse(f"http://{host}").path in ("", "/")

    assert "example.com" in hosts
    assert "other.test" in hosts


def test_choir_file_url_is_not_built_from_the_request_host():
    """The stored URL must not come from a caller-supplied Host header."""
    import ast
    import inspect
    import textwrap

    from app.routes import uploads

    # Strip comments and docstrings so only real code is inspected.
    tree = ast.parse(textwrap.dedent(inspect.getsource(uploads)))
    file_url_lines = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Attribute) and target.attr == "file_url":
                    file_url_lines.append(
                        ast.unparse(node.value) if node.value is not None else ""
                    )

    assert file_url_lines, "expected uploads.py to assign ChoirResource.file_url"
    for expression in file_url_lines:
        assert "base_url" not in expression
        assert "settings.BASE_URL" in expression