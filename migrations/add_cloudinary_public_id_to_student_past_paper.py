"""
Migration: add cloudinary_public_id column to student_past_paper table.

Run once after deploying the updated models.py:
    python migrations/add_cloudinary_public_id_to_student_past_paper.py

Safe to run multiple times — skips silently if the column already exists.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from sqlalchemy import text

app = create_app()

with app.app_context():
    with db.engine.connect() as conn:
        # Check if column already exists
        result = conn.execute(text(
            "SELECT COUNT(*) FROM pragma_table_info('student_past_paper') "
            "WHERE name='cloudinary_public_id'"
        ))
        exists = result.scalar()
        if exists:
            print("Column 'cloudinary_public_id' already exists — nothing to do.")
        else:
            conn.execute(text(
                "ALTER TABLE student_past_paper "
                "ADD COLUMN cloudinary_public_id VARCHAR(300)"
            ))
            conn.commit()
            print("Added 'cloudinary_public_id' column to student_past_paper.")
