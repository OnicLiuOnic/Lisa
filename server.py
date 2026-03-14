import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from deep_translator import GoogleTranslator

app = Flask(__name__)
CORS(app)

# Normalize DeepL-style language codes to Google Translate codes
LANGUAGE_CODE_MAP = {
    'ZH-HANT': 'zh-TW',
    'ZH-HANS': 'zh-CN',
    'ZH': 'zh-TW',
    'EN': 'en',
    'JA': 'ja',
    'KO': 'ko',
}

@app.route('/')
def home():
    return "Backend is running normally", 200

@app.route('/translate', methods=['POST', 'OPTIONS'])
def translate():
    """Google Translate translation endpoint"""

    if request.method == 'OPTIONS':
        return '', 204

    try:
        data = request.get_json()
        text = data.get('text')
        target_lang = data.get('target_lang', 'zh-TW')

        if not text or not target_lang:
            return jsonify({'error': 'Invalid input'}), 400

        target = LANGUAGE_CODE_MAP.get(target_lang.upper(), target_lang.lower())

        try:
            translated = GoogleTranslator(source='auto', target=target).translate(text)
        except Exception as e:
            return jsonify({'error': f'Translation failed: {str(e)}'}), 502
        return jsonify({'translations': [{'text': translated}]})

    except Exception as e:
        return jsonify({'error': str(e)}), 400

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
