"""
即時翻譯錄音 — 本地代理伺服器
功能：靜態檔案伺服 + DeepL API 代理（解決 CORS 問題）
使用方式：uv run python server.py
"""

import http.server
import json
import urllib.request
import urllib.parse
import urllib.error
from typing import Optional


class TranslateProxyHandler(http.server.SimpleHTTPRequestHandler):
    """擴展靜態檔案伺服器，加入 /api/translate 代理端點"""

    def do_OPTIONS(self) -> None:
        """處理 CORS 預檢請求（Preflight）"""
        self.send_response(200)
        self._set_cors_headers()
        self.end_headers()

    def do_POST(self) -> None:
        """處理翻譯 API 代理請求"""
        if self.path == '/api/translate':
            self._handle_translate()
        else:
            self.send_error(404, '未找到該端點')

    def _handle_translate(self) -> None:
        """代理轉發翻譯請求到 DeepL API，避免瀏覽器 CORS 限制"""
        try:
            # 讀取前端傳來的請求內容
            content_length: int = int(self.headers.get('Content-Length', 0))
            body: bytes = self.rfile.read(content_length)
            data: dict = json.loads(body.decode('utf-8'))

            api_key: str = data.get('api_key', '')
            text: list[str] = data.get('text', [])
            source_lang: str = data.get('source_lang', 'EN')
            target_lang: str = data.get('target_lang', 'ZH-HANT')

            if not api_key or not text:
                self._send_json(400, {'error': '缺少 api_key 或 text 參數'})
                return

            # 根據 API Key 結尾判斷免費版或付費版
            is_free: bool = api_key.endswith(':fx')
            base_url: str = (
                'https://api-free.deepl.com/v2/translate'
                if is_free
                else 'https://api.deepl.com/v2/translate'
            )

            print(f'[除錯] API Key 尾碼: ...{api_key[-6:]}')
            print(f'[除錯] 使用端點: {base_url}')

            # 使用 form-encoded body + Authorization header（符合 DeepL 官方文件）
            form_data: dict[str, str] = {
                'text': text[0],
                'source_lang': source_lang,
                'target_lang': target_lang,
            }
            encoded_data: bytes = urllib.parse.urlencode(form_data).encode('utf-8')

            req = urllib.request.Request(
                base_url,
                data=encoded_data,
                headers={
                    'Authorization': f'DeepL-Auth-Key {api_key}',
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                method='POST',
            )

            # 發送請求到 DeepL
            with urllib.request.urlopen(req, timeout=15) as resp:
                result: bytes = resp.read()
                print(f'[除錯] DeepL 回應成功')
                self._send_json(200, json.loads(result.decode('utf-8')))

        except urllib.error.HTTPError as e:
            error_body: str = e.read().decode('utf-8', errors='replace')
            print(f'[錯誤] DeepL API {e.code}: {error_body}')

            # 針對常見錯誤提供更友善的訊息
            if e.code == 403:
                msg = ('API Key 認證失敗。請確認：\n'
                       '1. Key 是否正確（免費版應以 :fx 結尾）\n'
                       '2. 是否已在 DeepL 網站啟用 API')
            elif e.code == 456:
                msg = '翻譯額度已用完'
            else:
                msg = f'DeepL API 錯誤: {e.code}'

            self._send_json(e.code, {'error': msg})
        except urllib.error.URLError as e:
            print(f'[錯誤] 網路連線: {e.reason}')
            self._send_json(502, {'error': f'無法連線到 DeepL: {e.reason}'})
        except json.JSONDecodeError:
            self._send_json(400, {'error': '無效的 JSON 格式'})
        except Exception as e:
            print(f'[錯誤] 伺服器內部錯誤: {e}')
            self._send_json(500, {'error': str(e)})

    def _send_json(self, status: int, data: dict) -> None:
        """發送 JSON 回應並附帶 CORS 標頭"""
        response: bytes = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self._set_cors_headers()
        self.end_headers()
        self.wfile.write(response)

    def _set_cors_headers(self) -> None:
        """設定 CORS 回應標頭，允許瀏覽器跨域存取"""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')

    def log_message(self, format: str, *args: object) -> None:
        """自訂日誌格式，更簡潔易讀"""
        print(f'[伺服器] {args[0]} {args[1]}')


def main() -> None:
    port: int = 8080
    server = http.server.HTTPServer(('0.0.0.0', port), TranslateProxyHandler)
    print(f'\n🚀 即時翻譯伺服器已啟動')
    print(f'📡 本地網址：http://localhost:{port}')
    print(f'📱 手機請用同一 WiFi，連線：http://<你的電腦IP>:{port}')
    print(f'\n按 Ctrl+C 停止伺服器\n')

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n伺服器已停止')
        server.server_close()


if __name__ == '__main__':
    main()
