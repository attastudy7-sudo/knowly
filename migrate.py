"""
migrate_faculty.py — Interactively assign faculties to existing programmes.
Run once from project root: python migrate_faculty.py
"""
import sqlite3
import os

DB_PATH = 'knowly.db'

if not os.path.exists(DB_PATH):
    print(f"ERROR: Could not find {DB_PATH} in current directory.")
    print("Make sure you're running this from the project root.")
    exit(1)

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

programmes = cur.execute(
    "SELECT id, name, faculty FROM programme ORDER BY name"
).fetchall()

if not programmes:
    print("No programmes found.")
    exit(0)

known_faculties = []
# Seed with any already-assigned faculties
for p in programmes:
    if p['faculty'] and p['faculty'] not in known_faculties:
        known_faculties.append(p['faculty'])

print("\n" + "="*55)
print("  Faculty Migration — Knowly")
print("="*55)
print(f"  {len(programmes)} programmes to assign\n")
print("  For each programme, either:")
print("  · Type a faculty name and press Enter")
print("  · Type a number to reuse an existing faculty")
print("  · Press Enter with no input to skip\n")
print("="*55 + "\n")

changed = 0

for prog in programmes:
    print(f"Programme : {prog['name']}")
    if prog['faculty']:
        print(f"Current   : {prog['faculty']}")

    if known_faculties:
        print("Faculties :")
        for i, f in enumerate(known_faculties, 1):
            print(f"  [{i}] {f}")

    val = input("Assign    : ").strip()

    if not val:
        print("  → Skipped\n")
        continue

    if val.isdigit():
        idx = int(val) - 1
        if 0 <= idx < len(known_faculties):
            faculty = known_faculties[idx]
        else:
            print("  → Invalid number, skipped\n")
            continue
    else:
        faculty = val

    if faculty not in known_faculties:
        known_faculties.append(faculty)

    cur.execute(
        "UPDATE programme SET faculty = ? WHERE id = ?",
        (faculty, prog['id'])
    )
    changed += 1
    print(f"  → Assigned: {faculty}\n")

conn.commit()
conn.close()

print("="*55)
print(f"  ✅ Done — {changed} programme(s) updated")
print("="*55)

# Print summary
conn2 = sqlite3.connect(DB_PATH)
rows = conn2.execute(
    "SELECT faculty, COUNT(*) as c FROM programme GROUP BY faculty ORDER BY faculty"
).fetchall()
print("\nSummary:")
for row in rows:
    label = row[0] if row[0] else "(unassigned)"
    print(f"  {label}: {row[1]} programme(s)")
conn2.close()