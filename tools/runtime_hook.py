"""
PyInstaller runtime hook that handles base_library.zip extraction.

On company-managed Windows machines, security software may encrypt ZIP files,
breaking PyInstaller's ability to import stdlib modules from base_library.zip.
This hook:
  1. Finds every base_library.zip (or other .zip) entry in sys.path.
  2. Extracts it to a sibling ``<name>_extracted/`` directory if not already present.
  3. Replaces the zip entry in sys.path with the extracted directory.

This way imports always come from raw .pyc files, never from a zip.
"""

import sys
import zipfile
from pathlib import Path


def _extract_and_replace() -> None:
    new_entries: list[str] = []
    zip_entries: list[str] = []

    for entry in sys.path:
        p = Path(entry)
        if p.suffix.lower() != ".zip":
            continue
        extracted = p.parent / f"{p.stem}_extracted"
        if not extracted.is_dir():
            try:
                with zipfile.ZipFile(p, "r") as zf:
                    zf.extractall(extracted)
            except (zipfile.BadZipFile, OSError, EOFError):
                continue
        if extracted.is_dir():
            new_entries.append(str(extracted))
            zip_entries.append(entry)

    for entry in zip_entries:
        sys.path.remove(entry)
    for entry in new_entries:
        sys.path.insert(0, entry)


_extract_and_replace()
