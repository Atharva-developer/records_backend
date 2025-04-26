import os
import sys
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import pandas as pd
from Levenshtein import ratio
from unidecode import unidecode
from indic_transliteration.sanscript import transliterate, DEVANAGARI, ITRANS

# Correct _file_ and _name_
BASE_DIR = os.path.dirname(os.path.abspath(_file_))
sys.path.insert(0, os.path.join(BASE_DIR, 'hindi_fuzzy_merge'))

app = Flask(_name_)
CORS(app)

# Path to your sample CSV data and documents directory
data_file = os.path.join(BASE_DIR, 'data', 'sample_records.csv')
docs_dir = os.path.join(BASE_DIR, 'static', 'documents')  # <-- Corrected path: static/documents/

# Load and prepare data
df = pd.read_csv(data_file, dtype=str)
df.fillna('', inplace=True)

# Normalize function
def normalize(text: str) -> str:
    text = text or ''
    try:
        text = transliterate(text, DEVANAGARI, ITRANS)
    except Exception:
        pass
    return unidecode(text).lower()

# Pre-compute normalized columns
search_cols = ['owner_name', 'father_name']
df['search_str'] = df.apply(lambda r: normalize(r['owner_name']) + ' ' + normalize(r['father_name']), axis=1)
df['owner_str'] = df['owner_name'].apply(normalize)
df['father_str'] = df['father_name'].apply(normalize)

@app.route('/search', methods=['GET'])
def search():
    owner_q = request.args.get('owner', '').strip()
    father_q = request.args.get('father', '').strip()
    owner_norm = normalize(owner_q)
    father_norm = normalize(father_q)

    if owner_q and not father_q:
        df['score'] = df['owner_str'].apply(lambda x: ratio(owner_norm, x))
    elif father_q and not owner_q:
        df['score'] = df['father_str'].apply(lambda x: ratio(father_norm, x))
    elif owner_q and father_q:
        query = f"{owner_norm} {father_norm}"
        df['score'] = df['search_str'].apply(lambda x: ratio(query, x))
    else:
        return jsonify([])

    matches = df[df['score'] >= 0.5].sort_values('score', ascending=False).head(20)

    results = []
    for _, row in matches.iterrows():
        document_filename = row['document']
        # Build full document URL
        document_url = f"https://records-backend-4lta.onrender.com/static/documents/{document_filename}"
        results.append({
            'Khata Number': row['Khata Number'],
            'Khasra Number': row['Khasra Number'],
            'Area': row['area'],
            'Document': document_url  # Returning full URL for frontend
        })
    return jsonify(results)

@app.route('/search-document')
def search_document():
    keyword = request.args.get('q', '').strip().lower()

    if not keyword:
        return jsonify([])

    matches = df[df['document'].str.lower().str.contains(keyword)]

    results = []
    for _, row in matches.iterrows():
        document_filename = row['document']
        document_url = f"https://records-backend-4lta.onrender.com/documents/{document_filename}"
        results.append({
            'Khata Number': row['Khata Number'],
            'Khasra Number': row['Khasra Number'],
            'Area': row['area'],
            'Document': document_url
        })

    return jsonify(results)

# Serve static documents
@app.route('/documents/<path:filename>')
def serve_doc(filename):
    return send_from_directory(docs_dir, filename)

if _name_ == '_main_':
    app.run(host='0.0.0.0', port=5000, debug=True)
