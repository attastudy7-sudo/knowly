 Completed
EduShare — Bug Fixes

BUG-01: _compute_section_marks dead code — PS marks always 0
BUG-02: free_attempts_left None crash + @property commit side-effect + direct decrement bypass
BUG-03: grade_quiz() looking for nested subparts on already-flat structure

EduShare — Tests

55 tests passing (35 existing + 20 new covering the three bugs)
TestComputeSectionMarks — 5 tests
TestFreeAttemptsLeft — 8 tests
TestGradeQuiz — 7 tests

KnowlyGen — Math rendering

MATH-01: Accent commands (\overline, \hat, \vec etc.) silently dropped → fixed
MATH-02: \\ line breaks in $...$ passing through as literal backslashes → fixed
INV-02: python-docx missing from requirements.txt; dead deps (weasyprint, reportlab) removed


🔄 In Progress — Deprecation cleanup (EduShare)
App code — changes discussed but not yet confirmed applied on your machine:
FileWhatCountapp/models.pyutcnow() calls2app/models.pydefault=datetime.utcnow column defaults19app/quiz/quiz_routes.pyutcnow() calls3app/quiz/quiz_routes.pyquery.get()1app/payments/routes.pyutcnow() calls8app/payments/routes.pyquery.get()2app/internal/routes.pyutcnow()1app/past_papers/routes.pyutcnow()1app/admin/routes.pyquery.get()1app/auth/routes.pyquery.get()1app/models.pyquery.get() in load_user1
Test files — not yet applied:
FileWhatCounttests/conftest.pyutcnow()1tests/test_payments.pyutcnow()2tests/test_payments.pyquery.get()3tests/test_posts.pyquery.get()4
Still pending after all the above:

SAWarning in app/posts/routes.py:386 — Object of type <Post> not in session during db.session.flush()


📋 Not Yet Started

KnowlyGen deployment prep (local PC — LibreOffice path, env config)
KnowlyGen runner end-to-end test against a live EduShare instance
Any EduShare issues outside the three bugs (none currently logged)


The deprecation cleanup is the only active thread. Once your machine has 0 warnings from app and test code (the SQLAlchemy library internal warning from third-party code is unfixable by us), we move to the SAWarning then deployment prep. Want to confirm which of the deprecation changes you've already applied so we know exactly where you are?