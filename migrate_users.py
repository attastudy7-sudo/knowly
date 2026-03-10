"""
migrate_users.py
================
Migrates user accounts from an old Postgres database to a new one.

Usage:
    python migrate_users.py --old OLD_DATABASE_URL --new NEW_DATABASE_URL [--dry-run]

Examples:
    # Preview what would be migrated
    python migrate_users.py \
        --old "postgresql://user:pass@old-host/dbname" \
        --new "postgresql://user:pass@new-host/dbname" \
        --dry-run

    # Run the actual migration
    python migrate_users.py \
        --old "postgresql://user:pass@old-host/dbname" \
        --new "postgresql://user:pass@new-host/dbname"

What it migrates:
    - All rows from the 'profiles' table
    - Skips users that already exist in the new DB (matched by email)
    - Preserves all fields including password hashes, XP, streaks, subscriptions
    - Optionally migrates the 'followers' association table

Requirements:
    pip install psycopg2-binary
"""

import argparse
import sys
from datetime import datetime

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    print("ERROR: psycopg2 not installed. Run: pip install psycopg2-binary")
    sys.exit(1)


# ── Columns to migrate (must match your profiles table) ──────────────────────
PROFILE_COLUMNS = [
    "id",
    "username",
    "email",
    "password_hash",
    "full_name",
    "bio",
    "profile_picture",
    "created_at",
    "is_active",
    "is_admin",
    "school",
    "programme",
    "last_activity_date",
    "current_streak",
    "longest_streak",
    "xp_points",
    "xp_level",
    "xp_title",
    "can_access_all_content",
    "subscription_tier",
    "subscription_start_date",
    "subscription_end_date",
    "free_quiz_attempts",
    "free_quiz_attempts_reset_date",
    "onboarding_skipped",
]


def connect(url: str, label: str):
    """Connect to a Postgres DB, exit on failure."""
    try:
        conn = psycopg2.connect(url)
        conn.autocommit = False
        print(f"  ✓ Connected to {label}")
        return conn
    except Exception as e:
        print(f"  ✗ Could not connect to {label}: {e}")
        sys.exit(1)


def get_existing_emails(cur) -> set:
    cur.execute("SELECT email FROM profiles")
    return {row[0] for row in cur.fetchall()}


def get_existing_usernames(cur) -> set:
    cur.execute("SELECT username FROM profiles")
    return {row[0] for row in cur.fetchall()}


def get_existing_ids(cur) -> set:
    cur.execute("SELECT id FROM profiles")
    return {row[0] for row in cur.fetchall()}


def get_actual_columns(cur, table: str) -> list:
    """Return column names that actually exist in the given table."""
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = %s ORDER BY ordinal_position
    """, (table,))
    return [row[0] for row in cur.fetchall()]


def migrate_users(old_conn, new_conn, dry_run: bool):
    old_cur = old_conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    new_cur = new_conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # ── Detect which columns exist in each DB ─────────────────────────────────
    old_cols = get_actual_columns(old_cur, "profiles")
    new_cols = get_actual_columns(new_cur, "profiles")

    # Only migrate columns that exist in BOTH databases
    cols = [c for c in PROFILE_COLUMNS if c in old_cols and c in new_cols]
    missing_old = [c for c in PROFILE_COLUMNS if c not in old_cols]
    missing_new = [c for c in PROFILE_COLUMNS if c not in new_cols]

    if missing_old:
        print(f"  ⚠ Columns missing in old DB (will use defaults): {missing_old}")
    if missing_new:
        print(f"  ⚠ Columns missing in new DB (will be skipped): {missing_new}")
    print(f"  Migrating {len(cols)} columns: {cols}")

    # ── Fetch all users from old DB ───────────────────────────────────────────
    col_list = ", ".join(cols)
    old_cur.execute(f"SELECT {col_list} FROM profiles ORDER BY id")
    old_users = old_cur.fetchall()
    print(f"\n  Found {len(old_users)} users in old database")

    # ── Check what already exists in new DB ───────────────────────────────────
    existing_emails    = get_existing_emails(new_cur)
    existing_usernames = get_existing_usernames(new_cur)
    existing_ids       = get_existing_ids(new_cur)
    print(f"  Found {len(existing_emails)} users already in new database")

    # ── Categorise users ──────────────────────────────────────────────────────
    to_insert    = []
    skipped      = []
    id_conflicts = []

    for user in old_users:
        email    = user["email"]
        username = user["username"]
        uid      = user["id"]

        if email in existing_emails:
            skipped.append((uid, email, "email already exists"))
        elif username in existing_usernames:
            skipped.append((uid, email, f"username '{username}' already taken"))
        else:
            if uid in existing_ids:
                id_conflicts.append(uid)
            to_insert.append(user)

    print(f"\n  To migrate : {len(to_insert)}")
    print(f"  To skip    : {len(skipped)}")
    if id_conflicts:
        print(f"  ID conflicts (will be re-sequenced): {id_conflicts}")

    if skipped:
        print("\n  Skipped users:")
        for uid, email, reason in skipped:
            print(f"    - [{uid}] {email} — {reason}")

    if dry_run:
        print("\n  DRY RUN — no changes written.")
        if to_insert:
            print("  Would insert:")
            for u in to_insert:
                print(f"    - [{u['id']}] {u['email']} ({u['username']})")
        return []

    if not to_insert:
        print("\n  Nothing to migrate.")
        return []

    # ── Insert users ──────────────────────────────────────────────────────────
    inserted_ids = []   # (old_id, new_id)
    insert_sql = f"""
        INSERT INTO profiles ({col_list})
        VALUES ({', '.join(['%s'] * len(cols))})
        ON CONFLICT (email) DO NOTHING
        RETURNING id
    """

    for user in to_insert:
        values = [user[col] for col in cols]

        # If this user's ID conflicts with an existing row in the new DB,
        # let Postgres auto-assign a new ID by nulling it out.
        if user["id"] in existing_ids:
            cols_no_id = [c for c in cols if c != "id"]
            vals_no_id = [user[c] for c in cols_no_id]
            sql_no_id = f"""
                INSERT INTO profiles ({', '.join(cols_no_id)})
                VALUES ({', '.join(['%s'] * len(cols_no_id))})
                ON CONFLICT (email) DO NOTHING
                RETURNING id
            """
            new_cur.execute(sql_no_id, vals_no_id)
        else:
            new_cur.execute(insert_sql, values)

        row = new_cur.fetchone()
        if row:
            new_id = row[0]
            inserted_ids.append((user["id"], new_id))
            print(f"    ✓ Inserted [{user['id']} → {new_id}] {user['email']}")
        else:
            print(f"    ⚠ Skipped (conflict) [{user['id']}] {user['email']}")

    new_conn.commit()
    print(f"\n  ✓ Committed {len(inserted_ids)} users to new database")
    return inserted_ids


def migrate_followers(old_conn, new_conn, id_map: dict, dry_run: bool):
    """Migrate follow relationships, remapping IDs as needed."""
    old_cur = old_conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    new_cur = new_conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # Check if followers table exists
    new_cur.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = 'followers'
        )
    """)
    if not new_cur.fetchone()[0]:
        print("  followers table not found — skipping.")
        return

    old_cur.execute("SELECT follower_id, followed_id FROM followers")
    rows = old_cur.fetchall()
    print(f"\n  Found {len(rows)} follow relationships")

    if dry_run:
        print("  DRY RUN — skipping followers migration.")
        return

    inserted = 0
    for row in rows:
        follower_id = id_map.get(row["follower_id"], row["follower_id"])
        followed_id = id_map.get(row["followed_id"], row["followed_id"])
        try:
            new_cur.execute("""
                INSERT INTO followers (follower_id, followed_id)
                VALUES (%s, %s) ON CONFLICT DO NOTHING
            """, (follower_id, followed_id))
            inserted += 1
        except Exception as e:
            print(f"    ⚠ Skipped follow {follower_id}→{followed_id}: {e}")
            new_conn.rollback()

    new_conn.commit()
    print(f"  ✓ Migrated {inserted} follow relationships")


def bump_sequence(new_conn):
    """Ensure the profiles id sequence is ahead of the max id to prevent future conflicts."""
    cur = new_conn.cursor()
    cur.execute("SELECT MAX(id) FROM profiles")
    max_id = cur.fetchone()[0] or 0
    cur.execute(f"SELECT setval(pg_get_serial_sequence('profiles', 'id'), {max_id + 1}, false)")
    new_conn.commit()
    print(f"\n  ✓ Sequence bumped to {max_id + 1}")


def main():
    parser = argparse.ArgumentParser(description="Migrate Knowly user accounts between Postgres databases.")
    parser.add_argument("--old", required=True, help="Old database URL (postgresql://...)")
    parser.add_argument("--new", required=True, help="New database URL (postgresql://...)")
    parser.add_argument("--dry-run", action="store_true", help="Preview only — no changes written")
    parser.add_argument("--skip-followers", action="store_true", help="Skip migrating follow relationships")
    args = parser.parse_args()

    print("=" * 60)
    print("  Knowly User Migration")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    print("=" * 60)

    print("\nConnecting...")
    old_conn = connect(args.old, "old database")
    new_conn = connect(args.new, "new database")

    print("\nMigrating users...")
    inserted_ids = migrate_users(old_conn, new_conn, args.dry_run)

    # Build old_id → new_id map for followers remapping
    id_map = {old_id: new_id for old_id, new_id in inserted_ids}

    if not args.skip_followers and not args.dry_run:
        print("\nMigrating follow relationships...")
        migrate_followers(old_conn, new_conn, id_map, args.dry_run)

    if not args.dry_run and inserted_ids:
        bump_sequence(new_conn)

    old_conn.close()
    new_conn.close()

    print("\n" + "=" * 60)
    print(f"  Done. {len(inserted_ids)} users migrated.")
    print("=" * 60)


if __name__ == "__main__":
    main()