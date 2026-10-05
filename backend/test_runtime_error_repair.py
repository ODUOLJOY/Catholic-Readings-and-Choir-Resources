"""Regression tests for the reported production runtime failures.

Covered defects
---------------
1. An unprovisioned database made every table-backed route return HTTP 500,
   because no Alembic revision in this repository creates the baseline schema and
   ``backend/render.yaml`` never ran a migration (``AUTO_CREATE_TABLES=false``).
2. Those 500s reached the browser as *CORS errors*, because an unhandled
   exception never passes through ``CORSMiddleware`` and so carried no
   ``Access-Control-Allow-Origin`` header, while the preflight for the same route
   succeeded. The real cause was invisible to the browser.
3. ``CORS_ORIGINS`` was accepted by the settings model but never read by the
   application, and a comma-separated value crashed the process at import time
   inside pydantic-settings before the validator could run.
4. ``bootstrap_schema()`` must be safe to run on every deploy.

No real credentials, tokens or secrets are asserted on, and no production
service is contacted: every test runs against a local SQLite database.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.constants.choir_categories import CHOIR_CATEGORIES
from app.db.database import Base, get_db
from app.main import app
from app.services import schema_bootstrap
from app.services.schema_bootstrap import SchemaBootstrapError

ALLOWED_ORIGIN = "http://localhost:8081"
DISALLOWED_ORIGIN = "https://not-allowed.example.com"


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------


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
    # raise_server_exceptions=False exercises the application's own unhandled
    # exception handler, which is the path the browser actually received.
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# --------------------------------------------------------------------------
# 1. Schema provisioning
# --------------------------------------------------------------------------


def _temp_database(tmp_path, monkeypatch) -> object:
    """Point both the application engine and Alembic at a throwaway file database.

    ``migrations/env.py`` reads ``settings.DATABASE_URL`` when it runs, so both
    have to be redirected or the assertions would run against -- and write to --
    the configured development database.
    """
    url = f"sqlite:///{tmp_path / 'bootstrap.db'}"
    from app.core.config import settings

    monkeypatch.setattr(settings, "DATABASE_URL", url)
    target = create_engine(url)
    monkeypatch.setattr("app.db.database.engine", target, raising=False)
    return target


def test_bootstrap_creates_schema_when_database_is_empty(tmp_path, monkeypatch):
    target = _temp_database(tmp_path, monkeypatch)

    action = schema_bootstrap.bootstrap_schema()

    assert action == "created-and-stamped"
    tables = set(inspect(target).get_table_names())
    # The tables the failing routes actually query.
    assert {"users", "liturgical_days", "choir_resources", "parishes", "readings"} <= tables
    with target.connect() as connection:
        stamped = connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar()
    assert stamped is not None, "A freshly created schema must be stamped, not left unmarked"


def test_bootstrap_is_idempotent_on_second_run(tmp_path, monkeypatch):
    target = _temp_database(tmp_path, monkeypatch)

    first = schema_bootstrap.bootstrap_schema()
    second = schema_bootstrap.bootstrap_schema()

    assert first == "created-and-stamped"
    assert second == "upgraded"
    tables = set(inspect(target).get_table_names())
    assert {"users", "liturgical_days", "choir_resources"} <= tables


def test_bootstrap_refuses_partially_provisioned_database(tmp_path, monkeypatch):
    target = _temp_database(tmp_path, monkeypatch)
    with target.connect() as connection:
        # A stray table that is *not* the application schema.
        connection.execute(text("CREATE TABLE unrelated (id INTEGER PRIMARY KEY)"))
        connection.commit()

    with pytest.raises(SchemaBootstrapError) as excinfo:
        schema_bootstrap.bootstrap_schema()

    assert "partially provisioned" in str(excinfo.value)


def test_check_reports_empty_database_without_creating_anything(tmp_path, monkeypatch):
    """Startup validation must never provision the schema it is validating.

    An implicit ``create_all`` on boot is an unreviewed production migration that
    runs on every deploy, so the start command uses the read-only ``--check``
    path and provisioning stays an explicit, separately approved step.
    """
    target = _temp_database(tmp_path, monkeypatch)

    with pytest.raises(SchemaBootstrapError) as excinfo:
        schema_bootstrap.check_schema()

    assert "No application schema found" in str(excinfo.value)
    assert "python -m app.services.schema_bootstrap" in str(excinfo.value)

    inspector_names = inspect(target).get_table_names()
    assert inspector_names == []


def test_check_succeeds_on_a_provisioned_database(tmp_path, monkeypatch):
    target = _temp_database(tmp_path, monkeypatch)
    schema_bootstrap.bootstrap_schema()

    assert schema_bootstrap.check_schema() == "ready"
    assert "users" in inspect(target).get_table_names()


def test_check_reports_a_partially_provisioned_database(tmp_path, monkeypatch):
    target = _temp_database(tmp_path, monkeypatch)
    with target.connect() as connection:
        connection.execute(text("CREATE TABLE unrelated (id INTEGER PRIMARY KEY)"))
        connection.commit()

    with pytest.raises(SchemaBootstrapError) as excinfo:
        schema_bootstrap.check_schema()

    assert "partially provisioned" in str(excinfo.value)


def test_render_start_command_does_not_mutate_the_schema():
    """The deployed start command must be read-only."""
    from pathlib import Path

    import yaml

    render_path = Path(__file__).resolve().parent / "render.yaml"
    config = yaml.safe_load(render_path.read_text(encoding="utf-8"))
    start_command = config["services"][0]["startCommand"]

    assert "--check" in start_command
    # No implicit migration between the server start and Uvicorn.
    bare_bootstrap = "app.services.schema_bootstrap &&"
    assert bare_bootstrap not in start_command
    assert "alembic" not in start_command


# --------------------------------------------------------------------------
# 2. CORS on unhandled 500s
# --------------------------------------------------------------------------


def test_unhandled_500_still_carries_cors_headers(client, engine):
    """A server error must not be reported to the browser as a CORS failure."""
    with engine.connect() as connection:
        connection.execute(text("DROP TABLE liturgical_days"))
        connection.commit()

    response = client.get("/api/v1/liturgy/today", headers={"Origin": ALLOWED_ORIGIN})

    assert response.status_code == 500
    # The browser hides the real status unless this header is present.
    assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN
    # A readable body instead of the bare "Internal Server Error" text.
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {"detail": "Internal server error."}


def test_disallowed_origin_gets_no_cors_header(client):
    response = client.options(
        "/api/choir/",
        headers={
            "Origin": DISALLOWED_ORIGIN,
            "Access-Control-Request-Method": "GET",
        },
    )

    assert "access-control-allow-origin" not in response.headers


# --------------------------------------------------------------------------
# 3. CORS configuration
# --------------------------------------------------------------------------


def test_preflight_advertises_allowed_origin_and_credentials(client):
    response = client.options(
        "/api/choir/",
        headers={
            "Origin": ALLOWED_ORIGIN,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN
    assert response.headers["access-control-allow-credentials"] == "true"
    assert "GET" in response.headers["access-control-allow-methods"]
    assert "authorization" in response.headers["access-control-allow-headers"]


def test_commaseparated_origins_are_accepted():
    """A comma-separated value previously raised inside pydantic-settings."""
    from app.core.config import Settings

    settings = Settings(CORS_ORIGINS="https://a.example.com, https://b.example.com")

    assert "https://a.example.com" in settings.ALLOWED_ORIGINS
    assert "https://b.example.com" in settings.ALLOWED_ORIGINS


def test_json_array_origins_are_accepted():
    from app.core.config import Settings

    settings = Settings(ALLOWED_ORIGINS='["https://c.example.com"]')

    assert "https://c.example.com" in settings.ALLOWED_ORIGINS


def test_deployed_frontend_origin_is_allowed_by_default():
    from app.core.config import Settings

    settings = Settings()

    assert "https://stellular-clafoutis-ad641c.netlify.app" in settings.ALLOWED_ORIGINS
    assert "http://localhost:8081" in settings.ALLOWED_ORIGINS


def test_preflight_from_shifted_loopback_port_is_allowed(client):
    """The reported failure: the dev server moved to port 8082.

    Expo takes the next free port when the previous one is busy, so the local
    origin is not a fixed value. The allow-list pinned 8081, and the preflight
    for 8082 was answered with no ``Access-Control-Allow-Origin`` header, which
    the browser reported as a CORS fault on every login and registration.
    """
    shifted_origin = "http://localhost:8082"

    response = client.options(
        "/api/auth/login",
        headers={
            "Origin": shifted_origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == shifted_origin
    assert response.headers["access-control-allow-credentials"] == "true"
    assert "POST" in response.headers["access-control-allow-methods"]


def test_loopback_is_accepted_on_an_arbitrary_port(client):
    """A higher port must work too, so the next conflict is not a new outage."""
    origin = "http://127.0.0.1:53211"

    response = client.options(
        "/api/auth/login",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin


def test_loopback_lookalike_hosts_are_still_rejected(client):
    """The loopback allowance must not extend to hostnames that merely start
    with ``localhost``, which would let a remote site read credentialed
    responses by registering a similar name."""
    for origin in (
        "https://localhost.attacker.example",
        "https://notlocalhost:8082",
        "http://localhost:8082@attacker.example",
    ):
        response = client.options(
            "/api/auth/login",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
            },
        )

        assert "access-control-allow-origin" not in response.headers, origin


def test_unhandled_500_carries_cors_headers_for_shifted_loopback(client, engine):
    """The error handler must accept the same origins as CORSMiddleware.

    If these two disagreed, a preflight would succeed and the subsequent 500
    would still be reported by the browser as a CORS fault, hiding the real
    server error.
    """
    with engine.connect() as connection:
        connection.execute(text("DROP TABLE liturgical_days"))
        connection.commit()

    shifted_origin = "http://localhost:8082"
    response = client.get(
        "/api/v1/liturgy/today",
        headers={"Origin": shifted_origin},
    )

    assert response.status_code == 500
    assert response.headers["access-control-allow-origin"] == shifted_origin
    assert response.headers["access-control-allow-credentials"] == "true"


def test_allowed_origin_helper_matches_middleware_policy():
    from app.core.config import is_allowed_origin

    allowed = ["https://stellular-clafoutis-ad641c.netlify.app"]

    assert is_allowed_origin("https://stellular-clafoutis-ad641c.netlify.app", allowed)
    assert is_allowed_origin("http://localhost:8082", allowed)
    assert is_allowed_origin("http://localhost:8082/", allowed)
    assert not is_allowed_origin("https://attacker.example", allowed)
    assert not is_allowed_origin("*", allowed)
    assert not is_allowed_origin(None, allowed)


def test_wildcard_origin_is_never_echoed_back():
    """``allow_credentials=True`` plus ``*`` is rejected by browsers.

    A wildcard must therefore never reach the CORS middleware, or every request
    from the deployed frontend fails while looking like a server problem.
    """
    import app.main as main_module

    assert "*" not in main_module._allowed_origins
    assert main_module._allowed_origins, "No usable origin would break the deployed frontend"


# --------------------------------------------------------------------------
# 5. The health check that stayed green during the outage
# --------------------------------------------------------------------------


def test_health_reports_healthy_on_provisioned_schema(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["database"] == "connected"


def test_health_fails_when_schema_is_missing(client, engine):
    """`SELECT 1` succeeds on an empty database, which hid the outage.

    A schema-less deployment served 500s from every route while `/health` -- the
    path Render watches -- kept returning 200, so nothing restarted or alerted.
    """
    with engine.connect() as connection:
        connection.execute(text("DROP TABLE choir_resources"))
        connection.commit()

    response = client.get("/health")

    assert response.status_code == 503
    assert "schema" in response.json()["detail"]


def test_health_failure_is_visible_to_the_browser(client, engine):
    with engine.connect() as connection:
        connection.execute(text("DROP TABLE choir_resources"))
        connection.commit()

    response = client.get("/health", headers={"Origin": ALLOWED_ORIGIN})

    assert response.status_code == 503
    assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN


# --------------------------------------------------------------------------
# 6. The routes that were returning 500
# --------------------------------------------------------------------------


def test_liturgy_today_succeeds_on_provisioned_schema(client):
    response = client.get("/api/v1/liturgy/today")

    assert response.status_code == 200
    payload = response.json()
    assert payload["verification_status"] in {"unverified", "verified"}
    # An empty database must produce an honest empty response, not invented text.
    assert isinstance(payload["readings"], list)


def test_liturgy_specific_date_succeeds_on_provisioned_schema(client):
    response = client.get("/api/v1/liturgy/date/2026-10-04")

    assert response.status_code == 200
    assert response.json()["date"] == "2026-10-04"


def test_choir_index_succeeds_on_provisioned_schema(client):
    response = client.get("/api/choir/")

    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.parametrize("category", CHOIR_CATEGORIES)
def test_every_choir_category_succeeds_on_provisioned_schema(client, category):
    response = client.get("/api/choir/", params={"category": category})

    assert response.status_code == 200
    assert isinstance(response.json(), list)