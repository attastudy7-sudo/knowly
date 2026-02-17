import sqlite3
import libsql_client
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

URL = os.getenv('TURSO_DATABASE_URL')
TOKEN = os.getenv('TURSO_AUTH_TOKEN')

# Validate that credentials exist
if not URL or not TOKEN:
    print("=" * 60)
    print("❌ ERROR: Missing Turso credentials!")
    print("=" * 60)
    print(f"TURSO_DATABASE_URL: {'✓ Found' if URL else '✗ Missing'}")
    print(f"TURSO_AUTH_TOKEN: {'✓ Found' if TOKEN else '✗ Missing'}")
    print("\nPlease check your .env file contains:")
    print("TURSO_DATABASE_URL=libsql://your-database.turso.io")
    print("TURSO_AUTH_TOKEN=eyJhbGci...")
    print("=" * 60)
    exit(1)

# Convert libsql:// to https:// for HTTP mode
if URL.startswith('libsql://'):
    HTTP_URL = URL.replace('libsql://', 'https://')
else:
    HTTP_URL = URL

print("=" * 60)
print("✓ Turso credentials loaded successfully")
print("=" * 60)
print(f"Database URL: {HTTP_URL}")
print(f"Using HTTP mode (more stable)")
print("=" * 60 + "\n")

def migrate():
    local_conn = sqlite3.connect('edushare.db')
    local_cursor = local_conn.cursor()
    
    print("🔄 Connecting to Turso via HTTP...")
    try:
        # Use HTTP mode instead of WebSocket
        remote_client = libsql_client.create_client_sync(
            url=HTTP_URL,
            auth_token=TOKEN
        )
        print("✅ Connected to Turso successfully!\n")
    except Exception as e:
        print(f"❌ Failed to connect to Turso: {e}")
        exit(1)

    # Tables to migrate (in order to respect foreign keys)
    table_map = {
        "user": "profiles",
        "subject": "subject",
        "document": "document",
        "post": "post",
        "comment": "comment",
        "like": "like",
        "purchase": "purchase",
        "notification": "notification",
        "followers": "followers"
    }

    for local_name, remote_name in table_map.items():
        print(f"\n>>> Migrating {local_name} -> {remote_name}")
        
        # 1. Get the local schema
        local_cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{local_name}';")
        result = local_cursor.fetchone()
        if not result:
            print(f"  ⚠ Table {local_name} not found in local database, skipping.")
            continue
            
        create_sql = result[0].replace(f"CREATE TABLE {local_name}", f'CREATE TABLE IF NOT EXISTS "{remote_name}"')
        create_sql = create_sql.replace("REFERENCES user", "REFERENCES profiles")

        # 2. Create the table (with IF NOT EXISTS)
        try:
            remote_client.execute(create_sql)
            print(f"  ✓ Table {remote_name} ready.")
        except Exception as e:
            print(f"  ℹ Table setup: {str(e)[:100]}")

        # 3. Get existing IDs to avoid duplicates
        try:
            # Get column info to find primary key
            local_cursor.execute(f"PRAGMA table_info({local_name})")
            columns = local_cursor.fetchall()
            pk_column = None
            for col in columns:
                if col[5] == 1:  # is primary key
                    pk_column = col[1]
                    break
            
            if pk_column:
                # Check which IDs already exist in remote
                existing_result = remote_client.execute(f'SELECT {pk_column} FROM "{remote_name}"')
                existing_ids = {row[pk_column] for row in existing_result.rows} if existing_result.rows else set()
                print(f"  ℹ Found {len(existing_ids)} existing records in remote database")
            else:
                existing_ids = set()
        except Exception as e:
            print(f"  ⚠ Could not check existing records: {str(e)[:50]}")
            existing_ids = set()

        # 4. Push data
        local_cursor.execute(f"SELECT * FROM {local_name}")
        rows = local_cursor.fetchall()
        
        if rows:
            # Get column names
            local_cursor.execute(f"PRAGMA table_info({local_name})")
            columns = [col[1] for col in local_cursor.fetchall()]
            
            success_count = 0
            skip_count = 0
            fail_count = 0
            
            for row in rows:
                row_id = row[0]  # Assuming first column is the ID
                
                # Skip if already exists
                if row_id in existing_ids:
                    skip_count += 1
                    continue
                
                try:
                    # Build INSERT with column names
                    placeholders = ", ".join(["?"] * len(row))
                    column_names = ", ".join([f'"{col}"' for col in columns])
                    insert_sql = f'INSERT INTO "{remote_name}" ({column_names}) VALUES ({placeholders})'
                    
                    remote_client.execute(insert_sql, list(row))
                    success_count += 1
                    if success_count <= 5:  # Only show first 5
                        print(f"    ✓ Row inserted (ID: {row_id})")
                    elif success_count == 6:
                        print(f"    ✓ ... continuing ...")
                except Exception as e:
                    fail_count += 1
                    error_msg = str(e)[:80]
                    if fail_count <= 3:  # Only show first 3 errors
                        print(f"    ✗ Failed (ID: {row_id}): {error_msg}")
                    elif fail_count == 4:
                        print(f"    ✗ ... more errors suppressed ...")
            
            print(f"  📊 Summary: {success_count} inserted, {skip_count} skipped (already exist), {fail_count} failed")
        else:
            print(f"  ℹ No data to migrate for {local_name}")

    print("\n" + "=" * 60)
    print("✅ Migration completed!")
    print("=" * 60)
    local_conn.close()

if __name__ == "__main__":
    try:
        migrate()
    except KeyboardInterrupt:
        print("\n\n⚠ Migration cancelled by user")
        exit(0)
    except Exception as e:
        print(f"\n\n❌ Migration failed with error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)


"libsql://edushare-attastudy7-sudo.aws-us-west-2.turso.io"