import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import app.models.content
import app.models.community
import app.models.locations
import app.models.parish
import app.models.user
from app.db.database import Base, get_db
from app.main import app
from app.models.content import Content


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


def test_public_content_detail_hides_unpublished_drafts(db: Session):
    published = Content(
        title="Published content",
        body="Public text",
        content_type="announcement",
        language="English",
        is_published=True,
    )
    draft = Content(
        title="Unpublished draft",
        body="Private draft text",
        content_type="announcement",
        language="English",
        is_published=False,
    )
    db.add_all([published, draft])
    db.commit()

    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as client:
            published_response = client.get(f"/api/content/{published.id}")
            draft_response = client.get(f"/api/content/{draft.id}")

        assert published_response.status_code == 200
        assert published_response.json()["body"] == "Public text"
        assert draft_response.status_code == 404
        assert draft_response.json()["detail"] == "Content not found."
    finally:
        app.dependency_overrides.pop(get_db, None)
