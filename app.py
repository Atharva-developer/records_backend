import os, sys
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import pandas as pd
from Levenshtein import ratio
from unidecode import unidecode
from indic_transliteration.sanscript import transliterate, DEVANAGARI, ITRANS

# Include hindi_fuzzy_merge module
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE_DIR, 'hindi_fuzzy_merge'))

app = Flask(__name__)
CORS(app)

# Path to your sample CSV data and documents directory
data_file = os.path.join(BASE_DIR, 'data', 'sample_records.csv')
docs_dir = os.path.join(BASE_DIR, 'static', 'documents')

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

    print(f"Received Search Query: owner='{owner_q}', father='{father_q}'")
    print(f"Normalized: owner='{owner_norm}', father='{father_norm}'")

    # Create a copy to avoid modifying global df
    temp_df = df.copy()

    if owner_q and not father_q:
        temp_df['score'] = temp_df['owner_str'].apply(lambda x: ratio(owner_norm, x))
    elif father_q and not owner_q:
        temp_df['score'] = temp_df['father_str'].apply(lambda x: ratio(father_norm, x))
    elif owner_q and father_q:
        query = f"{owner_norm} {father_norm}"
        temp_df['score'] = temp_df['search_str'].apply(lambda x: ratio(query, x))
    else:
        return jsonify([])

    # Filter and sort results
    matches = temp_df[temp_df['score'] >= 0.5].sort_values('score', ascending=False).head(20)

    results = []
    for _, row in matches.iterrows():
        # Extract only the filename (e.g., VID12345.pdf)
        document_filename = row['document']
        document_url = f"https://records-backend-krc7.onrender.com/static/documents/{document_filename}"
        results.append({
            'Khata Number': row['Khata Number'],
            'Khasra Number': row['Khasra Number'],
            'Area': row['area'],
            'Document': document_url  # Return
        })
    return jsonify(results)

@app.route('/search-document')
def search_document():
    keyword = request.args.get('q', '').strip().lower()

    if not keyword:
        return jsonify([])

    # Filter rows that contain the keyword in the document column
    matches = df[df['document'].str.lower().str.contains(keyword)]

    results = []
    for _, row in matches.iterrows():
        # Extract only the filename (e.g., VID12345.pdf)
        document_filename = row['document']
        document_url = f"https://records-backend-krc7.onrender.com/static/documents/{document_filename}"
        results.append({
            'Khata Number': row['Khata Number'],
            'Khasra Number': row['Khasra Number'],
            'Area': row['area'],
            'Document': document_url  # Return only the filename
        })

    return jsonify(results)

@app.route('/documents/<path:filename>')
def serve_doc(filename):
    return send_from_directory(docs_dir, filename)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
