import os
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

DEEPL_API_KEY = os.environ.get('DEEPL_API_KEY')

@app.route('/')
def home():
    return "Backend is running normally", 200

@app.route('/translate', methods=['POST', 'OPTIONS'])
def translate():
    """DeepL translation endpoint"""
    
    if request.method == 'OPTIONS':
        return '', 204

    try:
        data = request.get_json()
        text = data.get('text')
        target_lang = data.get('target_lang', 'ZH-HANT')

        if not text or not target_lang:
            return jsonify({'error': 'Invalid input'}), 400

        if not DEEPL_API_KEY:
            return jsonify({'error': 'DEEPL_API_KEY not configured'}), 500

        response = requests.post(
            'https://api-free.deepl.com/v2/translate',
            data={
                'auth_key': DEEPL_API_KEY,
                'text': text,
                'target_lang': target_lang
            },
            timeout=10
        )
        
        response.raise_for_status()
        translation = response.json()['translations'][0]['text']
        return jsonify({'translations': [{'text': translation}]})
        
    except requests.exceptions.RequestException as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
