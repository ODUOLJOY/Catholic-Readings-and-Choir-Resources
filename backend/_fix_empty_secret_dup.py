"""Remove empty duplicate GOOGLE_CLIENT_SECRET lines that override a nonempty value.

Never prints secret values.
"""
from pathlib import Path

path = Path(".env")
lines = path.read_text(encoding="utf-8").splitlines(keepends=True)

nonempty_secret = False
for line in lines:
    stripped = line.strip()
    if not stripped.startswith("GOOGLE_CLIENT_SECRET="):
        continue
    value = stripped.split("=", 1)[1].strip().strip('"').strip("'")
    if value:
        nonempty_secret = True

if not nonempty_secret:
    print("no_nonempty_secret_found_no_changes")
else:
    out = []
    removed = 0
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("GOOGLE_CLIENT_SECRET="):
            value = stripped.split("=", 1)[1].strip().strip('"').strip("'")
            if not value:
                removed += 1
                continue
        out.append(line)
    path.write_text("".join(out), encoding="utf-8")
    print(f"removed_empty_secret_duplicates={removed}")
