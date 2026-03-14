import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# DeepL API credentials
DEEP_L_API_KEY = 'YOUR_DEEPL_API_KEY'

@app.route('/translate', methods=['POST'])
def translate():
    data = request.json
    text = data.get('text')
    target_lang = data.get('target_lang')

    # Error handling
    if not text or not target_lang:
        return jsonify({'error': 'Invalid input'}), 400

    # Call DeepL API
    try:
        response = requests.post(
            'https://api-free.deepl.com/v2/translate',
            data={
                'auth_key': DEEP_L_API_KEY,
                'text': text,
                'target_lang': target_lang
            }
        )
        response.raise_for_status()
        translation = response.json()['translations'][0]['text']
        return jsonify({'translation': translation})
    except requests.exceptions.RequestException as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
