import sqlite3, json

conn = sqlite3.connect('instance/knowly.db')

rows = conn.execute('SELECT id, post_id, meta, questions FROM quiz_data').fetchall()
updated = 0

for row_id, post_id, meta_str, questions_str in rows:
    meta = json.loads(meta_str) if meta_str else {}

    if meta.get('document_type'):
        print(f'post_id={post_id} already has document_type={meta["document_type"]}')
        continue

    try:
        questions = json.loads(questions_str) if questions_str else []
    except:
        questions = []

    if not questions:
        doc_type = 'quiz'
    elif isinstance(questions[0], dict):
        keys = set(questions[0].keys())
        if 'section_number' in keys and 'content' in keys:
            doc_type = 'notes'
        elif 'section_type' in keys and 'entries' in keys:
            doc_type = 'cheatsheet'
        elif 'question_text' in keys or 'options' in keys or 'mark' in keys:
            doc_type = 'quiz'
        else:
            doc_type = 'quiz'
    else:
        doc_type = 'quiz'

    meta['document_type'] = doc_type
    conn.execute('UPDATE quiz_data SET meta=? WHERE id=?', (json.dumps(meta), row_id))
    print(f'post_id={post_id} → set document_type={doc_type}')
    updated += 1

conn.commit()
conn.close()
print(f'\nDone. Updated {updated} rows.')
