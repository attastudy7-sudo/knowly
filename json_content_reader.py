#!/usr/bin/env python3
"""
json_content_reader.py
======================
Replaces: pdf_quiz_parser.py, parse_quiz_pdf.py, batch_generate_quizzes.py

This script is the NEW entry point for loading any EduShare academic document
into the database. It reads canonical JSON sidecars — it does not and cannot
read PDFs.

RETIRED COMPONENTS
------------------
The following files are RETIRED and must not be used:

  ❌ pdf_quiz_parser.py           (pdfplumber + regex — fragile, math-blind)
  ❌ parse_quiz_pdf.py            (same approach, different API surface)
  ❌ batch_generate_quizzes.py    (called the above, now superseded)

REPLACEMENT ARCHITECTURE
------------------------
Generation pipeline produces:
  {stem}.json   ← canonical source of truth (this script reads this)
  {stem}.pdf    ← presentation layer only   (never parsed)
  {stem}.tex    ← LaTeX source              (debug/audit only)

WHY PDF PARSING WAS RETIRED
-----------------------------
1. Math rendered as equation objects in Word/LibreOffice PDF output
   becomes rasterized — invisible to any text extraction tool.
2. pdfplumber reconstructs text from glyph coordinates; multi-line
   equations and fractions produce mangled or empty output.
3. Regex patterns on extracted text fail silently when AI varies formatting.
4. The JSON sidecar, produced at generation time, contains the exact same
   content as the PDF — structured, validated, and machine-readable.

Usage:
    python json_content_reader.py <json_path> [--post-id <id>] [--save]
    python json_content_reader.py <json_path> --validate-only
    python json_content_reader.py --scan-folder <folder> --save

Examples:
    python json_content_reader.py notes/Calculus_Quiz_20260222_143022.json
    python json_content_reader.py notes/Calculus_Quiz_20260222_143022.json --post-id 7 --save
    python json_content_reader.py --scan-folder notes/ --save
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

# ── Path setup ────────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(
    level  = logging.INFO,
    format = "%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    datefmt= "%H:%M:%S",
)
logger = logging.getLogger("json_content_reader")


# ── Core imports ──────────────────────────────────────────────────────────────

def _import_core():
    try:
        from core.db_writer         import load_json_sidecar, document_to_db_format, write_document_to_db
        from core.content_validator import validate_document, DocumentValidationError
        return load_json_sidecar, document_to_db_format, write_document_to_db, validate_document, DocumentValidationError
    except ImportError as exc:
        logger.error("Failed to import core modules: %s", exc)
        logger.error(
            "Ensure the core/ directory is present and dependencies are installed:\n"
            "  pip install jsonschema google-genai"
        )
        sys.exit(1)


# ── Single file processing ────────────────────────────────────────────────────

def process_json_file(
    json_path: str,
    post_id: int | None = None,
    save_to_db: bool = False,
    validate_only: bool = False,
    re_validate: bool = True,
) -> dict | None:
    """
    Load, optionally re-validate, and optionally write a JSON sidecar to the DB.

    Args:
        json_path:     Path to the .json sidecar file.
        post_id:       Database post ID (required for --save).
        save_to_db:    If True, write to QuizData (requires Flask context).
        validate_only: If True, only validate and report; do not write DB.
        re_validate:   If True, run validate_document() again on the loaded dict.
                       Set to False to trust the hash in an existing sidecar.

    Returns:
        The DB-format dict, or None if processing failed.
    """
    (
        load_json_sidecar,
        document_to_db_format,
        write_document_to_db,
        validate_document,
        DocumentValidationError,
    ) = _import_core()

    print(f"\n{'─'*60}")
    print(f"  Processing: {json_path}")

    # ── Step 1: Load ──────────────────────────────────────────────────────
    try:
        doc = load_json_sidecar(json_path)
    except (FileNotFoundError, ValueError) as exc:
        logger.error("Load failed: %s", exc)
        return None

    doc_type = doc.get("document_type", "unknown")
    title    = doc.get("title", "unknown")
    print(f"  Type : {doc_type}")
    print(f"  Title: {title}")
    print(f"  Level: {doc.get('level', '?')}")
    print(f"  Hash : {doc.get('document_hash', 'MISSING')[:20]}...")

    # ── Step 2: Re-validate (optional but recommended) ────────────────────
    if re_validate:
        try:
            doc = validate_document(doc)
            print("  ✅ Validation: PASSED")
        except DocumentValidationError as exc:
            print(f"  ❌ Validation: FAILED ({len(exc.errors)} error(s))")
            for err in exc.errors[:10]:
                print(f"     • {err}")
            if validate_only:
                return None
            logger.warning(
                "Continuing despite validation errors (--validate-only not set)."
            )

    if validate_only:
        print("  [validate-only mode — no DB write]")
        return None

    # ── Step 3: Convert to DB format ──────────────────────────────────────
    try:
        db_data = document_to_db_format(doc)
    except Exception as exc:
        logger.error("DB format conversion failed: %s", exc)
        return None

    # ── Step 4: Print summary ─────────────────────────────────────────────
    questions = db_data.get("questions", [])
    print(f"  Items      : {len(questions)}")
    print(f"  Total marks: {db_data.get('total_marks', 0)}")
    print(f"  XP reward  : {db_data.get('xp_reward', 0)}")

    # Pretty-print first item as a sanity check
    if questions:
        first = questions[0]
        q_preview = str(first.get("question", first.get("section_title", "?")))[:80]
        print(f"  First item : {q_preview!r}")

    # ── Step 5: DB write ──────────────────────────────────────────────────
    if save_to_db:
        if post_id is None:
            logger.error("--post-id is required when using --save")
            return db_data

        try:
            write_document_to_db(doc, post_id, json_path=json_path)
            print(f"  ✅ Saved to database for post_id={post_id}")
        except RuntimeError as exc:
            logger.error("DB write failed: %s", exc)
            return db_data

    return db_data


# ── Folder scan ───────────────────────────────────────────────────────────────

def scan_and_process_folder(
    folder: str,
    save_to_db: bool = False,
    validate_only: bool = False,
) -> dict:
    """
    Discover all .json sidecar files in folder and process each one.
    Returns a summary dict.
    """
    folder_path = Path(folder)
    if not folder_path.exists():
        logger.error("Folder not found: %s", folder)
        return {"total": 0, "passed": 0, "failed": 0}

    json_files = sorted(folder_path.glob("*.json"))
    # Exclude state files and schema files
    json_files = [
        f for f in json_files
        if "state" not in f.name and "schema" not in f.name
    ]

    if not json_files:
        print(f"No .json sidecar files found in: {folder}")
        return {"total": 0, "passed": 0, "failed": 0}

    print(f"\nFound {len(json_files)} JSON file(s) in {folder}")
    summary = {"total": len(json_files), "passed": 0, "failed": 0}

    for json_file in json_files:
        result = process_json_file(
            str(json_file),
            post_id=None,
            save_to_db=save_to_db,
            validate_only=validate_only,
        )
        if result is not None:
            summary["passed"] += 1
        else:
            summary["failed"] += 1

    return summary


# ── Print DB-format output ────────────────────────────────────────────────────

def print_db_format(db_data: dict, json_path: str) -> None:
    """Print the DB-format dict to stdout as formatted JSON."""
    print(f"\n{'='*60}")
    print("  DB-FORMAT OUTPUT")
    print(f"  Source: {json_path}")
    print(f"{'='*60}")
    print(json.dumps(db_data, indent=2, ensure_ascii=False))


# ── CLI ────────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Load EduShare canonical JSON sidecars for validation and DB ingestion.\n"
            "Replaces: pdf_quiz_parser.py, parse_quiz_pdf.py, batch_generate_quizzes.py\n"
            "IMPORTANT: PDF files are NEVER read by this tool."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Positional: single file mode
    parser.add_argument(
        "json_path",
        nargs="?",
        help="Path to the .json sidecar file (single file mode)"
    )

    # Folder scan mode
    parser.add_argument(
        "--scan-folder",
        metavar="FOLDER",
        help="Scan a folder for all .json sidecar files and process them"
    )

    # Options
    parser.add_argument(
        "--post-id", type=int,
        help="Database post ID to associate with this document"
    )
    parser.add_argument(
        "--save", "-s", action="store_true",
        help="Write to database (requires --post-id in single file mode)"
    )
    parser.add_argument(
        "--validate-only", action="store_true",
        help="Run validation only; do not convert or write to DB"
    )
    parser.add_argument(
        "--output", "-o",
        help="Write DB-format JSON to this file instead of stdout"
    )
    parser.add_argument(
        "--no-revalidate", action="store_true",
        help="Skip re-validation (trust existing document_hash)"
    )

    args = parser.parse_args()

    # ── Guard against accidental PDF input ────────────────────────────────
    if args.json_path and args.json_path.lower().endswith(".pdf"):
        print(
            "\n[ERROR] You provided a .pdf file path.\n"
            "This tool does NOT read PDF files.\n"
            "PDF parsing has been retired in v2.0.\n\n"
            "To load a document into the database, provide the .json sidecar\n"
            "that was generated alongside the PDF:\n\n"
            f"  Replace: {args.json_path}\n"
            f"  With:    {args.json_path[:-4]}.json\n\n"
            "If no .json sidecar exists, regenerate the document using:\n"
            "  python exam_generator.py\n"
        )
        return 1

    # ── Folder scan mode ──────────────────────────────────────────────────
    if args.scan_folder:
        summary = scan_and_process_folder(
            folder        = args.scan_folder,
            save_to_db    = args.save,
            validate_only = args.validate_only,
        )
        print(f"\n{'='*60}")
        print(f"  SCAN COMPLETE")
        print(f"  Total   : {summary['total']}")
        print(f"  ✅ Passed  : {summary['passed']}")
        print(f"  ❌ Failed  : {summary['failed']}")
        print(f"{'='*60}")
        return 0 if summary["failed"] == 0 else 1

    # ── Single file mode ──────────────────────────────────────────────────
    if not args.json_path:
        parser.print_help()
        return 1

    db_data = process_json_file(
        json_path     = args.json_path,
        post_id       = args.post_id,
        save_to_db    = args.save,
        validate_only = args.validate_only,
        re_validate   = not args.no_revalidate,
    )

    if db_data is None:
        return 1

    # Output DB-format JSON
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(db_data, f, indent=2, ensure_ascii=False)
        print(f"\n✅ DB-format JSON written to: {args.output}")
    else:
        print_db_format(db_data, args.json_path)

    return 0


if __name__ == "__main__":
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
