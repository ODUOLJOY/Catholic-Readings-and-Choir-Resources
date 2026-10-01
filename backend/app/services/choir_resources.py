from pathlib import Path
from urllib.parse import urlparse

from app.core.config import settings
from app.models.choir import ChoirResource


PRIVATE_RESOURCE_PREFIX = "private://"


def local_resource_file(resource: ChoirResource) -> Path | None:
    url_path = urlparse(resource.file_url).path
    private_root = Path(settings.STORAGE_PATH) / "private_media"
    if url_path.startswith("/api/choir/"):
        relative_path = (
            Path("parishes") / str(resource.parish_id) / f"{resource.id}.{resource.file_type}"
            if resource.parish_id is not None
            else Path("resources") / f"{resource.id}.{resource.file_type}"
        )
        path = (private_root / relative_path).resolve()
        root = private_root.resolve()
    elif resource.file_url.startswith(PRIVATE_RESOURCE_PREFIX):
        relative_path = resource.file_url[len(PRIVATE_RESOURCE_PREFIX):]
        path = (private_root / relative_path).resolve()
        root = private_root.resolve()
    else:
        if url_path.startswith("/media/"):
            root = Path("media").resolve()
            path = (root / url_path.removeprefix("/media/")).resolve()
        elif url_path.startswith("/uploads/choir/"):
            root = Path("uploads").resolve()
            path = (root / url_path.removeprefix("/uploads/")).resolve()
        else:
            return None

    if path == root or root not in path.parents:
        return None
    return path
