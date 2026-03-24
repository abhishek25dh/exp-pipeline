"""
docx_to_paras.py
================
Converts a script.docx into individual para_N.json files.

The docx format expected:
  - Heading 1: video title (skipped)
  - Short line (< 100 chars): section title like "The content alone type." (skipped)
  - Long line: body paragraph text -> becomes para_N

Usage:
  python docx_to_paras.py                          # uses inputs/script.docx, outputs to assets/para/
  python docx_to_paras.py path/to/file.docx        # custom input
  python docx_to_paras.py path/to/file.docx 5      # start numbering from para_5
"""

import sys
import json
import os
from pathlib import Path

try:
    import docx
except ImportError:
    print("ERROR: python-docx not installed. Run: pip install python-docx")
    sys.exit(1)

TITLE_MAX_CHARS = 100   # lines shorter than this are treated as section titles (skipped)
OUTPUT_DIR = Path("assets/para")


def extract_paras(docx_path):
    """Read docx and return list of body paragraph strings (titles stripped out)."""
    doc = docx.Document(docx_path)
    paras = []

    for p in doc.paragraphs:
        text = p.text.strip()

        # Skip blank lines
        if not text:
            continue

        # Skip document headings (Heading 1, Heading 2, etc.)
        if p.style.name.startswith("Heading"):
            continue

        # Short line = section title label — skip it
        if len(text) < TITLE_MAX_CHARS:
            continue

        # Long line = body paragraph
        paras.append(text)

    return paras


def main():
    docx_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("inputs/script.docx")
    start_num = int(sys.argv[2]) if len(sys.argv) > 2 else 1

    if not docx_path.exists():
        print(f"ERROR: File not found: {docx_path}")
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    paras = extract_paras(docx_path)

    if not paras:
        print("No body paragraphs found. Check the docx structure.")
        sys.exit(1)

    print(f"Found {len(paras)} paragraph(s) in {docx_path.name}")
    print()

    for i, text in enumerate(paras):
        para_num = start_num + i
        para_key = f"para_{para_num}"
        out_file = OUTPUT_DIR / f"{para_key}.json"

        data = {para_key: text}

        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

        preview = text[:80] + "..." if len(text) > 80 else text
        print(f"  {out_file}  ({len(text)} chars)")
        print(f"    {preview}")
        print()

    print(f"Done. Wrote para_{start_num}.json to para_{start_num + len(paras) - 1}.json")


if __name__ == "__main__":
    main()
