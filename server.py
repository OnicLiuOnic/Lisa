"""
Online Translator — Cloudflare Workers 後端
功能：DeepL API 代理（解決 CORS 問題）
部署：透過 wrangler.toml 部署至 Cloudflare Workers
"""

import urllib.parse

from js import Response, fetch, JSON, Headers


async def on_fetch(request, env):
    """Cloudflare Workers 入口函式，處理所有 HTTP 請求"""

    # 設定 CORS 標頭，允許瀏覽器跨域存取
    headers = Headers.new()
    headers.set("Access-Control-Allow-Origin", "*")
    headers.set("Access-Control-Allow-Methods", "POST, OPTIONS")
    headers.set("Access-Control-Allow-Headers", "Content-Type")

    # 處理 CORS 預檢請求（Preflight）
    if request.method == "OPTIONS":
        return Response.new("", headers=headers)

    # 只有 POST 請求才處理翻譯
    if request.method == "POST":
        try:
            body = await request.json()

            text = getattr(body, "text", None)
            source_lang = getattr(body, "source_lang", "EN")
            target_lang = getattr(body, "target_lang", "ZH-HANT")

            if not text:
                headers.set("Content-Type", "application/json; charset=utf-8")
                return Response.new(
                    JSON.stringify({"error": "缺少 text 參數"}),
                    status=400,
                    headers=headers,
                )

            # 從 Cloudflare 環境變數安全讀取 API Key
            api_key = getattr(env, "DEEPL_API_KEY", None)
            if not api_key:
                headers.set("Content-Type", "application/json; charset=utf-8")
                return Response.new(
                    JSON.stringify({"error": "DEEPL_API_KEY 環境變數未設定"}),
                    status=500,
                    headers=headers,
                )

            # 根據 API Key 結尾判斷免費版或付費版
            if api_key.endswith(":fx"):
                deepl_url = "https://api-free.deepl.com/v2/translate"
            else:
                deepl_url = "https://api.deepl.com/v2/translate"

            # URL 編碼所有參數，避免特殊字元造成解析錯誤
            form_body = urllib.parse.urlencode({
                "text": text,
                "source_lang": source_lang,
                "target_lang": target_lang,
            })

            deepl_headers = Headers.new()
            deepl_headers.set("Authorization", f"DeepL-Auth-Key {api_key}")
            deepl_headers.set("Content-Type", "application/x-www-form-urlencoded")

            deepl_resp = await fetch(
                deepl_url,
                method="POST",
                headers=deepl_headers,
                body=form_body,
            )

            if not deepl_resp.ok:
                error_text = await deepl_resp.text()
                status = deepl_resp.status
                if status == 403:
                    msg = "API Key 認證失敗。請確認 Key 是否正確（免費版應以 :fx 結尾）"
                elif status == 456:
                    msg = "翻譯額度已用完"
                else:
                    msg = f"DeepL API 錯誤: {status}"
                headers.set("Content-Type", "application/json; charset=utf-8")
                return Response.new(
                    JSON.stringify({"error": msg, "detail": error_text}),
                    status=status,
                    headers=headers,
                )

            result = await deepl_resp.json()
            headers.set("Content-Type", "application/json; charset=utf-8")
            return Response.new(JSON.stringify(result), headers=headers)

        except Exception as e:
            headers.set("Content-Type", "application/json; charset=utf-8")
            return Response.new(
                JSON.stringify({"error": str(e)}),
                status=500,
                headers=headers,
            )

    # 非 POST / OPTIONS 請求回傳狀態訊息
    return Response.new("後端正常運行中", headers=headers)
