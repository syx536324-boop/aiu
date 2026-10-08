"""Responsibility: extract page-numbered text from a local PDF using pypdf."""
import json
import re
from pathlib import Path
import sys
from pypdf import PdfReader


def extract(source: Path, target: Path) -> dict:
    reader = PdfReader(source)
    if reader.is_encrypted:
        raise ValueError("Encrypted PDFs are not supported.")
    if len(reader.pages) > 120:
        raise ValueError("PDF exceeds the 120-page limit.")
    chunks = ["# PDF extracted text\n\nPlain text extraction; equations, figures and columns may be incomplete. Check the original PDF.\n"]
    characters = 0
    empty_pages = []
    control_characters_removed = 0
    for number, page in enumerate(reader.pages, 1):
        text = page.extract_text() or ""
        cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
        control_characters_removed += len(text) - len(cleaned)
        text = cleaned
        if not text.strip():
            empty_pages.append(number)
        characters += len(text)
        chunks.append(f"\n## Page {number}\n\n{text}\n")
    if characters < 100:
        raise ValueError("No usable text layer; OCR is not installed.")
    temporary = target.with_suffix(".tmp")
    temporary.write_text("\n".join(chunks), encoding="utf-8")
    temporary.replace(target)
    return {"pages": len(reader.pages), "characters": characters, "empty_pages": empty_pages, "control_characters_removed": control_characters_removed, "method": "pypdf text layer; no OCR"}


if __name__ == "__main__":
    print(json.dumps(extract(Path(sys.argv[1]), Path(sys.argv[2]))))
