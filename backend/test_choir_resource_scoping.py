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
