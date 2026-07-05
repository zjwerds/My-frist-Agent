"""Web search, fetch, and API request tools."""

import json
import re
import urllib.request
import urllib.error
import time as time_module


async def _web_search(args: dict) -> dict:
    query = args.get("query", "")
    max_results = min(int(args.get("max_results", 5)), 20)

    if not query:
        return {"error": "缺少搜索关键词"}

    try:
        from duckduckgo_search import DDGS
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append({"title": r.get("title", ""), "url": r.get("href", ""), "snippet": r.get("body", "")})
        return {"query": query, "results": results, "total": len(results)}
    except ImportError:
        return {"error": "DuckDuckGo 搜索不可用（未安装 duckduckgo-search 包）"}
    except Exception as e:
        return {"query": query, "error": str(e), "results": []}


async def _web_fetch(args: dict) -> dict:
    url = args.get("url", "")
    max_length = int(args.get("max_length", 5000))

    if not url:
        return {"error": "缺少 URL"}

    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            content = resp.read().decode("utf-8", errors="replace")

        text = re.sub(r"<[^>]+>", " ", content)
        text = re.sub(r"\s+", " ", text).strip()

        truncated = len(text) > max_length
        return {"url": url, "status": resp.status, "content": text[:max_length] + ("..." if truncated else ""), "truncated": truncated}
    except urllib.error.HTTPError as e:
        return {"url": url, "error": f"HTTP {e.code}: {e.reason}"}
    except urllib.error.URLError as e:
        return {"url": url, "error": f"无法访问: {e.reason}"}
    except Exception as e:
        return {"url": url, "error": str(e)}


async def _api_request(args: dict) -> dict:
    method = args.get("method", "GET").upper()
    url = args.get("url", "")
    headers = args.get("headers", {})
    body = args.get("body", "")
    timeout = int(args.get("timeout", 15))

    if not url:
        return {"error": "请提供 url"}

    valid_methods = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
    if method not in valid_methods:
        return {"error": f"不支持的 HTTP 方法: {method}，支持: {', '.join(valid_methods)}"}

    try:
        req_headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        if isinstance(headers, dict):
            req_headers.update(headers)
        elif isinstance(headers, str):
            try:
                req_headers.update(json.loads(headers))
            except json.JSONDecodeError:
                pass

        data = None
        if body and method in ("POST", "PUT", "PATCH"):
            data = body.encode("utf-8")
            if "Content-Type" not in {k.lower() for k in req_headers}:
                req_headers["Content-Type"] = "application/json"

        req = urllib.request.Request(url, data=data, headers=req_headers, method=method)

        start = time_module.time()
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            elapsed = round((time_module.time() - start) * 1000)
            raw = resp.read()
            content_type = resp.headers.get("Content-Type", "")

            try:
                body_json = json.loads(raw.decode("utf-8"))
                body_preview = json.dumps(body_json, ensure_ascii=False, indent=2)[:3000]
            except (json.JSONDecodeError, UnicodeDecodeError):
                body_preview = raw.decode("utf-8", errors="replace")[:2000]

        return {"url": url, "method": method, "status": resp.status, "status_text": f"{resp.status} {resp.reason}", "latency_ms": elapsed, "content_type": content_type, "headers": dict(resp.headers), "body": body_preview, "body_length": len(raw)}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:1000]
        return {"url": url, "method": method, "status": e.code, "error": f"HTTP {e.code}: {e.reason}", "body": body}
    except urllib.error.URLError as e:
        return {"url": url, "method": method, "error": f"无法访问: {e.reason}"}
    except Exception as e:
        return {"url": url, "method": method, "error": str(e)}
