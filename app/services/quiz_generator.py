"""
Quiz Generation Service for eDuShare

This module handles automatic quiz generation from PDF documents when posts are approved.
It provides functions to:
- Generate quiz JSON from PDF documents
- Detect document changes using file hash comparison
- Regenerate quizzes when documents are updated
- Handle quiz lifecycle (create, update, delete)

Usage:
    from app.services.quiz_generator import generate_quiz_for_post, regenerate_quiz
    
    # Generate quiz for a newly approved post
    generate_quiz_for_post(post_id)
    
    # Regenerate quiz when document is updated
    regenerate_quiz(post_id)
"""

import os
import json
import hashlib
import logging
from datetime import datetime

from app import db
from app.models import Post, QuizData, Document

# Configure logging
logger = logging.getLogger(__name__)


def calculate_file_hash(file_path):
    """
    Calculate SHA256 hash of a file to detect changes.
    
    Args:
        file_path: Path to the file
        
    Returns:
        str: Hexadecimal hash string, or None if file doesn't exist
    """
    if not os.path.exists(file_path):
        return None
    
    sha256_hash = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            # Read in chunks to handle large files
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    except Exception as e:
        logger.error(f"Error calculating file hash: {e}")
        return None


def get_document_path(document):
    """
    Get the absolute path to a document.
    
    Args:
        document: Document model instance
        
    Returns:
        str: Absolute path to the document file
    """
    if not document:
        return None
    
    # file_path could be relative or absolute
    file_path = document.file_path
    
    # If relative, make it absolute
    if not os.path.isabs(file_path):
        # Try common base paths
        base_paths = [
            os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'uploads', 'documents'),
            os.path.join(os.path.dirname(os.path.dirname(__file__)), 'app', 'static', 'uploads', 'documents'),
            os.path.join(os.path.dirname(os.path.dirname(__file__)), '..', 'app', 'static', 'uploads', 'documents'),
        ]
        
        for base in base_paths:
            abs_path = os.path.join(base, document.filename)
            if os.path.exists(abs_path):
                return abs_path
        
        # Fallback: assume it's relative to project root
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        return os.path.join(project_root, file_path)
    
    return file_path


def parse_pdf_to_quiz(pdf_path):
    """
    Parse a PDF file and extract quiz data.
    
    This function imports and uses the pdf_quiz_parser module.
    
    Args:
        pdf_path: Absolute path to the PDF file
        
    Returns:
        dict: Structured quiz data, or None if parsing fails
    """
    try:
        # Import the parser
        import sys
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        
        from pdf_quiz_parser import PDFQuizParser
        
        parser = PDFQuizParser(pdf_path)
        quiz_data = parser.parse()
        
        if quiz_data and quiz_data.get('sections'):
            logger.info(f"Successfully parsed PDF: {pdf_path}")
            return quiz_data
        else:
            logger.warning(f"No quiz data extracted from PDF: {pdf_path}")
            return None
            
    except Exception as e:
        logger.error(f"Error parsing PDF: {e}")
        return None


def generate_quiz_for_post(post_id):
    """
    Generate a quiz for a post from its attached PDF document.
    
    This function is called when:
    - A post is approved
    - A post's document is updated
    
    Args:
        post_id: ID of the post to generate quiz for
        
    Returns:
        QuizData: The created quiz object, or None if failed
    """
    logger.info(f"Generating quiz for post ID: {post_id}")
    
    # Get the post
    post = Post.query.get(post_id)
    if not post:
        logger.error(f"Post not found: {post_id}")
        return None
    
    # Check if post has a document
    if not post.has_document or not post.document:
        logger.warning(f"Post {post_id} has no document attached")
        return None
    
    # Check if document is PDF
    document = post.document
    if document.file_type != 'pdf':
        logger.warning(f"Document for post {post_id} is not a PDF (type: {document.file_type})")
        return None
    
    # Get the PDF file path
    pdf_path = get_document_path(document)
    if not pdf_path or not os.path.exists(pdf_path):
        logger.error(f"PDF file not found for post {post_id}: {pdf_path}")
        return None
    
    # Validate PDF structure before parsing
    try:
        from app.services.pdf_validation import validate_pdf_structure
        is_valid, doc_type, errors = validate_pdf_structure(pdf_path)
        if not is_valid:
            logger.error(f"PDF structure validation failed for post {post_id} ({doc_type}): {errors}")
            return None
        logger.info(f"PDF structure validation passed ({doc_type})")
    except Exception as e:
        logger.error(f"Error validating PDF structure: {e}")
        # Continue parsing if validation fails (backward compatibility)
    
    # Calculate file hash to track changes
    file_hash = calculate_file_hash(pdf_path)
    if not file_hash:
        logger.error(f"Could not calculate hash for PDF: {pdf_path}")
        return None
    
    # Parse the PDF
    quiz_data = parse_pdf_to_quiz(pdf_path)
    if not quiz_data:
        logger.error(f"Failed to parse PDF for post {post_id}")
        return None
    
    # Flatten questions for database storage
    all_questions = []
    for section in quiz_data.get('sections', []):
        section_type = section.get('question_type', section.get('type', 'multiple_choice'))
        for q in section.get('questions', []):
            # Determine question type
            if section_type in ['multiple_choice', 'mcq']:
                q_type = 'mcq'
            elif section_type in ['true_false', 'tf']:
                q_type = 'tf'
            elif section_type in ['short_answer']:
                q_type = 'short_answer'
            elif section_type in ['essay', 'problem_solving']:
                q_type = 'problem'
            else:
                q_type = 'mcq'
            
            q_db_format = {
                'type': q_type,
                'question': q.get('question_text', ''),
                'options': q.get('options', []),
                'answer': q.get('correct_answer', ''),
                'marks': q.get('marks', 2),
                'explanation': q.get('explanation', '')
            }
            
            # Format options as list of {letter, text} objects for template compatibility
            if 'options' in q and isinstance(q['options'], dict):
                q_db_format['options'] = [
                    {'letter': 'A', 'text': q['options'].get('A', '')},
                    {'letter': 'B', 'text': q['options'].get('B', '')},
                    {'letter': 'C', 'text': q['options'].get('C', '')},
                    {'letter': 'D', 'text': q['options'].get('D', '')}
                ]
            elif 'options' in q and isinstance(q['options'], list):
                # Already a list - ensure proper format
                formatted_opts = []
                letters = ['A', 'B', 'C', 'D', 'E', 'F']
                for i, opt in enumerate(q['options']):
                    if isinstance(opt, dict):
                        formatted_opts.append(opt)
                    elif isinstance(opt, str):
                        formatted_opts.append({'letter': letters[i] if i < len(letters) else chr(65+i), 'text': opt})
                q_db_format['options'] = formatted_opts
            
            # For true/false questions, ensure options are set
            if q_type == 'tf' and not q_db_format['options']:
                q_db_format['options'] = [
                    {'letter': 'T', 'text': 'True'},
                    {'letter': 'F', 'text': 'False'}
                ]
            
            all_questions.append(q_db_format)
    
    # Calculate totals
    total_marks = sum(q.get('marks', 0) for q in all_questions)
    xp_reward = max(5, total_marks // 10)
    
    # Build metadata with title
    metadata = quiz_data.get('metadata', {})
    meta = json.dumps({
        'title': metadata.get('title', '') or os.path.basename(pdf_path).replace('.pdf', '').replace('_', ' '),
        'time_minutes': metadata.get('time_allowed', 60) if isinstance(metadata.get('time_allowed'), int) else 60,
        'total_marks': total_marks,
        'total_questions': len(all_questions),
        'file_hash': file_hash,
        'generated_at': datetime.utcnow().isoformat(),
        'source_pdf': os.path.basename(pdf_path)
    })
    
    # Check if quiz already exists for this post
    existing_quiz = QuizData.query.filter_by(post_id=post_id).first()
    
    if existing_quiz:
        # Update existing quiz
        logger.info(f"Updating existing quiz for post {post_id}")
        existing_quiz.questions = json.dumps(all_questions)
        existing_quiz.total_marks = total_marks
        existing_quiz.xp_reward = xp_reward
        existing_quiz.meta = meta
        db.session.commit()
        return existing_quiz
    else:
        # Create new quiz
        logger.info(f"Creating new quiz for post {post_id}")
        quiz = QuizData(
            post_id=post_id,
            questions=json.dumps(all_questions),
            total_marks=total_marks,
            xp_reward=xp_reward,
            meta=meta
        )
        db.session.add(quiz)
        db.session.commit()
        return quiz


def regenerate_quiz(post_id):
    """
    Force regenerate a quiz for a post.
    
    This deletes any existing quiz and creates a new one from the current document.
    
    Args:
        post_id: ID of the post to regenerate quiz for
        
    Returns:
        QuizData: The new quiz object, or None if failed
    """
    logger.info(f"Regenerating quiz for post ID: {post_id}")
    
    # Delete existing quiz if any
    existing_quiz = QuizData.query.filter_by(post_id=post_id).first()
    if existing_quiz:
        logger.info(f"Deleting existing quiz for post {post_id}")
        db.session.delete(existing_quiz)
        db.session.commit()
    
    # Generate new quiz
    return generate_quiz_for_post(post_id)


def check_and_update_quiz(post_id):
    """
    Check if document has changed and update quiz if needed.
    
    Compares the current document's hash with the stored hash.
    Only regenerates if the file has actually changed.
    
    Args:
        post_id: ID of the post to check
        
    Returns:
        bool: True if quiz was updated, False if no change detected
    """
    post = Post.query.get(post_id)
    if not post or not post.has_document or not post.document:
        return False
    
    document = post.document
    pdf_path = get_document_path(document)
    
    if not pdf_path or not os.path.exists(pdf_path):
        return False
    
    # Calculate new hash
    new_hash = calculate_file_hash(pdf_path)
    if not new_hash:
        return False
    
    # Get existing quiz
    existing_quiz = QuizData.query.filter_by(post_id=post_id).first()
    
    if existing_quiz:
        # Parse stored metadata to get hash
        try:
            meta = json.loads(existing_quiz.meta) if existing_quiz.meta else {}
            stored_hash = meta.get('file_hash', '')
            
            if stored_hash == new_hash:
                logger.info(f"Document unchanged for post {post_id}, skipping regeneration")
                return False
            else:
                logger.info(f"Document changed for post {post_id}, regenerating quiz")
        except:
            pass
    
    # Generate/update quiz
    generate_quiz_for_post(post_id)
    return True


def delete_quiz_for_post(post_id):
    """
    Delete quiz data for a post.
    
    Args:
        post_id: ID of the post to delete quiz for
        
    Returns:
        bool: True if deleted, False if no quiz existed
    """
    existing_quiz = QuizData.query.filter_by(post_id=post_id).first()
    if existing_quiz:
        db.session.delete(existing_quiz)
        db.session.commit()
        logger.info(f"Deleted quiz for post {post_id}")
        return True
    return False


def on_post_approved(post_id):
    """
    Callback function to be called when a post is approved.
    
    This is the main entry point for automatic quiz generation.
    
    Args:
        post_id: ID of the approved post
        
    Returns:
        QuizData: The created quiz, or None
    """
    logger.info(f"Post approved: {post_id}")
    return generate_quiz_for_post(post_id)


def on_document_updated(post_id):
    """
    Callback function to be called when a post's document is updated.
    
    Handles document replacement - deletes old quiz and creates new one.
    
    Args:
        post_id: ID of the post with updated document
        
    Returns:
        QuizData: The new quiz, or None
    """
    logger.info(f"Document updated for post: {post_id}")
    return regenerate_quiz(post_id)
