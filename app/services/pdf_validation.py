"""
PDF Structural Validation Service for eDuShare

This module provides validation functions that handle different document types
with flexible rules:
- Quiz (with sections, questions, answer key)
- Study guide (learning materials)
- Assessment (simple quizzes without full sections)

Usage:
    from app.services.pdf_validation import validate_pdf_before_approval
    
    is_valid, message = validate_pdf_before_approval(pdf_path)
    if is_valid:
        print("Document is valid")
    else:
        print(f"Validation failed: {message}")
"""

import re
import logging
from pathlib import Path

try:
    import pdfplumber
except ImportError:
    pdfplumber = None
    print("Error: pdfplumber not installed. Run: pip install pdfplumber")

# Configure logging
logger = logging.getLogger(__name__)


def extract_pdf_text(pdf_path):
    """Extract all text from PDF using pdfplumber."""
    if not pdfplumber:
        raise ImportError("pdfplumber is not installed")
    
    try:
        text = ""
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        return text
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {e}")
        raise


def detect_document_type(text):
    """Detect if document is a quiz, study guide, or other type."""
    has_sections = re.search(r'Section\s*[A-D]:', text, re.IGNORECASE)
    has_questions = re.search(r'Question\s*\d+|^\d+\.', text, re.MULTILINE)
    has_answer_key = re.search(r'ANSWER\s*KEY|Correct\s*Answer|Solution', text, re.IGNORECASE)
    
    has_study_notes = re.search(r'STUDY\s*NOTES|LEARNING\s*OBJECTIVES|SUMMARY|KEY\s*POINTS', text, re.IGNORECASE)
    
    if has_sections and has_questions and has_answer_key:
        return 'quiz'
    elif has_study_notes:
        return 'study_guide'
    elif has_questions:
        return 'assessment'
    else:
        return 'unknown'


def validate_quiz(text):
    """Validate quiz structure with flexible rules."""
    errors = []
    
    if not re.search(r'Section\s*[A-D]:', text, re.IGNORECASE):
        errors.append("Missing section headers (A-D) - document may be a different type")
    
    if not re.search(r'Question\s*\d+|^\d+\.', text, re.MULTILINE):
        errors.append("No questions found - document may be a different type")
    
    if not re.search(r'ANSWER\s*KEY|Correct\s*Answer|Solution', text, re.IGNORECASE):
        errors.append("No answer key or solutions found - document may be a different type")
    
    return errors


def validate_study_guide(text):
    """Validate study guide structure."""
    errors = []
    
    if not re.search(r'LEARNING\s*OBJECTIVES|KEY\s*CONCEPTS|SUMMARY|STUDY\s*NOTES', text, re.IGNORECASE):
        errors.append("No study guide structure detected")
    
    return errors


def validate_assessment(text):
    """Validate assessment structure (simpler than quiz)."""
    errors = []
    
    if not re.search(r'Question\s*\d+|^\d+\.', text, re.MULTILINE):
        errors.append("No questions found")
    
    return errors


def validate_pdf_structure(pdf_path):
    """
    Main validation function with flexible rules for different document types.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        tuple: (is_valid, document_type, errors) where is_valid is bool, 
               document_type is string, and errors is list of strings
    """
    logger.info(f"Validating PDF structure: {pdf_path}")
    
    try:
        text = extract_pdf_text(pdf_path)
    except Exception as e:
        return False, 'unknown', [f"Error extracting text from PDF: {str(e)}"]
    
    document_type = detect_document_type(text)
    errors = []
    
    if document_type == 'quiz':
        errors = validate_quiz(text)
    elif document_type == 'study_guide':
        errors = validate_study_guide(text)
    elif document_type == 'assessment':
        errors = validate_assessment(text)
    else:
        errors = ["Unknown document type - please check content"]
    
    is_valid = len(errors) == 0
    
    if is_valid:
        logger.info(f"PDF structure validation passed for {document_type}")
    else:
        logger.warning(f"PDF structure validation failed for {document_type}: {errors}")
    
    return is_valid, document_type, errors


def validate_pdf_before_approval(pdf_path):
    """
    Convenience function for use in post approval process.
    Provides detailed error messages for moderators.
    """
    is_valid, doc_type, errors = validate_pdf_structure(pdf_path)
    
    if not is_valid:
        error_message = f"This {doc_type} document does not follow the expected format:\n\n"
        error_message += "\n".join(f"• {error}" for error in errors)
        return False, error_message
    
    return True, f"PDF structure is valid ({doc_type})"


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python pdf_validation.py <pdf_path>")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    is_valid, doc_type, errors = validate_pdf_structure(pdf_path)
    
    if is_valid:
        print(f"✅ PDF structure validation PASSED ({doc_type})")
    else:
        print(f"❌ PDF structure validation FAILED ({doc_type})")
        for error in errors:
            print(f"  • {error}")
        sys.exit(1)
