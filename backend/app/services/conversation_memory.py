"""对话记忆封装服务 — 结构化压缩 + 智能裁剪 + 按需召回。"""

import json
import os
import threading
import logging
from datetime import datetime, timezone, timedelta
from app.utils import get_data_dir

logger = logging.getLogger(__name__)

MEMORY_DIR = os.path.join(get_data_dir(), "memories")
MAX_CHARS = 90000
KEEP_RECENT = 3
MAX_SEARCH = 5

BEIJING = timezone(timedelta(hours=8))

# Simple per-conversation lock to prevent concurrent read-modify-write races
_memory_locks: dict[str, threading.Lock] = {}
_memory_locks_lock = threading.Lock()


def _get_lock(conversation_id: str) -> threading.Lock:
    with _memory_locks_lock:
        if conversation_id not in _memory_locks:
            _memory_locks[conversation_id] = threading.Lock()
        return _memory_locks[conversation_id]


def _ts() -> str:
    return datetime.now(BEIJING).isoformat()


def _memory_path(conversation_id: str) -> str:
    return os.path.join(MEMORY_DIR, f"conv_{conversation_id}.json")


def init_memories():
    os.makedirs(MEMORY_DIR, exist_ok=True)


def load_memory(conversation_id: str) -> dict:
    path = _memory_path(conversation_id)
    if not os.path.exists(path):
        return {"conversation_id": conversation_id, "entries": []}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        logger.warning("Failed to read memory file %s, starting fresh", path)
        return {"conversation_id": conversation_id, "entries": []}


def save_memory(conversation_id: str, data: dict):
    _trim_entries(data)
    path = _memory_path(conversation_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def append_entry(conversation_id: str, entry: dict):
    lock = _get_lock(conversation_id)
    with lock:
        mem = load_memory(conversation_id)
        entry["timestamp"] = _ts()
        mem.setdefault("entries", []).append(entry)
        save_memory(conversation_id, mem)


def search_memory(conversation_id: str, query: str, max_results: int = MAX_SEARCH) -> list:
    mem = load_memory(conversation_id)
    entries = mem.get("entries", [])
    if not entries or not query:
        return []

    q = query.lower()
    scored = []
    for e in entries:
        score = 0
        fields = [
            e.get("summary", ""),
            e.get("user_intent", ""),
            " ".join(e.get("key_points", [])),
            " ".join(e.get("constraints", [])),
            " ".join(e.get("decisions", [])),
            " ".join(e.get("artifacts", [])),
        ]
        for f in fields:
            if q in f.lower():
                score += 1
        if score > 0:
            scored.append((score, e))

    scored.sort(key=lambda x: -x[0])
    return [e for _, e in scored[:max_results]]


def get_recent_context(conversation_id: str, db_messages: list, recent_count: int = KEEP_RECENT) -> str:
    """返回最近 N 轮原始消息的文本摘要（Tier 1 工作记忆）。"""
    pairs = [(m.role, m.content) for m in db_messages if m.role in ("user", "assistant") and m.content]
    recent = pairs[-(recent_count * 2):]
    lines = []
    for role, content in recent:
        label = "用户" if role == "user" else "AI"
        lines.append(f"{label}：{content[:500]}{'…' if len(content) > 500 else ''}")
    return "\n".join(lines)


def get_history_summary(conversation_id: str) -> str:
    """返回压缩记忆的文本摘要（Tier 2 压缩历史）。"""
    mem = load_memory(conversation_id)
    entries = mem.get("entries", [])
    if not entries:
        return ""

    parts = ["【历史对话摘要】"]
    for e in entries:
        ts = e.get("timestamp", "")[11:19]
        summary = e.get("summary", "")
        artifacts = e.get("artifacts", [])
        constraints = e.get("constraints", [])
        decisions = e.get("decisions", [])

        line = f"[{ts}] {summary}"
        if artifacts:
            line += f" | 文件: {', '.join(artifacts)}"
        if constraints:
            line += f" | 限制: {'; '.join(constraints)}"
        if decisions:
            line += f" | 决策: {'; '.join(decisions)}"
        parts.append(line)

    return "\n".join(parts)


def _estimate_size(data: dict) -> int:
    """Estimate JSON size without full serialization (faster for large data)."""
    entries = data.get("entries", [])
    overhead = len(json.dumps({k: v for k, v in data.items() if k != "entries"}, ensure_ascii=False))
    total = overhead
    for e in entries:
        total += len(json.dumps(e, ensure_ascii=False)) + 1  # +1 for comma/newline
    return total


def _trim_entries(data: dict):
    """智能裁剪：保留首条 + 最近 N 条，优先删低信息条目。"""
    entries = data.get("entries", [])
    if not entries:
        return

    total = _estimate_size(data)
    if total <= MAX_CHARS:
        return

    logger.info("Memory %s is ~%d chars, trimming...", data.get("conversation_id"), total)

    keep_indices = {0}
    for i in range(max(1, len(entries) - KEEP_RECENT), len(entries)):
        keep_indices.add(i)

    candidates = [(i, entries[i]) for i in range(len(entries)) if i not in keep_indices]
    candidates.sort(key=lambda x: (
        0 if x[1].get("constraints") or x[1].get("decisions") else 1,
        -x[0],
    ))

    target = MAX_CHARS * 0.9
    deleted = 0
    for idx, _ in candidates:
        if total <= target:
            break
        actual_idx = idx - deleted
        entries.pop(actual_idx)
        deleted += 1

    logger.info("Trimmed %d entries", deleted)


CONDENSE_PROMPT = """将以下对话封装为一条结构化记忆条目。

用户：{user_msg}
AI：{ai_msg}

输出格式（仅输出 JSON，不要多余内容）：
{{
  "summary": "一句话概括本轮做了什么",
  "constraints": ["用户提出的限制条件"],
  "decisions": ["做出的关键决策"],
  "artifacts": ["涉及的文件或资源路径"],
  "user_intent": "用户本轮想干什么",
  "key_points": ["关键词标签"]
}}"""


async def condense_turn(user_msg: str, ai_msg: str, api_key: str, base_url: str, model: str) -> dict | None:
    """将一轮问答封装为结构化记忆条目（使用独立 API 调用，max_tokens=500）。"""
    from openai import AsyncOpenAI

    try:
        client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        prompt = CONDENSE_PROMPT.format(user_msg=user_msg[:2000], ai_msg=ai_msg[:3000])

        resp = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "你是一个对话记忆封装器。将对话精简为结构化 JSON 条目，只输出 JSON。"},
                {"role": "user", "content": prompt},
            ],
            max_tokens=500,
        )

        text = resp.choices[0].message.content or ""
        text = text.strip()
        # Strip markdown code fence if present
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text
            text = text.strip().rstrip("`").strip()
            if text.startswith("json"):
                text = text[4:].strip()

        return json.loads(text)

    except Exception as e:
        logger.warning("Failed to condense turn: %s", e)
        return None
