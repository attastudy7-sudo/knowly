# Quiz Service Requirements Documentation

## Overview

The `quiz_service.py` module serves as the **single source of truth** for all quiz-related operations in the eDuShare platform. It provides comprehensive functionality for validating, storing, normalizing, and grading quiz documents.

---

## 1. Module Purpose

The quiz service handles four core responsibilities:

1. **JSON Schema Validation** - Validates quiz documents against embedded JSON Schema (Draft 7)
2. **Semantic Validation** - Ensures logical consistency (marks totals, numbering, option counts)
3. **Question Normalization** - Converts section-based quiz structure to flat grading-ready list
4. **Database Persistence** - Stores normalized quiz data for grading operations

---

## 2. Supported Document Types

The service supports three document types, each with its own schema:

### 2.1 Quiz Document (`document_type: "quiz"`)
- **Required Fields**: document_type, title, course, level, metadata, sections
- **Structure**: Multi-section quizzes with various question types
- **Metadata**: total_questions, total_marks, time, time_allowed

### 2.2 Notes Document (`document_type: "notes"`)
- **Required Fields**: document_type, title, course, level, metadata, sections
- **Structure**: Educational content with block-based sections
- **Metadata**: estimated_read_time

### 2.3 Cheatsheet Document (`document_type: "cheatsheet"`)
- **Required Fields**: document_type, title, course, level, sections
- **Structure**: Quick reference guides with labeled entries

---

## 3. Question Types

### 3.1 Multiple Choice (`multiple_choice`)
- **Options**: Exactly 4 selectable options (A, B, C, D)
- **Correct Answer**: Must be one of A/B/C/D
- **Grading**: Case-insensitive letter comparison

### 3.2 True/False (`true_false`)
- **Options**: 2 selectable options (True / False)
- **Correct Answer**: Must be "True" or "False" (case-insensitive)
- **Grading**: Exact match after normalization

### 3.3 Short Answer (`short_answer`)
- **Options**: Can have any number of options (including 0)
- **Fallback**: If no options provided, True/False options added automatically
- **Correct Answer**: Must match one of the option letters
- **Grading**: Letter-based comparison

### 3.4 Problem Solving (`problem_solving`)
- **Structure**: Questions with multiple subparts (a, b, c...)
- **Subpart Options**: Each subpart must have exactly 2 selectable options
- **Correct Answer**: Must match one of the two option letters per subpart
- **Marks**: Subpart marks must sum to question marks
- **Grading**: Each subpart graded separately as flat question

---

## 4. Validation Process

### Phase 1: JSON Schema Validation
- **Tool**: jsonschema with Draft7Validator
- **Process**: Validates document structure against embedded schema
- **Output**: List of schema violation errors with path information
- **Error Format**: `[SCHEMA] path: error_message`

### Phase 2: Semantic Validation
- **Process**: Type-specific logical checks
- **Checks Include**:
  - Section letters sequential (A → D)
  - Question numbering sequential within sections
  - Option counts per question type
  - Correct answer validity
  - Marks accumulation
  - Explanation length (minimum 10 words)
- **Error Format**: `[SEMANTIC] context: error_message`

### Phase 3: Document Enrichment
- **Generated At**: Stamps current UTC timestamp if placeholder/missing
- **Document Hash**: SHA256 hash computed over all fields except document_hash itself

---

## 5. API Functions

### 5.1 `validate_document(doc: dict) -> dict`
**Purpose**: Main entry point for document validation

**Parameters**:
- `doc`: Dictionary containing quiz/notes/cheatsheet document

**Returns**: Same dictionary with `generated_at` and `document_hash` populated

**Raises**:
- `ValueError`: If document_type is missing or invalid
- `DocumentValidationError`: If validation fails (contains list of all errors)

**Example**:
```
python
try:
    validated = validate_document(quiz_dict)
except DocumentValidationError as e:
    for error in e.errors:
        print(error)
```

---

### 5.2 `normalise_quiz_to_flat_questions(validated_doc: dict) -> list[dict]`
**Purpose**: Converts section-based quiz to flat grading-ready format

**Output Structure** (per question):
```
python
{
    "type": "mcq" | "tf" | "sa" | "ps",
    "question": "HTML-safe question text",
    "answer": "correct_answer letter",
    "explanation": "explanation text",
    "marks": 10,
    "section": "A",
    "section_title": "Multiple Choice Questions",
    "question_number": 1,
    "options": [{"letter": "A", "text": "..."}],
    "subpart_label": "a)" | None,
    "subpart_text": "subpart question text" | None
}
```

**Key Behavior**:
- Problem solving: Each subpart becomes separate flat question
- True/False: Falls back to standard options if missing
- Short Answer: Ensures minimum 2 options

---

### 5.3 `grade_quiz(flat_questions: list[dict], answers: dict[str, str]) -> tuple[float, int]`
**Purpose**: Grades a quiz submission

**Parameters**:
- `flat_questions`: Output from `normalise_quiz_to_flat_questions()`
- `answers`: Dict mapping question index (string) → selected answer letter

**Returns**: Tuple of (earned_marks, total_marks)

**Grading Logic**:
- Case-insensitive letter comparison
- Empty answers skipped
- All question types use identical grading mechanism

**Example**:
```
python
earned, total = grade_quiz(flat_questions, {"0": "A", "1": "B", "2": "C"})
score_percentage = (earned / total) * 100
```

---

### 5.4 `validate_and_attach_quiz(post, json_bytes: bytes) -> tuple[QuizData, str|None]`
**Purpose**: Validates quiz JSON and attaches to post

**Parameters**:
- `post`: Flask post object
- `json_bytes`: Raw JSON file content

**Returns**:
- Success: `(QuizData, None)`
- Failure: `(None, error_message)`

**Database Operations**:
- Creates/updates QuizData record
- Stores flat questions as JSON
- Sets XP reward (total_marks × 10)

---

### 5.5 `quiz_from_sidecar(post) -> QuizData|None`
**Purpose**: Re-validates and re-attaches quiz from sidecar file

**Called From**: `on_post_approved()` after post approval

**Returns**: QuizData on success, None on failure

---

## 6. Data Models

### QuizData Model Fields
| Field | Type | Description |
|-------|------|-------------|
| `post_id` | Integer | Foreign key to Post |
| `questions` | JSON | Flat normalized question list |
| `total_marks` | Integer | Total possible marks |
| `xp_reward` | Integer | XP earned (total_marks × 10) |
| `meta` | JSON | Title, hash, generated_at, question count |

---

## 7. Error Handling

### DocumentValidationError
```
python
class DocumentValidationError(Exception):
    def __init__(self, errors: list[str]):
        self.errors = errors
```

**Usage**:
```
python
try:
    validate_document(doc)
except DocumentValidationError as e:
    print(e)  # Prints formatted error list
    for error in e.errors:
        log_error(error)
```

### Error Categories

| Category | Prefix | Description |
|----------|--------|-------------|
| Schema | `[SCHEMA]` | JSON structure violations |
| Semantic | `[SEMANTIC]` | Logical/business rule violations |

---

## 8. Configuration Constants

| Constant | Value | Description |
|----------|-------|-------------|
| `_MIN_EXPLANATION_WORDS` | 10 | Minimum words in explanation |
| `_SCHEMAS` | dict | Embedded JSON schemas (quiz, notes, cheatsheet) |

---

## 9. Dependencies

### Required Python Packages
- `jsonschema` - JSON Schema validation
- `flask` - Database session management
- `hashlib` - SHA256 hashing
- `json` - JSON parsing
- `datetime` - Timestamp generation

### Database Models
- `QuizData` - Quiz storage model
- `db` - Flask-SQLAlchemy instance

---

## 10. Usage Examples

### 10.1 Validating a Quiz Document
```
python
from app.services.quiz_service import validate_document, DocumentValidationError

quiz_data = {
    "document_type": "quiz",
    "title": "Mathematics Quiz",
    "course": "MATH101",
    "level": "Beginner",
    "metadata": {
        "total_questions": 10,
        "total_marks": 100
    },
    "sections": [...]
}

try:
    validated = validate_document(quiz_data)
    print(f"Hash: {validated['document_hash']}")
except DocumentValidationError as e:
    print("Validation failed:")
    for error in e.errors:
        print(f"  - {error}")
```

### 10.2 Grading a Submission
```
python
from app.services.quiz_service import (
    validate_document,
    normalise_quiz_to_flat_questions,
    grade_quiz
)

# Validate and normalize
validated = validate_document(quiz_dict)
flat_questions = normalise_quiz_to_flat_questions(validated)

# Grade submission
user_answers = {
    "0": "A",  # Question 0: User selected A
    "1": "B",  # Question 1: User selected B
    "2": "C",  # Question 2: User selected C
}

earned_marks, total_marks = grade_quiz(flat_questions, user_answers)
percentage = (earned_marks / total_marks) * 100

print(f"Score: {earned_marks}/{total_marks} ({percentage:.1f}%)")
```

### 10.3 Attaching Quiz to Post
```
python
from app.services.quiz_service import validate_and_attach_quiz

with open("quiz.json", "rb") as f:
    json_bytes = f.read()

quiz_data, error = validate_and_attach_quiz(post, json_bytes)

if error:
    print(f"Failed: {error}")
else:
    print(f"Attached quiz with {quiz_data.total_marks} marks")
```

---

## 11. Business Rules Summary

1. **Section Letters**: Must be sequential A → D
2. **Question Numbers**: Must be 1-based and sequential within section
3. **MCQ Options**: Exactly 4 options (A, B, C, D) required
4. **True/False**: Must have True/False as options and answer
5. **Problem Solving**: Each subpart must have 2 options; marks must sum correctly
6. **Explanations**: Minimum 10 words required
7. **Marks Totals**: Auto-corrected if declared vs actual mismatch
8. **XP Reward**: Calculated as total_marks × 10
9. **Hash**: SHA256 over all fields except document_hash

---

## 12. Extension Points

### Adding New Question Types
1. Add type to schema enum in `_QUIZ_SCHEMA`
2. Add validation logic in `_validate_quiz_semantics()`
3. Add normalization in `normalise_quiz_to_flat_questions()`
4. Update grading logic if needed (currently all use letter comparison)

### Adding New Document Types
1. Create schema in `_NOTES_SCHEMA`, `_CHEATSHEET_SCHEMA` pattern
2. Add to `_SCHEMAS` dictionary
3. Add semantic validator function
4. Update `validate_document()` dispatch dictionary

---

## 13. Testing Requirements

### Unit Tests
- Schema validation for valid/invalid documents
- Semantic validation edge cases
- Question normalization output format
- Grading logic accuracy
- Error message formatting

### Integration Tests
- End-to-end quiz submission and grading
- Database persistence
- Sidecar file handling

---

*Document Version: 1.0*  
*Last Updated: Auto-generated from quiz_service.py source code*
