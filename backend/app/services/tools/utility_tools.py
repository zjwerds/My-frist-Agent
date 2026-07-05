"""Translator, JSON formatter, regex tester, OCR, memory search, DB query, env management tools."""

import json
import os
import re
import sqlite3
from pathlib import Path

from app.services.security import WORKSPACE_ROOT, in_workspace
from app.services.ocr_service import ocr_image_from_base64


async def _translator(args: dict) -> dict:
    text = args.get("text", "")
    source = args.get("source", "auto")
    target = args.get("target", "zh-CN")

    if not text:
        return {"error": "缺少待翻译文本"}

    try:
        from deep_translator import GoogleTranslator
        translated = GoogleTranslator(source=source, target=target).translate(text)
        return {"source_text": text, "translated_text": translated, "source_lang": source, "target_lang": target}
    except ImportError:
        return {"error": "翻译不可用（未安装 deep-translator 包）"}
    except Exception as e:
        return {"error": f"翻译失败: {e}"}


async def _json_formatter(args: dict) -> dict:
    json_str = args.get("json_string", "")
    action = args.get("action", "format")

    if not json_str:
        return {"error": "缺少 JSON 字符串"}

    try:
        parsed = json.loads(json_str)
        if action == "format":
            result = json.dumps(parsed, indent=2, ensure_ascii=False)
        elif action == "minify":
            result = json.dumps(parsed, separators=(",", ":"), ensure_ascii=False)
        elif action == "validate":
            result = "JSON 格式有效"
        else:
            return {"error": f"未知操作: {action}，支持 format/minify/validate"}
        return {"action": action, "result": result, "valid": True}
    except json.JSONDecodeError as e:
        return {"action": action, "error": str(e), "valid": False, "position": e.pos}


async def _regex_tester(args: dict) -> dict:
    pattern = args.get("pattern", "")
    text = args.get("text", "")

    if not pattern:
        return {"error": "缺少正则表达式"}

    try:
        flags = 0
        if args.get("ignore_case"):
            flags |= re.IGNORECASE
        if args.get("multiline"):
            flags |= re.MULTILINE
        if args.get("dotall"):
            flags |= re.DOTALL

        matches = list(re.finditer(pattern, text, flags))
        details = []
        for m in matches:
            details.append({"start": m.start(), "end": m.end(), "match": m.group(), "groups": list(m.groups()) if m.groups() else None})
        return {"pattern": pattern, "match_count": len(details), "matches": details[:50], "error": None}
    except re.error as e:
        return {"pattern": pattern, "error": str(e), "match_count": 0, "matches": []}


async def _ocr_image(args: dict, context: dict | None = None) -> dict:
    image_index = args.get("image_index", 0)
    all_images = (context or {}).get("all_images", [])
    if not all_images:
        return {"error": "当前对话中没有找到图片", "text": ""}
    if image_index < 0 or image_index >= len(all_images):
        return {"error": f"图片索引 {image_index} 无效，有效范围: 0-{len(all_images) - 1}", "text": ""}
    data_uri = all_images[image_index]
    text = ocr_image_from_base64(data_uri)
    return {"image_index": image_index, "text": text}


async def _search_memory(args: dict, context: dict | None = None) -> dict:
    query = args.get("query", "")
    if not query:
        return {"error": "缺少搜索关键词"}

    conversation_id = (context or {}).get("conversation_id", "")
    if not conversation_id:
        return {"error": "无法获取当前对话 ID"}

    from app.services.conversation_memory import search_memory
    results = search_memory(conversation_id, query)

    if not results:
        return {"query": query, "results": [], "message": "未找到相关历史记录"}

    return {
        "query": query,
        "results": [{"timestamp": r.get("timestamp", ""), "summary": r.get("summary", ""), "constraints": r.get("constraints", []), "decisions": r.get("decisions", []), "artifacts": r.get("artifacts", []), "user_intent": r.get("user_intent", "")} for r in results],
        "total": len(results),
    }


async def _db_query(args: dict) -> dict:
    sql = args.get("sql", "").strip()
    if not sql:
        return {"error": "请提供 sql 参数（SELECT 查询语句）"}

    sql_upper = sql.upper().strip()
    if not sql_upper.startswith("SELECT"):
        return {"error": "仅支持 SELECT 查询，不支持写操作"}
    for kw in ("DROP ", "ALTER ", "DELETE ", "INSERT ", "UPDATE ", "ATTACH ", "DETACH ", "REINDEX "):
        if kw in sql_upper:
            return {"error": f"不允许使用 {kw.strip()} 操作"}
    stripped_no_strings = re.sub(r"'[^']*'", "", sql)
    semi_pos = stripped_no_strings.find(";")
    if semi_pos >= 0 and semi_pos < len(stripped_no_strings.rstrip()):
        return {"error": "不支持多语句查询（仅允许单个 SELECT 语句）"}

    from app.database import DB_DIR
    db_path = os.path.join(DB_DIR, "agent.db")
    conn = None
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.execute("PRAGMA query_only = ON")
        cursor = conn.execute(sql)
        columns = [desc[0] for desc in cursor.description]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]

        max_rows = 100
        return {"sql": sql, "row_count": len(rows), "rows": rows[:max_rows], "truncated": len(rows) > max_rows}
    except sqlite3.DatabaseError as e:
        return {"sql": sql, "error": str(e), "row_count": 0, "rows": []}
    except Exception as e:
        return {"sql": sql, "error": str(e), "row_count": 0, "rows": []}
    finally:
        if conn:
            conn.close()


def _parse_env_content(content: str) -> dict[str, str]:
    variables = {}
    for line in content.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            continue
        key, _, val = stripped.partition("=")
        key = key.strip()
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
            val = val[1:-1]
        variables[key] = val
    return variables


async def _env_manage(args: dict) -> dict:
    action = args.get("action", "list")
    filepath = args.get("filepath", "")
    key = args.get("key", "")
    value = args.get("value", "")

    if not filepath:
        candidates = [WORKSPACE_ROOT / ".env", WORKSPACE_ROOT.parent / ".env"]
        env_path = None
        for c in candidates:
            if c.exists():
                env_path = c
                break
        if env_path is None:
            env_path = candidates[0]
    else:
        env_path = Path(filepath)
        if not in_workspace(env_path):
            return {"error": f"无权操作该路径（超出工作区范围）: {filepath}"}

    try:
        if action == "list":
            if not env_path.exists():
                return {"env_file": str(env_path), "variables": {}, "total": 0}
            content = env_path.read_text("utf-8", errors="replace")
            variables = _parse_env_content(content)
            masked = {}
            for k, v in variables.items():
                if any(s in k.lower() for s in ["key", "secret", "token", "password", "passwd"]):
                    masked[k] = v[:4] + "..." if len(v) > 4 else "****"
                else:
                    masked[k] = v
            return {"env_file": str(env_path), "variables": masked, "total": len(variables)}

        elif action == "get":
            if not env_path.exists():
                return {"error": f".env 文件不存在: {env_path}", "key": key}
            if not key:
                return {"error": "请提供 key"}
            content = env_path.read_text("utf-8", errors="replace")
            variables = _parse_env_content(content)
            if key not in variables:
                return {"key": key, "error": f"未找到变量: {key}"}
            val = variables[key]
            if any(s in key.lower() for s in ["key", "secret", "token", "password", "passwd"]):
                val = val[:4] + "..." if len(val) > 4 else "****"
            return {"key": key, "value": val}

        elif action == "set":
            if not key:
                return {"error": "请提供 key"}
            content = env_path.read_text("utf-8", errors="replace") if env_path.exists() else ""
            lines = content.split("\n")
            found = False
            for i, line in enumerate(lines):
                stripped = line.strip()
                if stripped.startswith("#") or "=" not in stripped:
                    continue
                existing_key = stripped.split("=", 1)[0].strip()
                if existing_key == key:
                    lines[i] = f'{key}="{value}"'
                    found = True
                    break
            if not found:
                if content and not content.endswith("\n"):
                    lines.append("")
                lines.append(f'{key}="{value}"')
            env_path.parent.mkdir(parents=True, exist_ok=True)
            env_path.write_text("\n".join(lines), "utf-8")
            return {"action": "set", "key": key, "env_file": str(env_path), "status": "set"}

        elif action == "unset":
            if not env_path.exists():
                return {"error": f".env 文件不存在: {env_path}"}
            if not key:
                return {"error": "请提供 key"}
            content = env_path.read_text("utf-8", errors="replace")
            lines = content.split("\n")
            new_lines = []
            removed = False
            for line in lines:
                stripped = line.strip()
                if stripped.startswith("#") or "=" not in stripped:
                    new_lines.append(line)
                    continue
                existing_key = stripped.split("=", 1)[0].strip()
                if existing_key == key:
                    removed = True
                else:
                    new_lines.append(line)
            env_path.write_text("\n".join(new_lines), "utf-8")
            return {"action": "unset", "key": key, "removed": removed, "env_file": str(env_path)}

        else:
            return {"error": f"不支持的操作: {action}，支持: list/get/set/unset"}
    except PermissionError:
        return {"error": f"无权限操作文件: {env_path}"}
    except Exception as e:
        return {"error": str(e)}
