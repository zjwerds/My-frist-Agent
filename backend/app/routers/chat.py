import json
import asyncio
import os
import logging
from fastapi import APIRouter, Depends, Query, Body
from fastapi.responses import StreamingResponse
from app.services.tools import PENDING_QUESTION_FILE, _clear_pending_question
from app.database import SessionLocal, get_db

logger = logging.getLogger(__name__)
from sqlalchemy.orm import Session
from app.models.chat import ChatRequest
from app.crud import history as history_crud
from app.services import skill_store
from app.services.agent_service import run_agent_stream
from app.services.deepseek_service import generate_title
from app.services import config_file
from app.services.ocr_service import ocr_image_from_base64
from app.services.stats_service import record_usage
from app.services.conversation_memory import (
    append_entry,
    condense_turn,
)
from app.services.analysis_service import analyze_turn, append_record

router = APIRouter(prefix="/api/chat")


@router.post("")
async def chat(
    request: ChatRequest,
    conversation_id: str = Query(...),
):
    async def event_generator():
        # Create DB session inside generator so it lives as long as the SSE stream
        db = SessionLocal()
        try:
            # Save user message will happen after intent analysis (for cache stability)

            # Read API config from config.json only
            cfg = config_file.read_config()
            if not cfg or not cfg.get("api_key"):
                msg = "请先在左侧菜单「⚙️ API 接口配置」中填写 API Key 并保存，即可开始对话。"
                history_crud.add_message(db, conversation_id, "assistant", msg)
                for chunk in _text_stream(msg):
                    yield chunk
                return

            # Load enabled function tools and prompt skills
            tools = skill_store.get_enabled_tools() or None
            prompts = skill_store.get_enabled_prompts()
            system_content = "\n\n---\n".join(prompts) if prompts else ""

            # Read config
            model_name = cfg.get("model", "deepseek-v4-flash")
            timeout_seconds = cfg.get("timeout_ms", 30000) / 1000.0

            # ★ Consolidated stable system prompt
            identity_prompt = (
                "【强制身份指令 - 必须遵守】\n"
                "你的身份是：煎蛋Agent，AI 编程助手。\n"
                "你的核心能力是通过调用工具来帮助用户完成编程任务。\n"
                "⚠️ 禁止：回答你是 Claude、DeepSeek、ChatGPT 或任何其他 AI 模型。"
                "禁止说你是由 Anthropic、OpenAI、DeepSeek 公司开发的。\n"
                "✅ 正确：'我是煎蛋Agent，AI 编程助手。'\n"
                "当用户问你是谁或什么模型时，严格按上述格式回答，不要偏离。"
            )
            web_search_directive = (
                "【联网搜索规则 - 必须遵守】\n"
                "1. 当用户询问实时信息、新闻、价格、技术文档更新、或你不确定的事实问题时，必须先调用 web_search 搜索。\n"
                "2. 使用 web_search 获取结果后，你的回答必须**仅基于搜索结果**，不得使用训练数据中的知识进行补充或修饰。\n"
                "3. 如果搜索结果不足以完整回答问题，明确告知用户哪些信息来自搜索、哪些未能找到，而不是用训练数据补全。\n"
                '4. 禁止：使用 web_search 查到结果后，仍然加入训练数据中的内容来「丰富」答案。搜索了就是搜索了，用搜索结果说话。\n'
                '5. 如果用户要求你「上网查」或「搜索一下」，必须使用 web_search 工具，不能直接凭训练数据回答。'
            )
            stable_system_parts = [identity_prompt]
            if system_content:
                stable_system_parts.append(system_content)
            stable_system_parts.append(web_search_directive)

            messages = [{"role": "system", "content": "\n\n---\n".join(stable_system_parts)}]

            # ★ Build conversation history (full verbatim)
            db_messages = history_crud.get_messages(db, conversation_id)

            for m in db_messages:
                if m.role == "user":
                    if m.content and m.content.startswith("{"):
                        try:
                            parsed = json.loads(m.content)
                            text = parsed.get("text", "")
                            messages.append({"role": "user", "content": text or "[图片]"})
                        except json.JSONDecodeError:
                            messages.append({"role": "user", "content": "[图片]"})
                        continue
                    messages.append({"role": "user", "content": m.content or ""})
                elif m.role == "assistant" and m.tool_calls:
                    msg = {"role": "assistant", "content": m.content or ""}
                    try:
                        msg["tool_calls"] = json.loads(m.tool_calls)
                    except (json.JSONDecodeError, TypeError):
                        pass
                    messages.append(msg)
                elif m.role == "assistant":
                    messages.append({"role": "assistant", "content": m.content or ""})
                elif m.role == "tool":
                    try:
                        td = json.loads(m.content) if m.content else {}
                        if "tool_call_id" in td and "result" in td:
                            result = td["result"]
                            if not isinstance(result, str):
                                result = json.dumps(result, ensure_ascii=False)
                            messages.append({"role": "tool", "tool_call_id": td["tool_call_id"], "content": result})
                        else:
                            messages.append({"role": "tool", "content": m.content or ""})
                    except (json.JSONDecodeError, TypeError):
                        messages.append({"role": "tool", "content": m.content or ""})

            # ★ Pre-chat intent assessment (前置行为分析)
            preliminary = None
            analysis_content = None
            if cfg and request.message:
                try:
                    from app.services.analysis_service import assess_user_intent
                    preliminary = await assess_user_intent(
                        user_msg=request.message,
                        api_key=cfg["api_key"],
                        base_url=cfg.get("base_url", "https://api.deepseek.com"),
                        model=model_name,
                    )
                except Exception:
                    pass  # non-blocking

            if preliminary:
                guidance = preliminary.get("reply_guidance")
                enriched = preliminary.get("enriched_question")
                guidance_parts = []
                if enriched:
                    guidance_parts.append(f"用户真实意图: {enriched}")
                if guidance:
                    guidance_parts.append(f"回答建议: {guidance}")
                if guidance_parts:
                    analysis_content = "【前置分析】\n" + "\n".join(guidance_parts)

            # ★ Current user message
            if request.images:
                ocr_texts = []
                for data_uri in request.images:
                    text = ocr_image_from_base64(data_uri)
                    if text:
                        ocr_texts.append(text)
                if ocr_texts:
                    combined = request.message + "\n\n[图片中的文字]\n" + "\n---\n".join(ocr_texts)
                else:
                    combined = request.message + "\n\n[图片中未能识别出文字内容，无法读取图片信息]"
                current_user_msg = {"role": "user", "content": combined}
            else:
                current_user_msg = {"role": "user", "content": request.message}

            # Prepend analysis to user message (keep system prompt prefix stable for KV cache)
            if analysis_content:
                current_user_msg["content"] = analysis_content + "\n\n---\n" + current_user_msg["content"]

            # Save user message (use enhanced content for cache prefix stability)
            if not request.edit_mode:
                if request.images:
                    content_to_save = json.dumps({"text": current_user_msg["content"], "images": request.images}, ensure_ascii=False)
                else:
                    content_to_save = current_user_msg["content"]
                history_crud.add_message(db, conversation_id, "user", content_to_save)

            messages.append(current_user_msg)

            # Get conversation for project_path context
            conv = history_crud.get_conversation(db, conversation_id)
            project_path = conv.project_path if conv else None

            full_response = ""
            tool_calls_batch: list[dict] = []
            current_tool_call_id: str | None = None

            try:
                async for event in run_agent_stream(
                    messages=messages,
                    api_key=cfg["api_key"],
                    base_url=cfg.get("base_url", "https://api.deepseek.com"),
                    model=model_name,
                    tools=tools,
                    conversation_id=conversation_id,
                    temperature=request.temperature,
                    project_path=project_path,
                    timeout=timeout_seconds,
                ):
                    yield f"event: {event['event']}\ndata: {event['data']}\n\n"

                    if event["event"] == "text_chunk":
                        data = json.loads(event["data"])
                        full_response += data["content"]

                    if event["event"] == "tool_call_start":
                        ed = json.loads(event["data"])
                        current_tool_call_id = ed.get("tool_call_id", "")
                        tool_calls_batch.append({
                            "id": current_tool_call_id,
                            "type": "function",
                            "function": {"name": ed.get("tool_name", ""), "arguments": ed.get("arguments", "")},
                        })

                    if event["event"] == "tool_call_result":
                        ed = json.loads(event["data"])
                        if tool_calls_batch:
                            history_crud.add_message(
                                db, conversation_id, "assistant",
                                content="",
                                tool_calls=json.dumps(tool_calls_batch, ensure_ascii=False),
                            )
                            tool_calls_batch = []
                        history_crud.add_message(
                            db, conversation_id, "tool",
                            content=json.dumps({
                                "tool_call_id": current_tool_call_id or "",
                                "result": ed.get("result", ""),
                            }, ensure_ascii=False),
                        )

                    if event["event"] == "usage":
                        data = json.loads(event["data"])
                        record_usage(
                            prompt_tokens=data.get("prompt_tokens", 0),
                            completion_tokens=data.get("completion_tokens", 0),
                            cache_hit_tokens=data.get("cache_hit_tokens", 0),
                        )

                # Save assistant response
                if full_response:
                    history_crud.add_message(db, conversation_id, "assistant", full_response)

                # ★ 异步触发记忆封装 + 行为分析
                if full_response and cfg:
                    asyncio.ensure_future(
                        _condense_and_save(
                            conversation_id=conversation_id,
                            user_msg=request.message or "",
                            ai_msg=full_response,
                            api_key=cfg["api_key"],
                            base_url=cfg.get("base_url", "https://api.deepseek.com"),
                            model=model_name,
                        )
                    )
                    asyncio.ensure_future(
                        _analyze_and_record(
                            user_msg=request.message or "",
                            ai_msg=full_response,
                            api_key=cfg["api_key"],
                            base_url=cfg.get("base_url", "https://api.deepseek.com"),
                            model=model_name,
                        )
                    )

                # AI-refined title for new conversations (≤13 chars)
                conv = history_crud.get_conversation(db, conversation_id)
                if conv and conv.message_count == 1:
                    title = await generate_title(
                        cfg["api_key"],
                        cfg.get("base_url", "https://api.deepseek.com"),
                        model_name,
                        request.message or (request.images and "图片消息" or ""),
                        full_response or "",
                    )
                    if title:
                        conv.title = title[:13]
                        db.commit()

                yield "event: done\ndata: [DONE]\n\n"

            except Exception as e:
                logger.error("Chat stream error: %s", e)
                yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
                yield "event: done\ndata: [DONE]\n\n"

        except Exception as e:
            logger.error("Chat setup error: %s", e)
            yield f"event: error\ndata: {json.dumps({'error': f'聊天初始化失败: {str(e)}'})}\n\n"
            yield "event: done\ndata: [DONE]\n\n"
        finally:
            db.close()

    return StreamingResponse(event_generator(), media_type="text/event-stream")


def _text_stream(text: str):
    """Stream a plain text message as a normal assistant reply (SSE text_chunk + done)."""
    async def gen():
        yield f"event: text_chunk\ndata: {json.dumps({'content': text})}\n\n"
        yield "event: done\ndata: [DONE]\n\n"
    return gen()


async def _condense_and_save(
    conversation_id: str,
    user_msg: str,
    ai_msg: str,
    api_key: str,
    base_url: str,
    model: str,
):
    """异步封装一轮问答并写入记忆文件（出错不影响主流程）。"""
    entry = await condense_turn(user_msg, ai_msg, api_key, base_url, model)
    if entry:
        append_entry(conversation_id, entry)
    else:
        # 封装失败时写入兜底条目
        append_entry(conversation_id, {
            "summary": ai_msg[:200],
            "constraints": [],
            "decisions": [],
            "artifacts": [],
            "user_intent": user_msg[:100] if user_msg else "未知",
            "key_points": [],
        })


async def _analyze_and_record(
    user_msg: str,
    ai_msg: str,
    api_key: str,
    base_url: str,
    model: str,
):
    """异步分析一轮问答质量并写入用户行为文件（出错不影响主流程）。"""
    result = await analyze_turn(user_msg, ai_msg, api_key, base_url, model)
    if result:
        append_record(result)
    else:
        # 分析失败时写入一条简单记录
        append_record({
            "original_question": user_msg[:200],
            "enriched_question": "分析失败，使用原始问题",
            "rating": "positive",
            "behavior_analysis": "无法分析",
            "satisfaction_reason": "无法分析",
        })


@router.get("/pending-question")
def get_pending_question():
    """Return the current pending question, or null if none."""
    if not os.path.exists(PENDING_QUESTION_FILE):
        return {"question": None}
    try:
        with open(PENDING_QUESTION_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {"question": data.get("question", ""), "question_id": data.get("question_id", ""), "options": data.get("options", [])}
    except (json.JSONDecodeError, OSError):
        return {"question": None}


@router.post("/answer-question")
def answer_question(body: dict = Body(...)):
    """Accept an answer to a pending question and clear it."""
    answer = body.get("answer", "")
    _clear_pending_question()
    return {"success": True, "answer": answer}
