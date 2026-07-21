from datetime import datetime
from uuid import uuid4
import re


# =========================================================
# GENERAL
# =========================================================

def utc_now():
    return datetime.utcnow()


def generate_uuid() -> str:
    return str(uuid4())


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text


# =========================================================
# FILE HELPERS
# =========================================================

def get_file_extension(filename: str) -> str:
    return filename.split(".")[-1].lower()


def is_allowed_image(filename: str) -> bool:
    return get_file_extension(filename) in {
        "jpg",
        "jpeg",
        "png",
        "webp",
    }


def is_allowed_pdf(filename: str) -> bool:
    return get_file_extension(filename) == "pdf"


def is_allowed_audio(filename: str) -> bool:
    return get_file_extension(filename) in {
        "mp3",
        "wav",
        "aac",
        "ogg",
        "m4a",
    }


def is_allowed_video(filename: str) -> bool:
    return get_file_extension(filename) in {
        "mp4",
        "mov",
        "avi",
        "mkv",
        "webm",
    }


# =========================================================
# USER HELPERS
# =========================================================

def normalize_email(email: str) -> str:
    return email.strip().lower()


def full_name(first_name: str, last_name: str) -> str:
    return f"{first_name.strip()} {last_name.strip()}"


# =========================================================
# READING HELPERS
# =========================================================

def reading_title(
    feast: str | None,
    saint: str | None,
    reading_date,
) -> str:

    if feast:
        return feast

    if saint:
        return f"Memorial of {saint}"

    return reading_date.strftime("%A %d %B %Y")


# =========================================================
# API RESPONSE HELPERS
# =========================================================

def success(
    message: str,
    data=None,
):
    return {
        "success": True,
        "message": message,
        "data": data,
    }


def error(message: str):
    return {
        "success": False,
        "message": message,
    }


# =========================================================
# PAGINATION
# =========================================================

def paginate(
    page: int = 1,
    page_size: int = 20,
):
    page = max(page, 1)
    page_size = max(min(page_size, 100), 1)

    skip = (page - 1) * page_size

    return skip, page_size