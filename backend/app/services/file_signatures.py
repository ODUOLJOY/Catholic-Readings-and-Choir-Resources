"""Content-signature checks for uploaded files.

A filename extension and a client-declared MIME type are both assertions by the
uploader, so neither is evidence about the bytes. Both upload routes accept
whitelisted extensions, and both then serve the stored file back from a mounted
static directory on the application's own origin. Without a content check a
`.jpg` containing HTML is served with ``Content-Type: image/jpeg``; a browser
that sniffs the body executes it, turning the upload directory into stored XSS
that runs with the app's origin.

So every accepted type needs a magic-number check. It lives here, in one place,
because a per-route copy is a security control that silently drifts.
"""

from __future__ import annotations

# Signatures live in the first bytes of a file. 4 KiB is enough for every format
# below, including the RIFF containers that put their real type at offset 8.
SIGNATURE_CHECK_BYTES = 4096


def valid_file_signature(extension: str, header: bytes) -> bool:
    """Return True when ``header`` looks like the format ``extension`` claims.

    ``extension`` may be given with or without the leading dot: one caller uses
    ``Path(...).suffix`` and another uses a bare type name, and both must resolve
    to the same signature table. An extension with no known signature returns
    False: an unknown type is rejected rather than waved through, because the
    allow-lists that call this are supposed to be exhaustive.
    """
    suffix = f".{extension.lower().lstrip('.')}"

    if suffix == ".pdf":
        return header.startswith(b"%PDF-")
    if suffix in {".jpg", ".jpeg"}:
        return header.startswith(b"\xff\xd8\xff")
    if suffix == ".png":
        return header.startswith(b"\x89PNG\r\n\x1a\n")
    if suffix == ".webp":
        return header.startswith(b"RIFF") and header[8:12] == b"WEBP"
    if suffix == ".wav":
        return header.startswith(b"RIFF") and header[8:12] == b"WAVE"
    if suffix == ".mp3":
        return header.startswith(b"ID3") or (
            len(header) >= 2 and header[0] == 0xFF and header[1] & 0xE0 == 0xE0
        )
    if suffix in {".m4a", ".mp4", ".mov"}:
        return len(header) >= 8 and header[4:8] == b"ftyp"
    if suffix == ".aac":
        return len(header) >= 2 and header[0] == 0xFF and header[1] & 0xF6 == 0xF0
    if suffix == ".mkv":
        return header.startswith(b"\x1a\x45\xdf\xa3")
    return False