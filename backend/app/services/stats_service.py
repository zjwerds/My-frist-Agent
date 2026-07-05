"""Statistics service — tracks token usage and fetches API balance."""

import json
import os
import threading
import logging
import urllib.request
import urllib.error

from app.utils import get_data_dir

logger = logging.getLogger(__name__)

STATS_FILE = os.path.join(get_data_dir(), "stats.json")

_stats_lock = threading.Lock()

_DEFAULT_STATS = {
    "total_prompt_tokens": 0,
    "total_completion_tokens": 0,
    "total_tokens": 0,
    "total_cache_hit_tokens": 0,
    "session_count": 0,
}


def _read_stats() -> dict:
    try:
        with open(STATS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return dict(_DEFAULT_STATS)


def _write_stats(stats: dict) -> None:
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)


def record_usage(prompt_tokens: int = 0, completion_tokens: int = 0, cache_hit_tokens: int = 0) -> dict:
    with _stats_lock:
        stats = _read_stats()
        stats["total_prompt_tokens"] += prompt_tokens
        stats["total_completion_tokens"] += completion_tokens
        stats["total_tokens"] += prompt_tokens + completion_tokens
        stats["total_cache_hit_tokens"] += cache_hit_tokens
        stats["session_count"] += 1
        _write_stats(stats)
    return stats


def fetch_balance(api_key: str, base_url: str = "https://api.deepseek.com") -> dict | None:
    try:
        url = f"{base_url.rstrip('/')}/user/balance"
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"Bearer {api_key}")
        req.add_header("Accept", "application/json")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            infos = data.get("balance_infos", [])
            if infos:
                return {
                    "balance": infos[0].get("total_balance", "0"),
                    "currency": infos[0].get("currency", "CNY"),
                }
            return None
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return None
        logger.warning("HTTP error fetching balance: %s", e)
        return None
    except Exception as e:
        logger.warning("Failed to fetch balance: %s", e)
        return None


def get_stats(api_key: str | None = None, base_url: str | None = None) -> dict:
    stats = _read_stats()
    total_prompt = stats["total_prompt_tokens"]
    cache_hit = stats["total_cache_hit_tokens"]
    stats["cache_hit_rate"] = round(cache_hit / total_prompt, 4) if total_prompt > 0 else 0.0
    if api_key:
        balance = fetch_balance(api_key, base_url or "https://api.deepseek.com")
        if balance:
            stats["balance"] = balance["balance"]
            stats["currency"] = balance["currency"]
    return stats
