"""Manage a user-facing config.json file alongside SQLite.
This lets users see and edit their API config directly.
config.json is placed next to agent.db (see app.utils.get_data_dir).

Configuration structure (v2):
{
  "meta": { "version", "description", "last_updated" },
  "auth": { "api_key", "key_source" },
  "api":  { "base_url", "model", "timeout_ms", "max_retries" }
}
"""

import json
import os
import logging
from datetime import datetime, timezone
from app.utils import get_data_dir

logger = logging.getLogger(__name__)

CONFIG_FILE = os.path.join(get_data_dir(), "config.json")

_DEFAULTS = {
    "base_url": "https://api.deepseek.com",
    "model": "deepseek-v4-flash",
}


def _read_raw() -> dict | None:
    """Read the raw config.json content. Returns None if not exists."""
    if not os.path.exists(CONFIG_FILE):
        return None
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def read_config() -> dict | None:
    """Read API config and return a flat dict with api_key, base_url, model, timeout_ms.

    Handles both the new structured format (v2) and the legacy flat format (v1).
    Consumers continue to access cfg.get("api_key") / cfg.get("base_url") / cfg.get("model").
    """
    raw = _read_raw()
    if raw is None:
        return None

    # New structured format (v2+): extract flat fields
    if "auth" in raw or "api" in raw:
        auth = raw.get("auth", {})
        api = raw.get("api", {})
        return {
            "api_key": auth.get("api_key", ""),
            "base_url": api.get("base_url", _DEFAULTS["base_url"]),
            "model": api.get("model", _DEFAULTS["model"]),
            "timeout_ms": api.get("timeout_ms", 30000),
        }

    # Legacy flat format (v1)
    return {
        "api_key": raw.get("api_key", ""),
        "base_url": raw.get("base_url", _DEFAULTS["base_url"]),
        "model": raw.get("model", _DEFAULTS["model"]),
        "timeout_ms": raw.get("timeout_ms", 30000),
    }




def write_config(api_key: str, base_url: str, model: str) -> dict:
    """Write API config to config.json in the new structured format.

    Returns flat dict for backward compat with callers.
    """
    config = {
        "meta": {
            "version": "2.0.0",
            "description": "煎蛋Agent 配置",
            "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        },
        "auth": {
            "api_key": api_key,
            "key_source": "file",
        },
        "api": {
            "base_url": base_url,
            "model": model,
            "timeout_ms": 30000,
            "max_retries": 3,
        },
    }
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    return {"api_key": api_key, "base_url": base_url, "model": model}


def clear_config() -> None:
    """Remove the config.json file."""
    if os.path.exists(CONFIG_FILE):
        os.remove(CONFIG_FILE)
