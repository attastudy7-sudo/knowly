"""
send_launch_emails.py — Bulk launch email sender for Knowly.

Loads all users from the database, renders the HTML template with each
user's name, and sends via the Brevo transactional email API.

Usage:
    python send_launch_emails.py [--dry-run] [--limit N] [--resume-from EMAIL]

Options:
    --dry-run          Print emails that would be sent without actually sending
    --limit N          Only send to the first N users (for testing)
    --resume-from      Skip all users until this email address is reached
                       (useful for resuming a failed run)
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

import requests
from sqlalchemy import create_engine, text

# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────

BREVO_API_KEY       = os.getenv("BREVO_API_KEY", "")
SENDER_EMAIL        = os.getenv("MAIL_DEFAULT_SENDER") or os.getenv("MAIL_USERNAME", "")
SENDER_NAME         = "Alan from Knowly"
DATABASE_URL        = "postgresql://neondb_owner:npg_zmAZr0jWJ7OF@ep-square-dawn-aiofqlj4-pooler.c-4.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
TEMPLATE_PATH       = Path(__file__).parent / "knowly_launch_email.html"
SUBJECT             = "Exams are coming — here's how Knowly can help you prepare fast"
DELAY_BETWEEN_SENDS = 0.35
MAX_RETRIES         = 3


def load_template() -> str:
    if not TEMPLATE_PATH.exists():
        sys.exit(f"[ERROR] Template not found: {TEMPLATE_PATH}")
    return TEMPLATE_PATH.read_text(encoding="utf-8")


def render(template: str, name: str) -> str:
    first = name.strip().split()[0].capitalize() if name.strip() else "there"
    return template.replace("{{ name }}", first)


def fetch_users(limit: int | None = None) -> list[dict]:
    if not DATABASE_URL:
        sys.exit("[ERROR] DATABASE_URL not set in .env")
    engine = create_engine(DATABASE_URL, connect_args={"sslmode": "require"})
    query  = "SELECT email, full_name, username FROM profiles WHERE email IS NOT NULL ORDER BY id ASC"
    if limit:
        query += f" LIMIT {limit}"
    with engine.connect() as conn:
        rows = conn.execute(text(query)).fetchall()
    return [{"email": r[0], "full_name": r[1] or "", "username": r[2] or ""} for r in rows]


def send_email(to_email: str, display_name: str, html: str, dry_run: bool = False) -> bool:
    if dry_run:
        print(f"  [DRY RUN] Would send to {to_email} ({display_name})")
        return True
    if not BREVO_API_KEY:
        sys.exit("[ERROR] BREVO_API_KEY not set in .env")
    if not SENDER_EMAIL:
        sys.exit("[ERROR] MAIL_DEFAULT_SENDER not set in .env")

    payload = {
        "sender":      {"name": SENDER_NAME, "email": SENDER_EMAIL},
        "to":          [{"email": to_email, "name": display_name}],
        "subject":     SUBJECT,
        "htmlContent": html,
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(
                "https://api.brevo.com/v3/smtp/email",
                headers={"api-key": BREVO_API_KEY, "Content-Type": "application/json"},
                json=payload,
                timeout=20,
            )
            if resp.status_code == 201:
                return True
            if resp.status_code in (429, 500, 502, 503, 504):
                wait = 2 ** attempt
                print(f"    [WARN] HTTP {resp.status_code} — retrying in {wait}s ({attempt}/{MAX_RETRIES})")
                time.sleep(wait)
                continue
            print(f"    [FAIL] HTTP {resp.status_code}: {resp.text[:200]}")
            return False
        except requests.RequestException as exc:
            wait = 2 ** attempt
            print(f"    [WARN] Network error: {exc} — retrying in {wait}s")
            time.sleep(wait)
    return False


def main():
    parser = argparse.ArgumentParser(description="Send Knowly launch emails")
    parser.add_argument("--dry-run",     action="store_true")
    parser.add_argument("--limit",       type=int)
    parser.add_argument("--resume-from", type=str)
    args = parser.parse_args()

    template = load_template()

    print("Fetching users from database…")
    users = fetch_users(limit=args.limit)
    print(f"Found {len(users)} user(s).")

    if args.dry_run:
        print("[DRY RUN MODE — no emails will be sent]\n")

    sent = failed = skipped = 0
    resuming = bool(args.resume_from)

    for i, user in enumerate(users, 1):
        email   = user["email"]
        name    = user["full_name"] or user["username"] or "there"
        display = user["full_name"] or user["username"] or email

        if resuming:
            if email.lower() == args.resume_from.lower():
                resuming = False
            else:
                skipped += 1
                continue

        html = render(template, name)
        print(f"[{i}/{len(users)}] {email} ({display})…", end=" ", flush=True)

        ok = send_email(email, display, html, dry_run=args.dry_run)
        if ok:
            print("✓")
            sent += 1
        else:
            print("✗ FAILED")
            failed += 1

        if not args.dry_run:
            time.sleep(DELAY_BETWEEN_SENDS)

    print(f"\n{'─'*50}")
    print(f"Done.  Sent: {sent}  |  Failed: {failed}  |  Skipped: {skipped}")
    if failed:
        print(f"[WARN] Re-run with --resume-from <last_good_email> to retry failures.")


if __name__ == "__main__":
    main()