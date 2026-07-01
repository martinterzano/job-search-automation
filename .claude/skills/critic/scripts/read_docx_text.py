"""
read_docx_text.py — Extracts plain text from a .docx file.

Usage:
    python read_docx_text.py <path_to_docx>

Output: plain text to stdout, paragraphs separated by blank lines.
Used by the critic skill to read cover_letter_*.docx content.
"""

import sys
from pathlib import Path

try:
    from docx import Document
except ImportError:
    print("ERROR: python-docx not installed. Run: pip install python-docx", file=sys.stderr)
    sys.exit(1)


def extract_text(docx_path: str) -> str:
    doc = Document(docx_path)
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n\n".join(paragraphs)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python read_docx_text.py <path_to_docx>", file=sys.stderr)
        sys.exit(1)

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"ERROR: File not found: {path}", file=sys.stderr)
        sys.exit(1)

    print(extract_text(str(path)))
