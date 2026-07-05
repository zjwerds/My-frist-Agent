import time
import logging
from functools import lru_cache
from openai import OpenAI, AsyncOpenAI

logger = logging.getLogger(__name__)

_client_cache: dict[str, OpenAI] = {}
_async_client_cache: dict[str, AsyncOpenAI] = {}


def _client_key(api_key: str, base_url: str) -> str:
    return f"{api_key}@{base_url}"


def create_client(api_key: str, base_url: str = "https://api.deepseek.com") -> OpenAI:
    key = _client_key(api_key, base_url)
    if key not in _client_cache:
        _client_cache[key] = OpenAI(api_key=api_key, base_url=base_url)
    return _client_cache[key]


def create_async_client(api_key: str, base_url: str = "https://api.deepseek.com", timeout: float | None = None) -> AsyncOpenAI:
    key = _client_key(api_key, base_url)
    if key not in _async_client_cache:
        kwargs = {"api_key": api_key, "base_url": base_url}
        if timeout is not None:
            kwargs["timeout"] = timeout
        _async_client_cache[key] = AsyncOpenAI(**kwargs)
    return _async_client_cache[key]


def chat_completion_stream(
    client: OpenAI,
    messages: list[dict],
    model: str = "deepseek-v4-flash",
    tools: list[dict] | None = None,
    temperature: float | None = None,
):
    kwargs = dict(
        model=model,
        messages=messages,
        tools=tools,
        tool_choice="auto" if tools else None,
        stream=True,
        stream_options={"include_usage": True},
        max_tokens=8192,
    )
    if temperature is not None:
        kwargs["temperature"] = temperature
    return client.chat.completions.create(**kwargs)


async def chat_completion_stream_async(
    client: AsyncOpenAI,
    messages: list[dict],
    model: str = "deepseek-v4-flash",
    tools: list[dict] | None = None,
    temperature: float | None = None,
):
    kwargs = dict(
        model=model,
        messages=messages,
        tools=tools,
        tool_choice="auto" if tools else None,
        stream=True,
        stream_options={"include_usage": True},
        max_tokens=8192,
    )
    if temperature is not None:
        kwargs["temperature"] = temperature
    return await client.chat.completions.create(**kwargs)


async def generate_title(
    api_key: str, base_url: str, model: str,
    user_message: str, assistant_response: str,
) -> str | None:
    """Use the AI model to generate a concise conversation title (≤13 chars)."""
    try:
        client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        resp = await client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "根据对话内容生成一个简短的中文标题（不超过13个字）。"
                        "只返回标题本身，不要任何标点符号、引号或额外内容。"
                    ),
                },
                {
                    "role": "user",
                    "content": f"用户的问题：{user_message}\n\nAI的回复：{assistant_response}",
                },
            ],
            max_tokens=20,
        )
        title = resp.choices[0].message.content
        if title:
            title = title.strip().strip('"').strip("'").strip("「").strip("」")
            return title[:13] if title else None
        return None
    except Exception as e:
        logger.warning("generate_title failed: %s", e)
        return None


def test_connection(api_key: str, base_url: str, model: str) -> tuple[bool, int, str | None]:
    try:
        client = create_client(api_key, base_url)
        start = time.time()
        client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=5,
        )
        latency = int((time.time() - start) * 1000)
        return True, latency, None
    except Exception as e:
        return False, 0, str(e)
