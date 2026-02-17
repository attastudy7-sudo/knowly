import sqlite3
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# CONFIGURATION
# ============================================================

SQLITE_DB = 'edushare_dev.db'  # Your local SQLite database

NEON_URL = os.getenv('DATABASE_URL') or input("Paste your Neon DATABASE_URL: ").strip()

# Validate it's a PostgreSQL URL
if not NEON_URL.startswith('postgresql://'):
    print("❌ ERROR: DATABASE_URL must start with postgresql://")
    print(f"   Got: {NEON_URL[:50]}...")
    exit(1)

# ============================================================
# CONNECT TO BOTH DATABASES
# ============================================================

print("\n" + "=" * 60)
print("🔄 Connecting to databases...")
print("=" * 60)

# Connect to local SQLite
try:
    sqlite_conn = sqlite3.connect(SQLITE_DB)
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_cursor = sqlite_conn.cursor()
    print(f"✅ Connected to local SQLite: {SQLITE_DB}")
except Exception as e:
    print(f"❌ Failed to connect to SQLite: {e}")
    exit(1)

# Connect to Neon PostgreSQL
try:
    pg_conn = psycopg2.connect(NEON_URL)
    pg_conn.autocommit = False
    pg_cursor = pg_conn.cursor()
    print("✅ Connected to Neon PostgreSQL!")
except Exception as e:
    print(f"❌ Failed to connect to Neon: {e}")
    exit(1)

# ============================================================
# GET ALL TABLES FROM SQLITE
# ============================================================

sqlite_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
tables = [row[0] for row in sqlite_cursor.fetchall()]

print(f"\n📋 Found {len(tables)} tables in SQLite: {', '.join(tables)}")

# ============================================================
# TYPE CONVERSION HELPERS
# ============================================================

def sqlite_to_pg_type(sqlite_type):
    """Convert SQLite types to PostgreSQL types."""
    sqlite_type = (sqlite_type or '').upper().strip()
    if 'BOOL' in sqlite_type:
        return 'BOOLEAN'
    elif 'INT' in sqlite_type:
        return 'INTEGER'
    elif 'CHAR' in sqlite_type or 'TEXT' in sqlite_type or 'CLOB' in sqlite_type:
        return 'TEXT'
    elif 'BLOB' in sqlite_type or not sqlite_type:
        return 'TEXT'
    elif 'REAL' in sqlite_type or 'FLOA' in sqlite_type or 'DOUB' in sqlite_type:
        return 'FLOAT'
    elif 'DATE' in sqlite_type or 'TIME' in sqlite_type:
        return 'TIMESTAMP'
    else:
        return 'TEXT'

def get_boolean_columns(table_name):
    """Get list of boolean column names for a table."""
    sqlite_cursor.execute(f"PRAGMA table_info({table_name})")
    columns = sqlite_cursor.fetchall()
    bool_cols = []
    for col in columns:
        col_name = col[1]
        col_type = (col[2] or '').upper()
        if 'BOOL' in col_type:
            bool_cols.append(col_name)
    return bool_cols

def convert_row(row, col_names, bool_columns):
    """Convert SQLite row values to PostgreSQL compatible types."""
    converted = []
    for i, val in enumerate(row):
        col_name = col_names[i]
        if col_name in bool_columns and val is not None:
            # Convert SQLite integer (0/1) to Python bool (False/True)
            converted.append(bool(val))
        else:
            converted.append(val)
    return converted

# ============================================================
# MIGRATE EACH TABLE
# ============================================================

total_migrated = 0
total_failed = 0

for table in tables:
    print(f"\n{'=' * 60}")
    print(f">>> Migrating table: {table}")
    print(f"{'=' * 60}")

    # Get columns from SQLite
    sqlite_cursor.execute(f"PRAGMA table_info({table})")
    columns = sqlite_cursor.fetchall()

    if not columns:
        print(f"  ⚠ No columns found for {table}, skipping.")
        continue

    col_definitions = []
    col_names = []
    bool_columns = get_boolean_columns(table)

    if bool_columns:
        print(f"  ℹ Boolean columns detected: {', '.join(bool_columns)}")

    for col in columns:
        col_id, col_name, col_type, not_null, default_val, is_pk = col
        pg_type = sqlite_to_pg_type(col_type)
        col_names.append(col_name)

        if is_pk:
            if pg_type == 'INTEGER':
                col_definitions.append(f'"{col_name}" SERIAL PRIMARY KEY')
            else:
                col_definitions.append(f'"{col_name}" {pg_type} PRIMARY KEY')
        elif not_null:
            if default_val is not None:
                # Convert default boolean values
                if pg_type == 'BOOLEAN':
                    default_val = 'TRUE' if str(default_val) == '1' else 'FALSE'
                col_definitions.append(f'"{col_name}" {pg_type} NOT NULL DEFAULT {default_val}')
            else:
                col_definitions.append(f'"{col_name}" {pg_type}')
        else:
            col_definitions.append(f'"{col_name}" {pg_type}')

    # Drop and recreate table to ensure clean state
    try:
        pg_cursor.execute(f'DROP TABLE IF EXISTS "{table}" CASCADE;')
        pg_conn.commit()
    except Exception as e:
        pg_conn.rollback()

    # Create table in PostgreSQL
    create_sql = f'CREATE TABLE IF NOT EXISTS "{table}" ({", ".join(col_definitions)});'

    try:
        pg_cursor.execute(create_sql)
        pg_conn.commit()
        print(f"  ✅ Table '{table}' created in PostgreSQL")
    except Exception as e:
        pg_conn.rollback()
        print(f"  ❌ Table creation failed: {str(e)[:100]}")
        continue

    # Get data from SQLite
    sqlite_cursor.execute(f"SELECT * FROM {table}")
    rows = sqlite_cursor.fetchall()

    if not rows:
        print(f"  ℹ No data in {table}, skipping.")
        continue

    print(f"  📦 Migrating {len(rows)} rows...")

    success = 0
    failed = 0

    for row in rows:
        row_data = convert_row(list(row), col_names, bool_columns)
        placeholders = ", ".join(["%s"] * len(col_names))
        col_str = ", ".join([f'"{c}"' for c in col_names])
        insert_sql = f'INSERT INTO "{table}" ({col_str}) VALUES ({placeholders}) ON CONFLICT DO NOTHING;'

        try:
            pg_cursor.execute(insert_sql, row_data)
            pg_conn.commit()
            success += 1
        except Exception as e:
            pg_conn.rollback()
            failed += 1
            if failed <= 3:
                print(f"    ✗ Row failed: {str(e)[:100]}")
            elif failed == 4:
                print(f"    ✗ ... more errors suppressed ...")

    print(f"  📊 {success} rows migrated, {failed} failed")
    total_migrated += success
    total_failed += failed

# ============================================================
# DONE
# ============================================================

print("\n" + "=" * 60)
print("✅ MIGRATION COMPLETE!")
print("=" * 60)
print(f"✅ Total rows migrated: {total_migrated}")
print(f"❌ Total rows failed:   {total_failed}")
print("=" * 60)

sqlite_conn.close()
pg_cursor.close()
pg_conn.close()