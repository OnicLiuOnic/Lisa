// Cloudflare Worker: DeepL translation proxy.
// Mirrors the Flask backend in server.py (which runs on Railway) so the
// Cloudflare Workers build target is a valid Worker rather than a Flask app.

const DEEPL_URL = 'https://api-free.deepl.com/v2/translate';

const CORS_HEADERS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
};

function json(obj, status) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { 'Content-Type': 'application/json', ...CORS_HEADERS },
  });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: CORS_HEADERS });
    }

    if (url.pathname === '/' && request.method === 'GET') {
      return new Response('Backend is running normally', {
        status: 200,
        headers: CORS_HEADERS,
      });
    }

    if (url.pathname === '/translate' && request.method === 'POST') {
      let data;
      try {
        data = await request.json();
      } catch (e) {
        return json({ error: 'Invalid input' }, 400);
      }

      const text = data.text;
      const targetLang = data.target_lang || 'ZH-HANT';

      if (!text || !targetLang) {
        return json({ error: 'Invalid input' }, 400);
      }
      if (!env.DEEPL_API_KEY) {
        return json({ error: 'DEEPL_API_KEY not configured' }, 500);
      }

      try {
        const body = new URLSearchParams({
          auth_key: env.DEEPL_API_KEY,
          text,
          target_lang: targetLang,
        });
        const resp = await fetch(DEEPL_URL, {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          body,
        });
        if (!resp.ok) {
          return json({ error: `DeepL error: ${resp.status}` }, 500);
        }
        const result = await resp.json();
        const translation = result.translations[0].text;
        return json({ translations: [{ text: translation }] }, 200);
      } catch (e) {
        return json({ error: String(e) }, 500);
      }
    }

    return json({ error: 'Not found' }, 404);
  },
};
