"""Ask user, plan, subagent, schedule, and task tracking tools."""

import json
import os
import time
from datetime import datetime, timezone
from app.utils import get_data_dir

TASKS_FILE = os.path.join(get_data_dir(), "tasks.json")
PENDING_QUESTION_FILE = os.path.join(get_data_dir(), "pending_question.json")


def _clear_pending_question():
    if os.path.exists(PENDING_QUESTION_FILE):
        os.remove(PENDING_QUESTION_FILE)


def _read_tasks() -> dict:
    try:
        with open(TASKS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _write_tasks(tasks: dict) -> None:
    os.makedirs(os.path.dirname(TASKS_FILE), exist_ok=True)
    with open(TASKS_FILE, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)


async def _ask_user(args: dict) -> dict:
    question = args.get("question", "")
    if not question:
        return {"error": "缺少 question 参数"}

    options = args.get("options", [])
    qid = f"q_{int(time.time() * 1000)}"

    pending = {
        "question_id": qid, "question": question, "options": options,
        "created_at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
    }
    with open(PENDING_QUESTION_FILE, "w", encoding="utf-8") as f:
        json.dump(pending, f, ensure_ascii=False, indent=2)

    return {"__type": "ask_user", "question_id": qid, "question": question, "options": options, "status": "pending"}


async def _enter_plan(args: dict) -> dict:
    title = args.get("title", "无标题计划")
    steps = args.get("steps", [])
    context = args.get("context", "")

    if not steps:
        return {"error": "缺少 steps 参数，至少需要1个步骤"}

    plan_id = f"plan_{int(time.time() * 1000)}"
    plan_dir = os.path.join(get_data_dir(), "plans")
    os.makedirs(plan_dir, exist_ok=True)

    lines = [f"# {title}", "", f"**计划ID**: {plan_id}", f"**创建时间**: {datetime.now().isoformat()}", ""]
    if context:
        lines.extend(["## 背景上下文", "", context, ""])
    lines.append("## 实施步骤")
    for i, step in enumerate(steps, 1):
        lines.extend([f"", f"  - [ ] {step}"])
    lines.append("")

    content = "\n".join(lines)
    plan_path = os.path.join(plan_dir, f"{plan_id}.md")
    with open(plan_path, "w", encoding="utf-8") as f:
        f.write(content)

    return {
        "plan_id": plan_id, "title": title,
        "steps": [{"step": i, "description": s, "status": "pending"} for i, s in enumerate(steps, 1)],
        "total_steps": len(steps), "plan_content": content,
        "message": f"计划「{title}」已创建，共 {len(steps)} 个步骤。",
    }


async def _spawn_subagent(args: dict) -> dict:
    task_desc = args.get("task_description", "")
    context = args.get("context", "")

    if not task_desc:
        return {"error": "缺少 task_description 参数"}

    sub_id = f"sub_{int(time.time() * 1000)}"
    sub_dir = os.path.join(get_data_dir(), "subagents")
    os.makedirs(sub_dir, exist_ok=True)

    sub_task = {
        "subagent_id": sub_id, "task_description": task_desc, "context": context,
        "status": "pending", "created_at": datetime.now().isoformat(), "result": None,
    }
    sub_path = os.path.join(sub_dir, f"{sub_id}.json")
    with open(sub_path, "w", encoding="utf-8") as f:
        json.dump(sub_task, f, ensure_ascii=False, indent=2)

    return {"subagent_id": sub_id, "task_description": task_desc, "status": "pending", "message": f"子任务已创建（ID: {sub_id}）。"}


async def _schedule_task(args: dict) -> dict:
    prompt = args.get("prompt", "")
    cron = args.get("cron", "")
    recurring = args.get("recurring", True)

    if not prompt or not cron:
        return {"error": "缺少 prompt 或 cron 参数"}

    sched_id = f"sched_{int(time.time() * 1000)}"
    sched_dir = os.path.join(get_data_dir(), "scheduled")
    os.makedirs(sched_dir, exist_ok=True)

    schedule = {
        "schedule_id": sched_id, "prompt": prompt, "cron": cron,
        "recurring": recurring, "created_at": datetime.now().isoformat(), "status": "active",
    }
    sched_path = os.path.join(sched_dir, f"{sched_id}.json")
    with open(sched_path, "w", encoding="utf-8") as f:
        json.dump(schedule, f, ensure_ascii=False, indent=2)

    return {"schedule_id": sched_id, "prompt": prompt, "cron": cron, "recurring": recurring, "message": f"定时任务已创建（ID: {sched_id}）。"}


async def _task_track(args: dict) -> dict:
    action = args.get("action", "list")
    task_id = args.get("task_id", "")
    content = args.get("content", "")
    active_form = args.get("active_form", "")
    status = args.get("status", "")

    valid_actions = {"create", "update", "list", "delete", "reset"}
    if action not in valid_actions:
        return {"error": f"未知操作: {action}，支持: {', '.join(sorted(valid_actions))}"}

    valid_statuses = {"pending", "in_progress", "completed"}
    if status and status not in valid_statuses:
        return {"error": f"无效状态: {status}，支持: {', '.join(sorted(valid_statuses))}"}

    tasks = _read_tasks()

    if action == "create":
        if not content:
            return {"error": "创建任务需要 content 参数"}
        tid = task_id or f"task_{int(time.time() * 1000)}"
        tasks[tid] = {
            "content": content, "active_form": active_form or content, "status": "pending",
            "created_at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
        }
        _write_tasks(tasks)
        return {"task_id": tid, "status": "created", "task": tasks[tid]}

    elif action == "update":
        if not task_id:
            return {"error": "更新任务需要 task_id 参数"}
        if task_id not in tasks:
            return {"error": f"任务不存在: {task_id}"}
        if content:
            tasks[task_id]["content"] = content
        if status:
            tasks[task_id]["status"] = status
        if active_form:
            tasks[task_id]["active_form"] = active_form
        tasks[task_id]["updated_at"] = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        _write_tasks(tasks)
        return {"task_id": task_id, "status": "updated", "task": tasks[task_id]}

    elif action == "list":
        task_list = [{"id": tid, **t} for tid, t in tasks.items()]
        task_list.sort(key=lambda t: t.get("created_at", ""))
        return {"tasks": task_list, "total": len(task_list)}

    elif action == "delete":
        if not task_id:
            return {"error": "删除任务需要 task_id 参数"}
        if task_id not in tasks:
            return {"error": f"任务不存在: {task_id}"}
        del tasks[task_id]
        _write_tasks(tasks)
        return {"task_id": task_id, "status": "deleted"}

    elif action == "reset":
        tasks_data = args.get("tasks", [])
        new_tasks = {}
        for i, t in enumerate(tasks_data):
            tid = t.get("id", f"task_{int(time.time() * 1000)}_{i}")
            new_tasks[tid] = {
                "content": t.get("content", ""),
                "active_form": t.get("active_form", t.get("content", "")),
                "status": t.get("status", "pending"),
                "created_at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
            }
        _write_tasks(new_tasks)
        return {"task_ids": list(new_tasks.keys()), "total": len(new_tasks)}

    return {"error": f"未知操作: {action}"}
