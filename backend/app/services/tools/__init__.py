"""Tool implementations package — exports execute_tool dispatcher."""

import json
from app.services.tools.file_tools import _file_read, _file_write, _file_search, _edit_file, _read_lines, _file_delete, _file_rename
from app.services.tools.web_tools import _web_search, _web_fetch, _api_request
from app.services.tools.dev_tools import _shell_command, _code_review, _git_operation, _npm_install, _pip_install, _run_tests, _run_migration
from app.services.tools.utility_tools import _translator, _json_formatter, _regex_tester, _ocr_image, _search_memory, _db_query, _env_manage
from app.services.tools.process_tools import _start_process, _stop_process, _read_process_log
from app.services.tools.interaction_tools import _ask_user, _enter_plan, _spawn_subagent, _schedule_task, _task_track, _clear_pending_question, PENDING_QUESTION_FILE
from app.services.tools.watch_tools import _watch_files


async def execute_tool(tool_name: str, arguments: dict, context: dict | None = None) -> str:
    tool_map = {
        "web_search": _web_search,
        "web_fetch": _web_fetch,
        "file_read": _file_read,
        "file_write": _file_write,
        "file_search": _file_search,
        "shell_command": _shell_command,
        "code_review": _code_review,
        "translator": _translator,
        "json_formatter": _json_formatter,
        "regex_tester": _regex_tester,
        "ocr_image": _ocr_image,
        "search_memory": _search_memory,
        "git_operation": _git_operation,
        "edit_file": _edit_file,
        "read_lines": _read_lines,
        "file_delete": _file_delete,
        "file_rename": _file_rename,
        "db_query": _db_query,
        "start_process": _start_process,
        "stop_process": _stop_process,
        "read_process_log": _read_process_log,
        "npm_install": _npm_install,
        "pip_install": _pip_install,
        "run_tests": _run_tests,
        "run_migration": _run_migration,
        "api_request": _api_request,
        "watch_files": _watch_files,
        "env_manage": _env_manage,
        "task_track": _task_track,
        "ask_user": _ask_user,
        "enter_plan": _enter_plan,
        "spawn_subagent": _spawn_subagent,
        "schedule_task": _schedule_task,
    }

    handler = tool_map.get(tool_name)
    if not handler:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})

    try:
        if tool_name in ("ocr_image", "search_memory", "file_read"):
            result = await handler(arguments, context or {})
        else:
            result = await handler(arguments)
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)})


__all__ = [
    "execute_tool", "PENDING_QUESTION_FILE", "_clear_pending_question",
]
