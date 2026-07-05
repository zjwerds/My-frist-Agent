import json
import asyncio
import logging
from app.services.deepseek_service import create_async_client, chat_completion_stream_async
from app.services.tools import execute_tool

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 50


async def run_agent_stream(
    messages: list[dict],
    api_key: str,
    base_url: str,
    model: str,
    tools: list[dict] | None = None,
    conversation_id: str = "",
    temperature: float | None = None,
    project_path: str | None = None,
    timeout: float | None = None,
):
    """Run the agent ReAct loop and yield SSE events."""
    client = create_async_client(api_key, base_url, timeout=timeout)
    current_messages = list(messages)
    total_prompt = 0
    total_completion = 0
    total_cache = 0

    def _emit_done(reason: str = ""):
        return {"event": "done", "data": json.dumps({"reason": reason})}

    def _emit_usage():
        return {
            "event": "usage",
            "data": json.dumps({
                "prompt_tokens": total_prompt,
                "completion_tokens": total_completion,
                "cache_hit_tokens": total_cache,
            }),
        }

    for iteration in range(MAX_ITERATIONS):
        # ── LLM API call with error protection ──
        try:
            stream = await chat_completion_stream_async(client, current_messages, model, tools, temperature=temperature)
        except Exception as e:
            logger.error("LLM API call failed (iteration %d): %s", iteration, e)
            yield {"event": "error", "data": json.dumps({"error": f"LLM API 调用失败: {str(e)}"})}
            return

        response_text = ""
        tool_calls = []
        usage = None

        # ── Stream iteration with error protection ──
        try:
            async for chunk in stream:
                if chunk.usage:
                    usage = chunk.usage
                delta = chunk.choices[0].delta if chunk.choices else None
                if not delta:
                    continue

                if delta.content:
                    response_text += delta.content
                    yield {"event": "text_chunk", "data": json.dumps({"content": delta.content})}

                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        while len(tool_calls) <= tc.index:
                            tool_calls.append({"id": "", "type": "function", "function": {"name": "", "arguments": ""}})
                        if tc.id:
                            tool_calls[tc.index]["id"] = tc.id
                        if tc.function:
                            if tc.function.name:
                                tool_calls[tc.index]["function"]["name"] += tc.function.name
                            if tc.function.arguments:
                                tool_calls[tc.index]["function"]["arguments"] += tc.function.arguments
        except Exception as e:
            logger.error("LLM stream interrupted (iteration %d): %s", iteration, e)
            yield {"event": "error", "data": json.dumps({"error": f"LLM 响应流中断: {str(e)}"})}
            return

        if usage:
            total_prompt += usage.prompt_tokens or 0
            total_completion += usage.completion_tokens or 0
            # Try different cache token field names (OpenAI vs DeepSeek API）
            cached = getattr(usage, "prompt_cache_hit_tokens", None)
            if cached is None and hasattr(usage, "prompt_tokens_details"):
                cached = getattr(usage.prompt_tokens_details, "cached_tokens", None)
            total_cache += cached or 0

        # If no tool calls, emit usage + done and we're done
        if not tool_calls:
            yield _emit_usage()
            yield _emit_done("completed")
            return

        # Process tool calls
        current_messages.append({"role": "assistant", "content": response_text or None, "tool_calls": tool_calls})

        for tc in tool_calls:
            tool_name = tc["function"]["name"]
            try:
                args = json.loads(tc["function"]["arguments"])
            except json.JSONDecodeError:
                args = {}

            yield {
                "event": "tool_call_start",
                "data": json.dumps({"tool_name": tool_name, "arguments": tc["function"]["arguments"], "tool_call_id": tc["id"]}),
            }

            # Collect all images from conversation context for OCR tool
            all_images = []
            for msg in current_messages:
                if msg["role"] == "user" and isinstance(msg.get("content"), list):
                    for part in msg["content"]:
                        if part.get("type") == "image_url":
                            all_images.append(part["image_url"]["url"])

            context = {
                "all_images": all_images,
                "conversation_id": conversation_id,
                "project_path": project_path or "",
            } if tool_name in ("ocr_image", "search_memory", "file_read") else {}
            result = await execute_tool(tool_name, args, context)

            yield {
                "event": "tool_call_result",
                "data": json.dumps({"tool_name": tool_name, "result": result}),
            }

            # ★ AskUser: if the tool returned a question, yield ask_user event and stop
            try:
                result_data = json.loads(result)
                if result_data.get("__type") == "ask_user":
                    yield {
                        "event": "ask_user",
                        "data": json.dumps({
                            "question_id": result_data.get("question_id", ""),
                            "question": result_data.get("question", ""),
                            "options": result_data.get("options", []),
                        }),
                    }
                    yield _emit_usage()
                    yield _emit_done("ask_user")
                    return
            except (json.JSONDecodeError, TypeError):
                pass

            current_messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": result,
            })

    # Max iterations reached — yield usage and done events before returning
    yield _emit_usage()
    yield _emit_done("max_iterations")
