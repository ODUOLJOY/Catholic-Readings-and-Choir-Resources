from pathlib import Path, PurePosixPath
from typing import BinaryIO

from app.core.config import settings
from app.models.choir import ChoirResource
from app.services.choir_resources import local_resource_file


def resource_storage_key(resource: ChoirResource) -> str:
    scope = f"parishes/{resource.parish_id}" if resource.parish_id is not None else "resources"
    return f"{scope}/{resource.id}.{resource.file_type}"


def _local_path(key: str, root: Path | None = None) -> Path:
    key_path = PurePosixPath(key)
    if key_path.is_absolute() or any(part in {"", ".", ".."} for part in key_path.parts):
        raise ValueError("Invalid private storage key.")
    storage_root = (root or Path(settings.STORAGE_PATH) / "private_media").resolve()
    path = (storage_root / Path(*key_path.parts)).resolve()
    if storage_root not in path.parents:
        raise ValueError("Private storage key escapes the configured storage directory.")
    return path


def _firebase_bucket():
    if not settings.FIREBASE_STORAGE_BUCKET:
        raise RuntimeError(
            "FIREBASE_STORAGE_BUCKET is required when STORAGE_BACKEND=firebase."
        )
    from firebase_admin import storage

    from app.services.firebase import initialize_firebase

    app = initialize_firebase()
    return storage.bucket(
        settings.FIREBASE_STORAGE_BUCKET,
        app=app,
    )


def put_private_file(
    source: Path,
    key: str,
    content_type: str | None,
    local_root: Path | None = None,
) -> None:
    if settings.STORAGE_BACKEND == "local":
        destination = _local_path(key, local_root)
        destination.parent.mkdir(parents=True, exist_ok=True)
        source.replace(destination)
        return

    blob = _firebase_bucket().blob(key)
    blob.upload_from_filename(source, content_type=content_type)
    source.unlink(missing_ok=True)


def open_private_file(key: str) -> BinaryIO:
    if settings.STORAGE_BACKEND == "local":
        return _local_path(key).open("rb")

    blob = _firebase_bucket().blob(key)
    if not blob.exists():
        raise FileNotFoundError("Private resource file not found.")
    return blob.open("rb")


def remove_resource_file(resource: ChoirResource) -> None:
    if resource.storage_key:
        if settings.STORAGE_BACKEND == "firebase":
            blob = _firebase_bucket().blob(resource.storage_key)
            if blob.exists():
                blob.delete()
        else:
            _local_path(resource.storage_key).unlink(missing_ok=True)
        return

    filepath = local_resource_file(resource)
    if filepath is not None:
        filepath.unlink(missing_ok=True)


def open_resource_file(resource: ChoirResource) -> BinaryIO:
    if resource.storage_key:
        return open_private_file(resource.storage_key)

    filepath = local_resource_file(resource)
    if filepath is None:
        raise FileNotFoundError("Resource file path is unavailable.")
    return filepath.open("rb")
