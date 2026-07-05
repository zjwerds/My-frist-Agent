"""LLM utility functions — shared client creation, response parsing, JSON extraction."""

import json
import logging
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


def strip_code_fence(text: str) -> str:
    """Remove markdown code fences and optional json/lang tag from LLM output."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        text = text.strip().rstrip("`").strip()
        if text.startswith("json"):
            text = text[4:].strip()
    return text


async def call_llm_json(
    system_prompt: str,
    user_prompt: str,
    api_key: str,
    base_url: str,
    model: str,
    max_tokens: int = 500,
) -> dict | None:
    """Call an LLM and parse the response as JSON. Returns None on failure."""
    try:
        client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        resp = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=max_tokens,
        )
        text = resp.choices[0].message.content or ""
        text = strip_code_fence(text)
        return json.loads(text)
    except Exception as e:
        logger.warning("LLM JSON call failed: %s", e)
        return None
