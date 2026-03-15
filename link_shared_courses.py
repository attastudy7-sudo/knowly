"""
link_shared_courses.py
======================
Reads the shared_courses.csv and creates subject-programme links in the
database for any that don't already exist.  Safe to run multiple times —
existing links are never duplicated or removed.

Usage:
    python link_shared_courses.py [--dry-run]

Options:
    --dry-run   Print what would be linked without touching the database.
"""

import sys
import csv
import io
import os

# ── Inline CSV data ───────────────────────────────────────────────────────────
CSV_DATA = """Course Name,Programmes,Programme Count
Analytical Chemistry,BSc Artificial Chemistry; BSc Chemistry,2
Anatomy and Physiology,BSc Nursing; BSc Optometry; BSc Radiography,3
Animal Science,BSc Agricultural Science; BSc Agriculture,2
Big Data Analytics,BSc Data Analytics; BSc Data Science,2
Biochemistry,BSc Chemistry; BSc Microbiology,2
Broadcast Journalism,BA Communication Studies; BSc Journalism,2
Capstone Project,BSc Data Analytics; BSc Information Technology; BSc Software Engineering,3
Cell Biology,BSc Artificial Life Sciences; BSc Biochemistry; BSc Biology; BSc Biotechnology; BSc Microbiology,5
Chemistry Project,BSc Artificial Chemistry; BSc Chemistry,2
Clinical Nutrition,BSc Human Nutrition; BSc Nutrition and Dietetics,2
Clinical Practice I,BSc Occupational Therapy; BSc Physiotherapy,2
Clinical Psychology,BA Psychology; BSc Psychology,2
Cognitive Psychology,BA Psychology; BSc Psychology,2
Comparative Politics,BA Political Science; BSc Political Science,2
Computer Networks,BSc Computer Science; BSc Cybersecurity,2
Contract Law,BSc Law; LLB Law,2
Control Systems,BSc Electrical & Electronic Engineering; BSc Electrical Engineering,2
Corporate Finance,BSc Accounting; BSc Banking and Finance; BSc Finance,3
Creative Fashion Design,BSc Fashion & Textile Design; BSc Textile and Fashion Design,2
Criminal Law,BSc Criminology and Security Studies; BSc Law; LLB Law,3
Crop Science,BSc Agricultural Science; BSc Agriculture,2
Data Mining,BSc Data Analytics; BSc Data Science,2
Database Systems,BSc Computer Science; BSc Data Science; BSc Software Engineering,3
Destination Management,BSc Tourism Management; BSc Tourism and Events Management,2
Digital Electronics,BSc Electrical & Electronic Engineering; BSc Electrical Engineering,2
Educational Psychology,BSc Education (Mathematics); BSc Education (Science),2
Electronics I,BSc Electrical & Electronic Engineering; BSc Electrical Engineering,2
Energy Systems,BSc Mechanical Engineering; BSc Renewable Energy Engineering,2
Engineering Drawing,BSc Civil Engineering; BSc Mechanical Engineering,2
Engineering Mechanics,BSc Civil Engineering; BSc Mechanical Engineering,2
Engineering Mathematics,BSc Civil Engineering; BSc Electrical Engineering; BSc Mechanical Engineering,3
Entrepreneurship,BSc Accounting; BSc Banking and Finance; BSc Business Administration; BSc Marketing,4
Financial Accounting,BSc Accounting; BSc Banking and Finance,2
Genetics,BSc Biology; BSc Biotechnology; BSc Microbiology,3
Human Physiology,BSc Nursing; BSc Physiotherapy,2
Hydrology,BSc Civil Engineering; BSc Environmental Engineering,2
Industrial Training,BSc Computer Science; BSc Information Technology; BSc Software Engineering,3
Inorganic Chemistry,BSc Chemistry; BSc Chemical Engineering,2
Linear Algebra,BSc Computer Science; BSc Data Science; BSc Mathematics,3
Machine Learning,BSc Computer Science; BSc Data Science,2
Marketing Principles,BSc Business Administration; BSc Marketing,2
Microbiology,BSc Biology; BSc Biotechnology; BSc Microbiology,3
Object Oriented Programming,BSc Computer Science; BSc Information Technology; BSc Software Engineering,3
Operating Systems,BSc Computer Science; BSc Information Technology; BSc Software Engineering,3
Organic Chemistry,BSc Chemistry; BSc Chemical Engineering,2
Pharmacology,BSc Nursing; BSc Physiotherapy,2
Physics I,BSc Computer Science; BSc Engineering; BSc Physics,3
Physics II,BSc Computer Science; BSc Engineering; BSc Physics,3
Probability Theory,BSc Data Science; BSc Mathematics; BSc Statistics,3
Programming Fundamentals,BSc Computer Science; BSc Information Technology; BSc Software Engineering,3
Project Management,BSc Business Administration; BSc Computer Science; BSc Information Technology; BSc Software Engineering,4
Research Methods,BSc Political Science; BSc Psychology; BSc Sociology,3
Software Engineering,BSc Computer Science; BSc Software Engineering,2
Statistical Inference,BSc Data Science; BSc Statistics,2
Structural Analysis,BSc Civil Engineering; BSc Structural Engineering,2
Thermodynamics,BSc Chemical Engineering; BSc Mechanical Engineering,2
Web Development,BSc Computer Science; BSc Information Technology; BSc Software Engineering,3
Calculus,BSc Mathematics; BSc Physics; BSc Electrical Engineering; BSc Mechanical Engineering; BSc Civil Engineering; BSc Chemical Engineering; BSc Computer Science,7
Introduction to Statistics,BSc Mathematics; BSc Data Science; BSc Data Analytics; BSc Actuarial Science; BSc Statistics; BSc Economics,6
Discrete Mathematics,BSc Computer Science; BSc Software Engineering; BSc Data Science; BSc Mathematics; BSc Artificial Intelligence; BSc Cybersecurity,6
Data Structures and Algorithms,BSc Computer Science; BSc Software Engineering; BSc Information Technology; BSc Data Science; BSc Artificial Intelligence,5
Numerical Methods,BSc Mathematics; BSc Civil Engineering; BSc Mechanical Engineering; BSc Chemical Engineering; BSc Electrical Engineering,5
Microeconomics,BSc Economics; BSc Business Administration; BSc Banking and Finance; BSc Accounting; BSc Finance; BSc International Business; BSc Marketing,7
Macroeconomics,BSc Economics; BSc Business Administration; BSc Banking and Finance; BSc Accounting; BSc Finance; BSc International Business,6
Business Law,BSc Business Administration; BSc Marketing; BSc Banking and Finance; BSc Accounting; BSc Supply Chain Management; BSc International Business,6
Accounting Principles,BSc Business Administration; BSc Banking and Finance; BSc Finance; BSc Marketing; BSc Supply Chain Management,5
Human Resource Management,BSc Business Administration; BSc Banking and Finance; BSc Accounting; BSc Hospitality Management; BSc Supply Chain Management,5
Technical Writing,BSc Computer Science; BSc Software Engineering; BSc Information Technology; BSc Data Science; BSc Electrical Engineering; BSc Mechanical Engineering; BSc Civil Engineering,7
Academic Writing,BSc Psychology; BSc Political Science; BSc Sociology; BSc Law; BSc Communication Studies; BSc Education (Mathematics); BSc Education (Science),7
Environmental Science,BSc Agriculture; BSc Civil Engineering; BSc Petroleum Engineering; BSc Environmental Engineering; BSc Urban and Regional Planning; BSc Agricultural Science,6"""

DRY_RUN = "--dry-run" in sys.argv

# ── Bootstrap Flask app ───────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from app import create_app, db
from app.models import Subject, Programme

app = create_app()

def normalise(name: str) -> str:
    """Lower-case and strip for fuzzy matching."""
    return name.strip().lower()


with app.app_context():
    # ── Build lookup maps ─────────────────────────────────────────────────────
    all_subjects   = Subject.query.all()
    all_programmes = Programme.query.all()

    subject_map   = {normalise(s.name): s for s in all_subjects}
    programme_map = {normalise(p.name): p for p in all_programmes}

    # ── Parse CSV ─────────────────────────────────────────────────────────────
    reader = csv.DictReader(io.StringIO(CSV_DATA.strip()))

    added   = 0
    skipped = 0
    missing_subjects   = []
    missing_programmes = []

    for row in reader:
        course_name    = row["Course Name"].strip()
        programme_names = [p.strip() for p in row["Programmes"].split(";")]

        subject = subject_map.get(normalise(course_name))
        if not subject:
            missing_subjects.append(course_name)
            continue

        existing_prog_ids = {p.id for p in subject.programmes.all()}

        for prog_name in programme_names:
            programme = programme_map.get(normalise(prog_name))
            if not programme:
                missing_programmes.append(f"{course_name} → {prog_name}")
                continue

            if programme.id in existing_prog_ids:
                skipped += 1
                print(f"  SKIP   {course_name} ↔ {prog_name} (already linked)")
            else:
                added += 1
                print(f"  {'(DRY) ' if DRY_RUN else ''}ADD    {course_name} ↔ {prog_name}")
                if not DRY_RUN:
                    subject.programmes.append(programme)
                    existing_prog_ids.add(programme.id)

    if not DRY_RUN and added > 0:
        db.session.commit()

    # ── Summary ───────────────────────────────────────────────────────────────
    print()
    print("=" * 60)
    print(f"  Links added  : {added}")
    print(f"  Already exist: {skipped}")

    if missing_subjects:
        print(f"\n  Subjects not found in DB ({len(missing_subjects)}):")
        for s in missing_subjects:
            print(f"    - {s}")

    if missing_programmes:
        print(f"\n  Programmes not found in DB ({len(missing_programmes)}):")
        for p in missing_programmes:
            print(f"    - {p}")

    if DRY_RUN:
        print("\n  DRY RUN — no changes written to the database.")
    else:
        print("\n  Done. All changes committed.")
    print("=" * 60)