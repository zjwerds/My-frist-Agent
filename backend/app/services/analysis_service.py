"""对话分析服务 — 评估问答质量、记录用户行为、生成综合报告。"""

import re
import os
import json
import logging
from datetime import datetime
from typing import Optional
from app.utils import get_data_dir, BEIJING

logger = logging.getLogger(__name__)

ANALYSIS_DIR = os.path.join(get_data_dir(), "analysis")

ANALYSIS_PROMPT = """你是一个对话质量分析器。分析以下问答对，输出 JSON 格式评估。

用户问题：{user_msg}
AI回答：{ai_msg}

请分析：
1. 用户的原始问题是什么
2. 用户的真实需求/意图是什么（有时问题背后有更深层需求，用户可能没有明确表达）
3. 回答是否满足了用户需求（positive/negative）
4. 用户行为特征分析（用户的提问方式、习惯、知识水平、沟通风格等）
5. 如未满足，可能的原因是什么
6. 满足的情况下，回答在哪个方面解决了用户问题

输出格式（仅 JSON，不要多余内容）：
{{
  "original_question": "用户的原始问题",
  "enriched_question": "用户的真实需求和深层意图（对比原始问题的差异）",
  "rating": "positive",
  "behavior_analysis": "用户行为特征分析",
  "satisfaction_reason": "满足或未满足需求的原因分析"
}}

注意：rating 的取值只能是 "positive" 或 "negative"。
"""

PRELIMINARY_PROMPT = """你是一个对话前置分析器。在 AI 回答用户之前，先分析用户的提问。

用户问题：{user_msg}

请分析：
1. 用户的原始问题是什么
2. 用户的真实需求/深层意图是什么（原始问题可能没有完全表达）
3. 用户的行为特征（提问方式、沟通风格、知识水平）
4. 回答建议（AI 应该注意什么，以什么方式回答最好）

输出格式（仅 JSON，不要多余内容）：
{{
  "original_question": "用户的原始问题",
  "enriched_question": "用户的真实需求和深层意图",
  "user_state": "用户的情绪或状态（curious/frustrated/urgent/exploring/unsure）",
  "behavior_traits": "本次提问的行为特征",
  "reply_guidance": "对 AI 回答的建议"
}}
"""


def _ensure_dir():
    os.makedirs(ANALYSIS_DIR, exist_ok=True)


def _ts() -> str:
    return datetime.now(BEIJING).isoformat()


def _date_str() -> str:
    return datetime.now(BEIJING).strftime("%Y-%m-%d")


def _analysis_path() -> str:
    return os.path.join(ANALYSIS_DIR, "user_behavior.md")


def _count_records(content: str) -> int:
    """统计文件中 Q&A 记录的条数。"""
    matches = re.findall(r"^### Q&A #(\d+)", content, re.MULTILINE)
    if not matches:
        return 0
    return max(int(m) for m in matches)


async def analyze_turn(
    user_msg: str,
    ai_msg: str,
    api_key: str,
    base_url: str,
    model: str,
) -> Optional[dict]:
    """调用 LLM 分析一轮问答的质量和用户行为。"""
    from openai import AsyncOpenAI

    try:
        client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        prompt = ANALYSIS_PROMPT.format(
            user_msg=user_msg[:2000],
            ai_msg=ai_msg[:3000],
        )

        resp = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "你是一个对话质量分析器。只输出 JSON。"},
                {"role": "user", "content": prompt},
            ],
            max_tokens=600,
        )

        text = resp.choices[0].message.content or ""
        text = text.strip()
        # Strip markdown code fence
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text
            text = text.strip().rstrip("`").strip()
            if text.startswith("json"):
                text = text[4:].strip()

        result = json.loads(text)
        if "rating" not in result:
            result["rating"] = "positive"
        return result

    except Exception as e:
        logger.warning("Failed to analyze turn: %s", e)
        return None


async def assess_user_intent(
    user_msg: str,
    api_key: str,
    base_url: str,
    model: str,
) -> Optional[dict]:
    """在 AI 回答之前，前置分析用户问题的意图和特征。

    返回结构化评估结果，可用于增强 system prompt。
    出错时返回 None（不影响主流程）。
    """
    from openai import AsyncOpenAI

    try:
        client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        prompt = PRELIMINARY_PROMPT.format(user_msg=user_msg[:2000])

        resp = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "你是一个对话前置分析器。只输出 JSON。"},
                {"role": "user", "content": prompt},
            ],
            max_tokens=400,
        )

        text = resp.choices[0].message.content or ""
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text
            text = text.strip().rstrip("`").strip()
            if text.startswith("json"):
                text = text[4:].strip()

        result = json.loads(text)
        return result

    except Exception as e:
        logger.warning("Failed to assess user intent: %s", e)
        return None


def append_record(analysis: dict):
    """写入一条格式化分析记录到 user_behavior.md，在里程碑处插入小结。"""
    _ensure_dir()
    path = _analysis_path()
    today = _date_str()
    now_ts = _ts()

    content = ""
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            content = f.read().strip()

    total_before = _count_records(content)
    record_num = total_before + 1

    rating_display = "✅ 满足需求" if analysis.get("rating") == "positive" else "❌ 未满足需求"

    entry = (
        f"\n### Q&A #{record_num}\n"
        f"**时间**: {now_ts}\n"
        f"**原始问题**: {analysis.get('original_question', '未知')}\n"
        f"**理解后问题**: {analysis.get('enriched_question', '未知')}\n"
        f"**评价**: {rating_display}\n"
        f"**行为分析**: {analysis.get('behavior_analysis', '无')}\n"
        f"**原因**: {analysis.get('satisfaction_reason', '无')}\n"
    )

    today_header = f"## {today}"

    if not content:
        # 全新文件
        content = f"# 用户行为分析\n\n{today_header}\n{entry}"
    elif today_header in content:
        # 追加到今天 section 末尾
        lines = content.split("\n")
        today_line_idx = None
        for i, line in enumerate(lines):
            if line.startswith(today_header):
                today_line_idx = i
                break

        # 找今天的 section 之后的下一个 ## header
        next_header_idx = None
        for i in range(today_line_idx + 1, len(lines)):
            if lines[i].startswith("## "):
                next_header_idx = i
                break

        if next_header_idx is not None:
            lines.insert(next_header_idx, entry.strip())
        else:
            lines.append(entry.strip())
        content = "\n".join(lines)
    else:
        # 新的一天
        content += f"\n\n{today_header}\n{entry}"

    with open(path, "w", encoding="utf-8") as f:
        f.write(content + "\n")

    # 里程碑检查
    total = record_num
    if total >= 10 and total % 10 == 0:
        _insert_major_summary(path, total)
    if total >= 100 and total % 100 == 0:
        _insert_user_analysis(path, total)


def _insert_major_summary(path: str, total: int):
    """插入阶段小结（每 10 条记录）。"""
    summary_num = total // 10
    start_record = total - 9
    text = (
        f"\n---\n"
        f"### 📊 阶段小结 #{summary_num}\n"
        f"**时间**: {_ts()}\n"
        f"**覆盖记录**: 第 {start_record} - {total} 条\n\n"
        f"*（由 AI 自动生成）*\n"
    )
    with open(path, "a", encoding="utf-8") as f:
        f.write(text + "\n")
    logger.info("Inserted major summary #%d (records %d-%d)", summary_num, start_record, total)


def _insert_user_analysis(path: str, total: int):
    """插入用户画像分析（每 100 条记录）。"""
    analysis_num = total // 100
    text = (
        f"\n---\n"
        f"## 🧠 用户画像分析 #{analysis_num}\n"
        f"**时间**: {_ts()}\n"
        f"**覆盖记录**: 第 1 - {total} 条\n\n"
        f"*（由 AI 自动生成，基于 {total} 条对话记录的综合分析）*\n"
    )
    with open(path, "a", encoding="utf-8") as f:
        f.write(text + "\n")
    logger.info("Inserted user analysis #%d (total records: %d)", analysis_num, total)


async def generate_daily_report():
    """生成每日综合分析报告（由调度器在每天 10pm 调用）。"""
    from app.services import config_file
    from openai import AsyncOpenAI

    path = _analysis_path()
    if not os.path.exists(path):
        logger.info("No analysis data yet, skipping daily report")
        return

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    records = _count_records(content)
    if records == 0:
        logger.info("No records in analysis file, skipping daily report")
        return

    # 获取今天的日期作为文件名
    today = _date_str()
    report_path = os.path.join(ANALYSIS_DIR, f"daily_report_{today}.md")

    # 读取配置
    cfg = config_file.read_config()
    if not cfg or not cfg.get("api_key"):
        logger.warning("No API config for daily report generation")
        # 生成一个基于已有数据的简单报告
        _write_simple_report(report_path, content, records, today)
        return

    try:
        client = AsyncOpenAI(api_key=cfg["api_key"], base_url=cfg.get("base_url", "https://api.deepseek.com"))

        # 计算 positive/negative 比例
        positive = len(re.findall(r"✅ 满足需求", content))
        negative = len(re.findall(r"❌ 未满足需求", content))

        # 截取内容用于分析（取最近 50 条和所有小结）
        summary_sections = re.findall(r"(### 📊 阶段小结.*?)(?=###|\Z)", content, re.DOTALL)

        report_prompt = f"""基于以下用户行为分析数据，生成一份每日综合分析报告。

总记录数: {records}
今日新增记录: 待统计
满足需求: {positive} 次
未满足需求: {negative} 次
满意度: {positive / max(positive + negative, 1) * 100:.1f}%

阶段小结:
{chr(10).join(summary_sections[-5:]) if summary_sections else '暂无小结'}

请输出（仅 JSON）：
{{
  "daily_summary": "今日对话总体情况概述",
  "satisfaction_trend": "满意度趋势分析",
  "user_behavior_insight": "用户行为模式洞察",
  "common_topics": "今日主要话题",
  "improvement_suggestions": "改进建议"
}}"""

        resp = await client.chat.completions.create(
            model=cfg.get("model", "deepseek-v4-flash"),
            messages=[
                {"role": "system", "content": "你是一个用户行为分析报告生成器。只输出 JSON。"},
                {"role": "user", "content": report_prompt},
            ],
            max_tokens=800,
        )

        text = resp.choices[0].message.content or ""
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text
            text = text.strip().rstrip("`").strip()
            if text.startswith("json"):
                text = text[4:].strip()

        report_data = json.loads(text)

        report = (
            f"# 每日综合分析报告 — {today}\n\n"
            f"## 数据概览\n"
            f"- 累计记录数: {records}\n"
            f"- 满足需求: {positive} 次\n"
            f"- 未满足需求: {negative} 次\n"
            f"- 满意度: {positive / max(positive + negative, 1) * 100:.1f}%\n\n"
            f"## 今日总结\n"
            f"{report_data.get('daily_summary', '无')}\n\n"
            f"## 满意度趋势\n"
            f"{report_data.get('satisfaction_trend', '无')}\n\n"
            f"## 用户行为洞察\n"
            f"{report_data.get('user_behavior_insight', '无')}\n\n"
            f"## 主要话题\n"
            f"{report_data.get('common_topics', '无')}\n\n"
            f"## 改进建议\n"
            f"{report_data.get('improvement_suggestions', '无')}\n\n"
            f"---\n"
            f"*报告生成时间: {_ts()}*\n"
        )

    except Exception as e:
        logger.warning("Failed to generate AI daily report: %s", e)
        _write_simple_report(report_path, content, records, today)
        return

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    logger.info("Daily report generated: %s", report_path)


def _write_simple_report(report_path: str, content: str, records: int, today: str):
    """生成一个不依赖 LLM 的简单数据报告。"""
    positive = len(re.findall(r"✅ 满足需求", content))
    negative = len(re.findall(r"❌ 未满足需求", content))
    report = (
        f"# 每日数据报告 — {today}\n\n"
        f"## 数据概览\n"
        f"- 累计记录数: {records}\n"
        f"- 满足需求: {positive} 次\n"
        f"- 未满足需求: {negative} 次\n"
        f"- 满意度: {positive / max(positive + negative, 1) * 100:.1f}%\n\n"
        f"---\n"
        f"*报告生成时间: {_ts()}*\n"
    )
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    logger.info("Simple daily report generated: %s", report_path)
