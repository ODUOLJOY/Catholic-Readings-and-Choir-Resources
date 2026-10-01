from collections.abc import Callable
from pathlib import Path
from urllib.parse import quote, unquote

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import or_
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.staticfiles import StaticFiles

from app.db.database import SessionLocal
from app.models.choir import ChoirResource


class PublicFiles(StaticFiles):
    def __init__(
        self,
        directory: str | Path,
        url_prefix: str,
        session_factory: Callable[[], Session] = SessionLocal,
    ) -> None:
        super().__init__(directory=directory)
        self.url_prefix = url_prefix.rstrip("/")
        self.session_factory = session_factory

    async def get_response(self, path: str, scope):
        decoded_path = unquote(path).replace("\\", "/").lstrip("/")
        resource_path = f"{self.url_prefix}/{decoded_path}"
        encoded_path = quote(resource_path, safe="/:@-._~")
        if await run_in_threadpool(
            self._is_choir_resource_path,
            resource_path,
            encoded_path,
        ):
            raise StarletteHTTPException(status_code=404)
        return await super().get_response(path, scope)

    def _is_choir_resource_path(
        self,
        resource_path: str,
        encoded_path: str,
    ) -> bool:
        with self.session_factory() as db:
            return (
                db.query(ChoirResource.id)
                .filter(
                    or_(
                        ChoirResource.file_url == resource_path,
                        ChoirResource.file_url == encoded_path,
                        ChoirResource.file_url.endswith(resource_path, autoescape=True),
                        ChoirResource.file_url.endswith(encoded_path, autoescape=True),
                    )
                )
                .first()
                is not None
            )
