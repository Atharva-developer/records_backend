import os, sys
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import pandas as pd
from Levenshtein import ratio
from unidecode import unidecode
from indic_transliteration.sanscript import transliterate, DEVANAGARI, ITRANS

# -------------------- CONFIGURATION --------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, 'data', 'sample_records.csv')
DOCS_DIR = os.path.join(BASE_DIR, 'documents')

# Serve files out of ./static at the site root
app = Flask(
    __name__,
    static_folder='static',
    static_url_path=''     # <–– this makes /foo map to static/foo
)

# Route “/” to static/index.html
@app.route('/')
def index():
    return app.send_static_file('index.html')

# Serve documents directory via static route
app.add_url_rule(
    '/documents/<path:filename>',
    'documents',
    lambda filename: send_from_directory(DOCS_DIR, filename)
)

# Debug: log directory and available files
print(f"Documents directory: {DOCS_DIR}")
try:
    print("Available documents:", os.listdir(DOCS_DIR))
except Exception as e:
    print(f"Error listing documents: {e}")

# -------------------- DATA LOAD & NORMALIZATION ---------
df = pd.read_csv(DATA_FILE, dtype=str)
df.fillna('', inplace=True)

def normalize(text: str) -> str:
    """
    Transliterate (if needed) and strip diacritics, returning lowercase ASCII.
    """
    text = text or ''
    try:
        text = transliterate(text, DEVANAGARI, ITRANS)
    except Exception:
        pass
    return unidecode(text).lower().strip()

# Pre-compute normalized columns and a combined search string
for col in ['owner_name', 'father_name', 'document']:
    df[f'{col}_norm'] = df[col].apply(normalize)

df['search_str'] = (
    df['owner_name_norm'] + ' ' +
    df['father_name_norm'] + ' ' +
    df['document_norm']
)

# -------------------- ROUTES -----------------------------
@app.route('/search')
def search():
    """
    Single endpoint for searching by owner, father, or document keyword.
    Uses substring or fuzzy match (Levenshtein ratio) on normalized data.
    """
    q_raw = request.args.get('q', '').strip()
    if not q_raw:
        return jsonify([])

    q = normalize(q_raw)
    threshold = 0.7  # fuzzy threshold
    results = []

    for _, row in df.iterrows():
        # exact substring
        if q in row['search_str'] or \
           ratio(q, row['owner_name_norm']) >= threshold or \
           ratio(q, row['father_name_norm']) >= threshold or \
           ratio(q, row['document_norm']) >= threshold:

            doc_url = f"{request.host_url.rstrip('/')}/documents/{row['document']}"
            results.append({
                'Khata Number': row['Khata Number'],
                'Khasra Number': row['Khasra Number'],
                'Area': row['area'],
                'Document': doc_url
            })

    return jsonify(results)

@app.route('/get-cities')
def get_cities():
    """
    Returns unique district names for dropdowns or filters.
    """
    cities = df['district'].unique().tolist()
    return jsonify(cities)

# -------------------- MAIN ------------------------------
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
