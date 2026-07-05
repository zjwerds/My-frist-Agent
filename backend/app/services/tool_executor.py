"""Built-in tool implementations for the agent — all real, no mocks."""

import json
import os
import sys
import re
import time
import shlex
import glob as glob_module
import subprocess
import urllib.request
import urllib.error
import tempfile
from datetime import datetime
from pathlib import Path

from app.services.ocr_service import ocr_image_from_base64
from app.services.file_parser_service import parse_file
from app.utils import get_data_dir

# Workspace scope: restrict file operations to the project directory
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent  # backend/
ALLOWED_WRITE_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx",
    ".html", ".css", ".json", ".md", ".txt",
    ".yaml", ".yml", ".toml", ".ini", ".cfg",
    ".sh", ".bat", ".ps1", ".sql", ".xml",
    ".env", ".gitignore",
}


def _in_workspace(path: Path) -> bool:
    """Check if a resolved path is within the workspace scope."""
    try:
        resolved = path.resolve()
        workspace = WORKSPACE_ROOT.resolve()
        agent_root = workspace.parent  # agent-platform/
        if workspace in resolved.parents or resolved == workspace:
            return True
        if agent_root in resolved.parents or resolved == agent_root:
            return True
        return False
    except Exception:
        return False


# ── Safe command execution (prevents shell injection) ─────────────────

_SHELL_METACHARS = re.compile(r'[|;&`$(){}<>]')

def _safe_command_split(command: str) -> list[str] | None:
    """Split a command string into args list safely.

    Returns a list suitable for subprocess.run(..., shell=False),
    or None if the command contains shell metacharacters (pipes,
    redirects, sub-shells, etc.) and cannot be safely split.
    """
    # Reject commands with shell metacharacters
    if _SHELL_METACHARS.search(command):
        return None
    try:
        return shlex.split(command, posix=False)
    except ValueError:
        return None


# ── Dispatcher ──────────────────────────────────────────────────────────

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
        # P0 tools
        "git_operation": _git_operation,
        "edit_file": _edit_file,
        "read_lines": _read_lines,
        "db_query": _db_query,
        # P1 tools
        "start_process": _start_process,
        "stop_process": _stop_process,
        "read_process_log": _read_process_log,
        "npm_install": _npm_install,
        "pip_install": _pip_install,
        "run_tests": _run_tests,
        # P2 tools
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


# ── Web Search ──────────────────────────────────────────────────────────

async def _web_search(args: dict) -> dict:
    """Search the internet using DuckDuckGo (free, no API key required)."""
    query = args.get("query", "")
    max_results = min(int(args.get("max_results", 5)), 20)

    if not query:
        return {"error": "缺少搜索关键词"}

    try:
        from duckduckgo_search import DDGS
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", ""),
                })
        return {"query": query, "results": results, "total": len(results)}
    except ImportError:
        return {"error": "DuckDuckGo 搜索不可用（未安装 duckduckgo-search 包）"}
    except Exception as e:
        return {"query": query, "error": str(e), "results": []}


# ── Web Fetch ───────────────────────────────────────────────────────────

async def _web_fetch(args: dict) -> dict:
    """Fetch and read the content of a URL."""
    url = args.get("url", "")
    max_length = int(args.get("max_length", 5000))

    if not url:
        return {"error": "缺少 URL"}

    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            content = resp.read().decode("utf-8", errors="replace")

        # Strip HTML tags for readability
        text = re.sub(r"<[^>]+>", " ", content)
        text = re.sub(r"\s+", " ", text).strip()

        truncated = len(text) > max_length
        return {
            "url": url,
            "status": resp.status,
            "content": text[:max_length] + ("..." if truncated else ""),
            "truncated": truncated,
        }
    except urllib.error.HTTPError as e:
        return {"url": url, "error": f"HTTP {e.code}: {e.reason}"}
    except urllib.error.URLError as e:
        return {"url": url, "error": f"无法访问: {e.reason}"}
    except Exception as e:
        return {"url": url, "error": str(e)}


# ── File Read ───────────────────────────────────────────────────────────

async def _file_read(args: dict, context: dict | None = None) -> dict:
    """Read the contents of a file from the filesystem.
    Priority: absolute path → project directory → workspace root.
    """
    filepath = args.get("path", "")
    if not filepath:
        return {"error": "缺少文件路径"}

    project_path = (context or {}).get("project_path", "")

    try:
        # Try resolving the path with priority: absolute → project_dir → workspace
        candidates = []
        path = Path(filepath)
        if path.is_absolute():
            candidates = [path]
        else:
            if project_path:
                candidates.append(Path(project_path) / filepath)
            candidates.append(WORKSPACE_ROOT / filepath)

        resolved_path = None
        for candidate in candidates:
            try:
                candidate = candidate.resolve()
                if candidate.exists() and candidate.is_file() and _in_workspace(candidate):
                    resolved_path = candidate
                    break
            except (PermissionError, OSError):
                continue

        if resolved_path is None:
            # Try the original path as-is (may error with helpful message)
            p = Path(filepath).resolve()
            if not _in_workspace(p):
                hint = f" (项目目录: {project_path})" if project_path else ""
                return {"error": f"文件不存在或无权访问: {filepath}{hint}"}
            return {"error": f"文件不存在: {filepath}"}

        ext = resolved_path.suffix.lower()

        # ── Binary document formats: parse with document parser ──
        if ext in (".pdf", ".docx", ".doc", ".xlsx", ".xls"):
            file_bytes = resolved_path.read_bytes()
            result = parse_file(file_bytes, resolved_path.name)
            if "error" in result:
                return {"error": result["error"]}
            content = result.get("text", "")
            metadata = {k: v for k, v in result.items() if k not in ("text", "filename")}
            lines = content.split("\n")
            return {
                "path": str(resolved_path),
                "size": len(content),
                "lines": len(lines),
                "content": content,
                **metadata,
            }

        # ── Text files: read as UTF-8 ──
        content = resolved_path.read_text("utf-8", errors="replace")
        lines = content.split("\n")
        return {
            "path": str(resolved_path),
            "size": len(content),
            "lines": len(lines),
            "content": content,
        }
    except PermissionError:
        return {"error": f"无权限读取: {filepath}"}
    except Exception as e:
        return {"error": str(e)}


# ── File Write ──────────────────────────────────────────────────────────

async def _file_write(args: dict) -> dict:
    """Create or overwrite a file on the filesystem."""
    filepath = args.get("path", "")
    content = args.get("content", "")

    if not filepath:
        return {"error": "缺少文件路径"}

    ext = Path(filepath).suffix.lower()
    if ext and ext not in ALLOWED_WRITE_EXTENSIONS:
        return {"error": f"不支持写入该文件类型: {ext}，允许: {', '.join(sorted(ALLOWED_WRITE_EXTENSIONS))}"}

    try:
        path = Path(filepath)
        if not _in_workspace(path):
            return {"error": f"无权写入该路径（超出工作区范围）: {filepath}"}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, "utf-8")
        return {
            "path": str(path.resolve()),
            "size": len(content),
            "status": "written",
        }
    except PermissionError:
        return {"error": f"无权限写入: {filepath}"}
    except Exception as e:
        return {"error": str(e)}


# ── File Search ─────────────────────────────────────────────────────────

async def _file_search(args: dict) -> dict:
    """Search the filesystem for files matching a pattern or containing text."""
    pattern = args.get("pattern", "")
    search_text = args.get("search_text", "")
    root_dir = args.get("root_dir", ".")
    max_results = min(int(args.get("max_results", 20)), 100)
    exclude_dirs = {"node_modules", ".git", "__pycache__", ".venv", "dist", "build", ".skills", ".tools"}

    # Validate root_dir is within workspace
    root_path = Path(root_dir).resolve()
    if root_dir != "." and not _in_workspace(root_path):
        return {"error": f"无权搜索该目录（超出工作区范围）: {root_dir}"}

    results = []

    if pattern and not search_text:
        # Glob mode: find files by name pattern
        for p in glob_module.glob(pattern, root_dir=root_dir, recursive=True):
            full = os.path.join(root_dir, p) if root_dir != "." else p
            if not any(excluded in full.split(os.sep) for excluded in exclude_dirs):
                results.append({"path": full})
                if len(results) >= max_results:
                    break
        return {"pattern": pattern, "matches": results, "total": len(results)}

    elif search_text:
        # Grep mode: find files containing text
        root = root_path
        count = 0
        for p in root.rglob("*"):
            if p.is_dir() or p.name.startswith("."):
                continue
            rel = str(p.relative_to(root))
            if any(excluded in rel.split(os.sep) for excluded in exclude_dirs):
                continue
            try:
                for i, line in enumerate(p.read_text("utf-8", errors="replace").split("\n"), 1):
                    if search_text in line:
                        results.append({"path": rel, "line": i, "content": line.strip()[:200]})
                        count += 1
                        if count >= max_results:
                            break
            except (PermissionError, UnicodeDecodeError, OSError):
                continue
            if count >= max_results:
                break
        return {"search_text": search_text, "matches": results, "total": len(results)}

    return {"error": "请提供 pattern（文件名匹配）或 search_text（内容搜索）"}


# ── Shell Command ───────────────────────────────────────────────────────

async def _shell_command(args: dict) -> dict:
    """Execute a shell command and return its output."""
    command = args.get("command", "")
    work_dir = args.get("work_dir", None)
    timeout = int(args.get("timeout", 30))

    if not command:
        return {"error": "缺少命令"}

    # Restrict working directory to workspace
    if work_dir:
        wd_path = Path(work_dir).resolve()
        if not _in_workspace(wd_path):
            return {"error": f"无权在该目录执行命令（超出工作区范围）: {work_dir}"}
    else:
        work_dir = str(WORKSPACE_ROOT)

    # Deny list for dangerous commands (word-boundary matching to prevent bypass)
    dangerous_patterns = [
        r"\brm\s+-rf\b", r"\bdel\s+/", r"\brd\s+/", r"\bshutdown\b",
        r"\btaskkill\b", r"\bformat\s+[a-z]:", r"\bdd\s+if=",
        r">\s*/dev/sda", r">\s*/dev/sdb",
    ]
    cmd_lower = command.lower()
    for d in dangerous_patterns:
        if re.search(d, cmd_lower):
            return {"error": f"命令包含危险操作，已阻止: {command}"}

    cmd_list = _safe_command_split(command)
    if cmd_list is None:
        return {"error": f"命令包含不安全的 shell 元字符，已阻止: {command}"}

    try:
        result = subprocess.run(
            cmd_list,
            shell=False,
            cwd=work_dir,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = result.stdout or ""
        error = result.stderr or ""
        # Truncate if too long
        max_output = 10000
        return {
            "command": command,
            "exit_code": result.returncode,
            "stdout": output[:max_output] + ("\n...(truncated)" if len(output) > max_output else ""),
            "stderr": error[:max_output] + ("\n...(truncated)" if len(error) > max_output else ""),
        }
    except subprocess.TimeoutExpired:
        return {"command": command, "error": f"命令执行超时（{timeout}秒）"}
    except FileNotFoundError:
        return {"command": command, "error": "命令未找到"}
    except Exception as e:
        return {"command": command, "error": str(e)}


# ── Code Review (flake8) ────────────────────────────────────────────────

async def _code_review(args: dict) -> dict:
    """Run flake8 linting on a Python file or on code string."""
    filepath = args.get("path", "")
    code = args.get("code", "")

    issues = []

    if filepath:
        # Lint an existing file
        path = Path(filepath)
        if not path.exists():
            return {"error": f"文件不存在: {filepath}"}
        try:
            result = subprocess.run(
                ["flake8", str(path)],
                capture_output=True, text=True, timeout=30,
            )
            for line in result.stdout.strip().split("\n"):
                if line:
                    parts = line.split(":", 3)
                    if len(parts) >= 4:
                        issues.append({
                            "line": int(parts[1]),
                            "col": int(parts[2]),
                            "message": parts[3].strip(),
                        })
                    else:
                        issues.append({"message": line})
            return {
                "file": filepath,
                "issues": issues,
                "total": len(issues),
            }
        except subprocess.TimeoutExpired:
            return {"error": "代码审查超时"}
        except FileNotFoundError:
            return {"error": "flake8 未安装"}

    elif code:
        # Lint code string: write to temp file, run flake8
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
                f.write(code)
                tmp_path = f.name
            result = subprocess.run(
                ["flake8", tmp_path],
                capture_output=True, text=True, timeout=30,
            )
            for line in result.stdout.strip().split("\n"):
                if line:
                    parts = line.split(":", 3)
                    if len(parts) >= 4:
                        issues.append({
                            "line": int(parts[1]),
                            "col": int(parts[2]),
                            "message": parts[3].strip(),
                        })
                    else:
                        issues.append({"message": line})
            return {"issues": issues, "total": len(issues)}
        except subprocess.TimeoutExpired:
            return {"error": "代码审查超时"}
        except FileNotFoundError:
            return {"error": "flake8 未安装"}
        except Exception as e:
            return {"error": str(e)}
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

    return {"error": "请提供 path（文件路径）或 code（代码内容）"}


# ── Translator ──────────────────────────────────────────────────────────

async def _translator(args: dict) -> dict:
    """Translate text between languages using Google Translate (free)."""
    text = args.get("text", "")
    source = args.get("source", "auto")
    target = args.get("target", "zh-CN")

    if not text:
        return {"error": "缺少待翻译文本"}

    try:
        from deep_translator import GoogleTranslator
        translated = GoogleTranslator(source=source, target=target).translate(text)
        return {
            "source_text": text,
            "translated_text": translated,
            "source_lang": source,
            "target_lang": target,
        }
    except ImportError:
        return {"error": "翻译不可用（未安装 deep-translator 包）"}
    except Exception as e:
        return {"error": f"翻译失败: {e}"}


# ── JSON Formatter ──────────────────────────────────────────────────────

async def _json_formatter(args: dict) -> dict:
    """Format, validate, or minify a JSON string."""
    json_str = args.get("json_string", "")
    action = args.get("action", "format")

    if not json_str:
        return {"error": "缺少 JSON 字符串"}

    try:
        parsed = json.loads(json_str)
        if action == "format":
            result = json.dumps(parsed, indent=2, ensure_ascii=False)
        elif action == "minify":
            result = json.dumps(parsed, separators=(",", ":"), ensure_ascii=False)
        elif action == "validate":
            result = "JSON 格式有效"
        else:
            return {"error": f"未知操作: {action}，支持 format/minify/validate"}
        return {"action": action, "result": result, "valid": True}
    except json.JSONDecodeError as e:
        return {"action": action, "error": str(e), "valid": False, "position": e.pos}


# ── Regex Tester ────────────────────────────────────────────────────────

async def _regex_tester(args: dict) -> dict:
    """Test a regular expression against text."""
    pattern = args.get("pattern", "")
    text = args.get("text", "")

    if not pattern:
        return {"error": "缺少正则表达式"}

    try:
        flags = 0
        if args.get("ignore_case"):
            flags |= re.IGNORECASE
        if args.get("multiline"):
            flags |= re.MULTILINE
        if args.get("dotall"):
            flags |= re.DOTALL

        matches = list(re.finditer(pattern, text, flags))
        details = []
        for m in matches:
            details.append({
                "start": m.start(),
                "end": m.end(),
                "match": m.group(),
                "groups": list(m.groups()) if m.groups() else None,
            })
        return {
            "pattern": pattern,
            "match_count": len(details),
            "matches": details[:50],
            "error": None,
        }
    except re.error as e:
        return {"pattern": pattern, "error": str(e), "match_count": 0, "matches": []}


# ── OCR Image (keep existing real implementation) ───────────────────────

async def _ocr_image(args: dict, context: dict | None = None) -> dict:
    """OCR tool: extract text from an image using pytesseract."""
    image_index = args.get("image_index", 0)
    all_images = (context or {}).get("all_images", [])
    if not all_images:
        return {"error": "当前对话中没有找到图片", "text": ""}
    if image_index < 0 or image_index >= len(all_images):
        return {
            "error": f"图片索引 {image_index} 无效，有效范围: 0-{len(all_images) - 1}",
            "text": "",
        }
    data_uri = all_images[image_index]
    text = ocr_image_from_base64(data_uri)
    return {"image_index": image_index, "text": text}


# ── Memory Search ─────────────────────────────────────────────────────

async def _search_memory(args: dict, context: dict | None = None) -> dict:
    """Search conversation memory by keyword."""
    query = args.get("query", "")
    if not query:
        return {"error": "缺少搜索关键词"}

    conversation_id = (context or {}).get("conversation_id", "")
    if not conversation_id:
        return {"error": "无法获取当前对话 ID"}

    from app.services.conversation_memory import search_memory
    results = search_memory(conversation_id, query)

    if not results:
        return {"query": query, "results": [], "message": "未找到相关历史记录"}

    return {
        "query": query,
        "results": [
            {
                "timestamp": r.get("timestamp", ""),
                "summary": r.get("summary", ""),
                "constraints": r.get("constraints", []),
                "decisions": r.get("decisions", []),
                "artifacts": r.get("artifacts", []),
                "user_intent": r.get("user_intent", ""),
            }
            for r in results
        ],
        "total": len(results),
    }


# ═══════════════════════════════════════════════════════════════════
# P0 — Git Operation
# ═══════════════════════════════════════════════════════════════════

async def _git_operation(args: dict) -> dict:
    """Run git commands within the workspace scope."""
    action = args.get("action", "")
    repo_path = args.get("repo_path", str(WORKSPACE_ROOT))

    if not action:
        return {"error": "缺少 action 参数，支持: status/diff/log/add/commit/push/pull/branch/checkout/merge"}

    # Resolve and validate repo path
    repo = Path(repo_path)
    if not _in_workspace(repo):
        return {"error": f"无权操作该路径（超出工作区范围）: {repo_path}"}
    if not (repo / ".git").exists():
        return {"error": f"该目录不是 git 仓库（无 .git 目录）: {repo_path}"}

    cmd = ["git"]
    try:
        if action == "status":
            cmd.extend(["status", "--short"])
        elif action == "diff":
            cmd.append("diff")
            if args.get("staged"):
                cmd.append("--cached")
        elif action == "log":
            count = min(int(args.get("count", 10)), 50)
            cmd.extend(["log", f"--oneline", f"-{count}", "--decorate"])
        elif action == "add":
            files = args.get("files", ".")
            cmd.extend(["add", "--", files])
        elif action == "commit":
            msg = args.get("message", "")
            if not msg:
                return {"error": "commit 需要 message 参数"}
            cmd.extend(["commit", "-m", msg])
        elif action == "push":
            remote = args.get("remote", "origin")
            branch = args.get("branch", "")
            cmd.extend(["push", remote])
            if branch:
                cmd.append(branch)
        elif action == "pull":
            remote = args.get("remote", "origin")
            branch = args.get("branch", "")
            cmd.extend(["pull", remote])
            if branch:
                cmd.append(branch)
        elif action == "branch":
            cmd.append("branch")
            if args.get("list"):
                cmd.append("-a")
            elif args.get("new_branch"):
                cmd.extend(["-c", args["new_branch"]])
        elif action == "checkout":
            target = args.get("target", "")
            if not target:
                return {"error": "checkout 需要 target 参数（分支名或提交 hash）"}
            new_branch = args.get("new_branch", "")
            if new_branch:
                cmd.extend(["checkout", "-b", new_branch])
            else:
                cmd.extend(["checkout", target])
        elif action == "merge":
            source = args.get("source", "")
            if not source:
                return {"error": "merge 需要 source 参数（源分支名）"}
            cmd.extend(["merge", source])
        else:
            return {"error": f"不支持的操作: {action}，支持: status/diff/log/add/commit/push/pull/branch/checkout/merge"}

        result = subprocess.run(
            cmd,
            cwd=str(repo),
            capture_output=True,
            text=True,
            timeout=30,
        )
        return {
            "action": action,
            "exit_code": result.returncode,
            "stdout": result.stdout[:5000] + ("...(truncated)" if len(result.stdout) > 5000 else ""),
            "stderr": result.stderr[:2000] + ("...(truncated)" if len(result.stderr) > 2000 else ""),
        }
    except subprocess.TimeoutExpired:
        return {"action": action, "error": "git 操作超时（30秒）"}
    except FileNotFoundError:
        return {"action": action, "error": "git 未安装或不在 PATH 中"}
    except Exception as e:
        return {"action": action, "error": str(e)}


# ═══════════════════════════════════════════════════════════════════
# P0 — Edit File (search/replace, like Claude Code's Edit tool)
# ═══════════════════════════════════════════════════════════════════

async def _edit_file(args: dict) -> dict:
    """Apply a search-and-replace edit to an existing file."""
    filepath = args.get("path", "")
    old_string = args.get("old_string", "")
    new_string = args.get("new_string", "")
    replace_all = args.get("replace_all", False)

    if not filepath or not old_string:
        return {"error": "请提供 path（文件路径）和 old_string（要替换的文本）"}

    path = Path(filepath)
    if not path.exists():
        return {"error": f"文件不存在: {filepath}"}
    if not path.is_file():
        return {"error": f"路径不是文件: {filepath}"}
    if not _in_workspace(path):
        return {"error": f"无权编辑该文件（超出工作区范围）: {filepath}"}

    try:
        content = path.read_text("utf-8", errors="replace")

        if replace_all:
            if old_string not in content:
                return {"error": f"未在文件中找到匹配文本（replace_all）: {old_string[:100]}"}
            new_content = content.replace(old_string, new_string)
            count = content.count(old_string)
        else:
            # Only replace first occurrence
            idx = content.find(old_string)
            if idx == -1:
                return {"error": f"未在文件中找到匹配文本: {old_string[:100]}"}
            new_content = content[:idx] + new_string + content[idx + len(old_string):]
            count = 1

        path.write_text(new_content, "utf-8")

        return {
            "path": str(path.resolve()),
            "replaced": count,
            "size_before": len(content),
            "size_after": len(new_content),
            "status": "edited",
        }
    except PermissionError:
        return {"error": f"无权限编辑: {filepath}"}
    except Exception as e:
        return {"error": str(e)}


# ═══════════════════════════════════════════════════════════════════
# P0 — Read Lines (read a specific line range from a file)
# ═══════════════════════════════════════════════════════════════════

async def _read_lines(args: dict) -> dict:
    """Read a specific line range from a file."""
    filepath = args.get("path", "")
    start = int(args.get("start", 1))
    end = int(args.get("end", 0))

    if not filepath:
        return {"error": "请提供 path（文件路径）"}

    path = Path(filepath)
    if not path.exists():
        return {"error": f"文件不存在: {filepath}"}
    if not path.is_file():
        return {"error": f"路径不是文件: {filepath}"}
    if not _in_workspace(path):
        return {"error": f"无权读取该文件（超出工作区范围）: {filepath}"}

    try:
        lines = path.read_text("utf-8", errors="replace").split("\n")
        total = len(lines)

        if start < 1:
            start = 1
        if end <= 0 or end > total:
            end = total
        if start > end:
            return {"error": f"起始行（{start}）不能大于结束行（{end}），文件共 {total} 行"}

        selected = lines[start - 1:end]
        return {
            "path": str(path.resolve()),
            "total_lines": total,
            "start_line": start,
            "end_line": end,
            "lines": len(selected),
            "content": "\n".join(selected),
        }
    except PermissionError:
        return {"error": f"无权限读取: {filepath}"}
    except Exception as e:
        return {"error": str(e)}


# ═══════════════════════════════════════════════════════════════════
# P0 — Database Query (read-only SQLite access)
# ═══════════════════════════════════════════════════════════════════

async def _db_query(args: dict) -> dict:
    """Execute a read-only SQL query on the agent's SQLite database."""
    sql = args.get("sql", "").strip()
    if not sql:
        return {"error": "请提供 sql 参数（SELECT 查询语句）"}

    sql_upper = sql.upper().strip()
    # Must start with SELECT (ignore leading whitespace/comments)
    if not sql_upper.startswith("SELECT"):
        return {"error": "仅支持 SELECT 查询，不支持写操作"}
    # Reject multi-statement queries (semicolons not at end of SELECT)
    stripped_no_strings = re.sub(r"'[^']*'", "", sql)  # remove string literals
    semi_pos = stripped_no_strings.find(";")
    if semi_pos >= 0 and semi_pos < len(stripped_no_strings.rstrip()):
        return {"error": "不支持多语句查询（仅允许单个 SELECT 语句）"}

    # Use a read-only SQLite connection to prevent any write access
    from app.database import DB_DIR
    import sqlite3
    db_path = os.path.join(DB_DIR, "agent.db")
    conn = None
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.execute("PRAGMA query_only = ON")
        cursor = conn.execute(sql)
        columns = [desc[0] for desc in cursor.description]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]

        max_rows = 100
        return {
            "sql": sql,
            "row_count": len(rows),
            "rows": rows[:max_rows],
            "truncated": len(rows) > max_rows,
        }
    except sqlite3.DatabaseError as e:
        return {"sql": sql, "error": str(e), "row_count": 0, "rows": []}
    except Exception as e:
        return {"sql": sql, "error": str(e), "row_count": 0, "rows": []}
    finally:
        if conn:
            conn.close()


# ═══════════════════════════════════════════════════════════════════
# P1 — Background Process Management
# ═══════════════════════════════════════════════════════════════════

import threading
import time as time_module

_processes: dict[str, dict] = {}
_process_counter = 0
_process_lock = threading.Lock()


async def _start_process(args: dict) -> dict:
    """Start a long-running background process."""
    global _process_counter
    command = args.get("command", "")
    work_dir = args.get("work_dir", str(WORKSPACE_ROOT))
    process_id = args.get("process_id", "")

    if not command:
        return {"error": "请提供 command（要执行的命令）"}

    # Same dangerous command blacklist as _shell_command
    dangerous_patterns = [
        r"\brm\s+-rf\b", r"\bdel\s+/", r"\brd\s+/", r"\bshutdown\b",
        r"\btaskkill\b", r"\bformat\s+[a-z]:", r"\bdd\s+if=",
        r">\s*/dev/sda", r">\s*/dev/sdb",
    ]
    cmd_lower = command.lower()
    for d in dangerous_patterns:
        if re.search(d, cmd_lower):
            return {"error": f"命令包含危险操作，已阻止: {command}"}

    wd = Path(work_dir).resolve()
    if not _in_workspace(wd):
        return {"error": f"无权在该目录启动进程（超出工作区范围）: {work_dir}"}

    cmd_list = _safe_command_split(command)
    if cmd_list is None:
        return {"error": f"命令包含不安全的 shell 元字符，已阻止: {command}"}

    try:
        proc = subprocess.Popen(
            cmd_list,
            shell=False,
            cwd=str(wd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        if not process_id:
            with _process_lock:
                _process_counter += 1
                process_id = f"proc_{_process_counter}"

        with _process_lock:
            _processes[process_id] = {
                "process": proc,
                "command": command,
                "work_dir": str(wd),
                "started_at": time_module.strftime("%H:%M:%S"),
                "stdout_buf": [],
                "stderr_buf": [],
                "running": True,
            }

        # Start reader threads
        def _reader(stream, buf, pid):
            for line in iter(stream.readline, ""):
                with _process_lock:
                    if pid in _processes:
                        _processes[pid]["stdout_buf"].append(line.rstrip("\n"))
            stream.close()

        def _stderr_reader(stream, buf, pid):
            for line in iter(stream.readline, ""):
                with _process_lock:
                    if pid in _processes:
                        _processes[pid]["stderr_buf"].append(line.rstrip("\n"))
            stream.close()

        threading.Thread(target=_reader, args=(proc.stdout, _processes[process_id]["stdout_buf"], process_id), daemon=True).start()
        threading.Thread(target=_stderr_reader, args=(proc.stderr, _processes[process_id]["stderr_buf"], process_id), daemon=True).start()

        return {
            "process_id": process_id,
            "command": command,
            "work_dir": str(wd),
            "status": "started",
            "pid": proc.pid,
        }
    except FileNotFoundError:
        return {"error": "命令未找到"}
    except Exception as e:
        return {"error": str(e)}


async def _stop_process(args: dict) -> dict:
    """Stop a background process."""
    process_id = args.get("process_id", "")
    force = args.get("force", False)

    if not process_id:
        return {"error": "请提供 process_id"}

    with _process_lock:
        entry = _processes.get(process_id)
        if not entry:
            return {"error": f"进程不存在: {process_id}"}
        proc = entry["process"]

    try:
        if force:
            proc.kill()
        else:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=3)

        with _process_lock:
            if process_id in _processes:
                _processes[process_id]["running"] = False
                _processes[process_id]["exit_code"] = proc.returncode

        return {
            "process_id": process_id,
            "command": entry["command"],
            "exit_code": proc.returncode,
            "status": "stopped",
        }
    except Exception as e:
        return {"error": str(e)}


async def _read_process_log(args: dict) -> dict:
    """Read the stdout/stderr log of a background process."""
    process_id = args.get("process_id", "")
    stream = args.get("stream", "stdout")
    lines_count = int(args.get("lines", 50))

    if not process_id:
        return {"error": "请提供 process_id"}

    with _process_lock:
        entry = _processes.get(process_id)
        if not entry:
            return {"error": f"进程不存在: {process_id}"}

        buf = entry.get(f"{stream}_buf", [])
        selected = buf[-lines_count:]
        is_running = entry["running"]
        exit_code = entry.get("exit_code")

    # Check if the process is still alive
    proc = entry["process"]
    if is_running:
        rc = proc.poll()
        if rc is not None:
            with _process_lock:
                if process_id in _processes:
                    _processes[process_id]["running"] = False
                    _processes[process_id]["exit_code"] = rc
            is_running = False
            exit_code = rc

    return {
        "process_id": process_id,
        "command": entry["command"],
        "stream": stream,
        "lines": len(selected),
        "content": "\n".join(selected),
        "running": is_running,
        "exit_code": exit_code,
    }


# ═══════════════════════════════════════════════════════════════════
# P1 — Package Manager: npm install
# ═══════════════════════════════════════════════════════════════════

async def _npm_install(args: dict) -> dict:
    """Install npm packages."""
    packages = args.get("packages", "")
    work_dir = args.get("work_dir", str(WORKSPACE_ROOT))
    save_dev = args.get("save_dev", False)

    wd = Path(work_dir).resolve()
    if not _in_workspace(wd):
        return {"error": f"无权在该目录操作（超出工作区范围）: {work_dir}"}

    if not (wd / "package.json").exists():
        return {"error": f"该目录没有 package.json: {work_dir}"}

    cmd = ["npm", "install"]
    if packages:
        cmd.extend(packages.split())
    if save_dev:
        cmd.append("--save-dev")

    try:
        result = subprocess.run(
            cmd,
            cwd=str(wd),
            capture_output=True,
            text=True,
            timeout=120,
        )
        output = result.stdout or ""
        error = result.stderr or ""
        return {
            "command": " ".join(cmd),
            "exit_code": result.returncode,
            "stdout": output[:3000] + ("...(truncated)" if len(output) > 3000 else ""),
            "stderr": error[:2000] + ("...(truncated)" if len(error) > 2000 else ""),
        }
    except subprocess.TimeoutExpired:
        return {"error": "npm install 超时（120秒）"}
    except FileNotFoundError:
        return {"error": "npm 未安装或不在 PATH 中"}
    except Exception as e:
        return {"error": str(e)}


# ═══════════════════════════════════════════════════════════════════
# P1 — Package Manager: pip install
# ═══════════════════════════════════════════════════════════════════

async def _pip_install(args: dict) -> dict:
    """Install Python packages via pip."""
    packages = args.get("packages", "")
    requirements = args.get("requirements", "")

    if not packages and not requirements:
        return {"error": "请提供 packages（包名）或 requirements（requirements.txt 路径）"}

    cmd = [sys.executable or "python", "-m", "pip", "install"]
    if requirements:
        req_path = Path(requirements)
        if not req_path.exists():
            return {"error": f"requirements 文件不存在: {requirements}"}
        cmd.extend(["-r", str(req_path)])
    else:
        cmd.extend(packages.split())

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=180,
        )
        output = result.stdout or ""
        error = result.stderr or ""
        return {
            "command": " ".join(cmd),
            "exit_code": result.returncode,
            "stdout": output[:3000] + ("...(truncated)" if len(output) > 3000 else ""),
            "stderr": error[:2000] + ("...(truncated)" if len(error) > 2000 else ""),
        }
    except subprocess.TimeoutExpired:
        return {"error": "pip install 超时（180秒）"}
    except FileNotFoundError:
        return {"error": "pip 未安装或不在 PATH 中"}
    except Exception as e:
        return {"error": str(e)}


# ═══════════════════════════════════════════════════════════════════
# P1 — Test Runner
# ═══════════════════════════════════════════════════════════════════

async def _run_tests(args: dict) -> dict:
    """Run tests using pytest, npm test, or a custom command."""
    runner = args.get("runner", "auto")
    work_dir = args.get("work_dir", str(WORKSPACE_ROOT))
    path = args.get("path", "")
    command = args.get("command", "")
    timeout = int(args.get("timeout", 120))

    wd = Path(work_dir).resolve()
    if not _in_workspace(wd):
        return {"error": f"无权在该目录操作（超出工作区范围）: {work_dir}"}

    # Auto-detect or use explicit command
    if command:
        cmd_list = _safe_command_split(command)
        if cmd_list is None:
            return {"error": f"命令包含不安全的 shell 元字符，已阻止: {command}"}
    elif runner == "pytest":
        if path:
            cmd_list = [sys.executable, "-m", "pytest", path, "-v", "--tb=short"]
        else:
            cmd_list = [sys.executable, "-m", "pytest", "-v", "--tb=short"]
    elif runner == "npm":
        cmd_list = ["npm", "test"]
    elif runner == "auto":
        if (wd / "pytest.ini").exists() or (wd / "pyproject.toml").exists() or list(wd.glob("test_*.py")) or list(wd.glob("*_test.py")):
            if path:
                cmd_list = [sys.executable, "-m", "pytest", path, "-v", "--tb=short"]
            else:
                cmd_list = [sys.executable, "-m", "pytest", "-v", "--tb=short"]
        elif (wd / "package.json").exists():
            cmd_list = ["npm", "test"]
        else:
            return {"error": "未检测到测试框架，请显式指定 runner(pytest/npm) 或 command"}
    else:
        return {"error": f"不支持的测试 runner: {runner}，支持: pytest/npm/auto"}

    try:
        result = subprocess.run(
            cmd_list,
            shell=False,
            cwd=str(wd),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = (result.stdout or "") + (result.stderr or "")
        cmd_str = " ".join(cmd_list) if isinstance(cmd_list, list) else cmd_list
        parsed = _parse_test_output(output, runner if runner != "auto" else ("pytest" if "pytest" in str(cmd_list) else "npm"))
        return {
            "runner": runner,
            "command": cmd_str,
            "exit_code": result.returncode,
            "output": output[:5000] + ("...(truncated)" if len(output) > 5000 else ""),
            "parsed": parsed,
        }
    except subprocess.TimeoutExpired:
        return {"error": f"测试超时（{timeout}秒）"}
    except FileNotFoundError:
        return {"error": "测试命令未找到"}
    except Exception as e:
        return {"error": str(e)}


def _parse_test_output(output: str, runner: str) -> dict:
    """Parse test output to extract summary information."""
    result = {"passed": 0, "failed": 0, "errors": 0, "skipped": 0, "total": 0}

    if runner == "pytest":
        # Match pytest summary line: "= 10 passed, 2 failed, 1 skipped in 2.34s ="
        summary = re.search(r"=+\s*(\d+)\s+passed.*?(\d+)\s+failed.*?(\d+)\s+skipped.*?=+", output)
        if summary:
            result["passed"] = int(summary.group(1))
            result["failed"] = int(summary.group(2))
            result["skipped"] = int(summary.group(3))
            result["total"] = result["passed"] + result["failed"] + result["skipped"]
        else:
            # Fallback: count individual test result lines
            result["passed"] = len(re.findall(r"PASSED|\.\.\.", output))
            result["failed"] = len(re.findall(r"FAILED", output))
            result["total"] = result["passed"] + result["failed"]

        # Extract failed test names
        failed_tests = re.findall(r"FAILED\s+(\S+)", output)
        if failed_tests:
            result["failed_tests"] = failed_tests[:10]

    elif runner == "npm":
        # Match npm test output
        result["raw_output"] = output[:1000]

    return result


# ═══════════════════════════════════════════════════════════════════
# P2 — Database Migration (Alembic)
# ═══════════════════════════════════════════════════════════════════

async def _run_migration(args: dict) -> dict:
    """Run Alembic database migrations."""
    command = args.get("command", "upgrade")
    revision = args.get("revision", "head")
    work_dir = args.get("work_dir", str(WORKSPACE_ROOT))
    message = args.get("message", "auto_migration")

    wd = Path(work_dir).resolve()
    if not _in_workspace(wd):
        return {"error": f"无权在该目录操作（超出工作区范围）: {work_dir}"}

    if command == "autogenerate":
        if not message:
            return {"error": "autogenerate 需要 message 参数"}
        cmd = ["alembic", "revision", "--autogenerate", "-m", message]
    elif command == "upgrade":
        cmd = ["alembic", "upgrade", revision]
    elif command == "downgrade":
        cmd = ["alembic", "downgrade", revision]
    elif command == "history":
        cmd = ["alembic", "history"]
    elif command == "current":
        cmd = ["alembic", "current"]
    elif command == "check":
        cmd = ["alembic", "check"]
    elif command == "branches":
        cmd = ["alembic", "branches"]
    else:
        return {"error": f"不支持的命令: {command}，支持: upgrade/downgrade/autogenerate/history/current/check/branches"}

    try:
        result = subprocess.run(
            cmd,
            cwd=str(wd),
            capture_output=True,
            text=True,
            timeout=30,
        )
        output = (result.stdout or "") + (result.stderr or "")
        return {
            "command": command,
            "revision": revision,
            "exit_code": result.returncode,
            "output": output[:3000] + ("...(truncated)" if len(output) > 3000 else ""),
        }
    except FileNotFoundError:
        return {"error": "alembic 未安装或不在 PATH 中（请先 pip install alembic）"}
    except subprocess.TimeoutExpired:
        return {"error": "迁移操作超时（30秒）"}
    except Exception as e:
        return {"error": str(e)}


# ═══════════════════════════════════════════════════════════════════
# P2 — HTTP API Request (test APIs)
# ═══════════════════════════════════════════════════════════════════

async def _api_request(args: dict) -> dict:
    """Send an HTTP request to test an API endpoint."""
    method = args.get("method", "GET").upper()
    url = args.get("url", "")
    headers = args.get("headers", {})
    body = args.get("body", "")
    timeout = int(args.get("timeout", 15))

    if not url:
        return {"error": "请提供 url"}

    valid_methods = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
    if method not in valid_methods:
        return {"error": f"不支持的 HTTP 方法: {method}，支持: {', '.join(valid_methods)}"}

    try:
        req_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }
        if isinstance(headers, dict):
            req_headers.update(headers)
        elif isinstance(headers, str):
            try:
                req_headers.update(json.loads(headers))
            except json.JSONDecodeError:
                pass

        data = None
        if body and method in ("POST", "PUT", "PATCH"):
            data = body.encode("utf-8")
            if "Content-Type" not in {k.lower() for k in req_headers}:
                req_headers["Content-Type"] = "application/json"

        req = urllib.request.Request(url, data=data, headers=req_headers, method=method)

        start = time_module.time()
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            elapsed = round((time_module.time() - start) * 1000)
            raw = resp.read()
            content_type = resp.headers.get("Content-Type", "")

            # Try to parse as JSON, fallback to text
            try:
                body_json = json.loads(raw.decode("utf-8"))
                body_preview = json.dumps(body_json, ensure_ascii=False, indent=2)[:3000]
            except (json.JSONDecodeError, UnicodeDecodeError):
                body_preview = raw.decode("utf-8", errors="replace")[:2000]

        return {
            "url": url,
            "method": method,
            "status": resp.status,
            "status_text": f"{resp.status} {resp.reason}",
            "latency_ms": elapsed,
            "content_type": content_type,
            "headers": dict(resp.headers),
            "body": body_preview,
            "body_length": len(raw),
        }
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:1000]
        return {
            "url": url,
            "method": method,
            "status": e.code,
            "error": f"HTTP {e.code}: {e.reason}",
            "body": body,
        }
    except urllib.error.URLError as e:
        return {"url": url, "method": method, "error": f"无法访问: {e.reason}"}
    except Exception as e:
        return {"url": url, "method": method, "error": str(e)}


# ═══════════════════════════════════════════════════════════════════
# P2 — File Change Monitor (polling-based)
# ═══════════════════════════════════════════════════════════════════

_watch_snapshots: dict[str, dict] = {}

async def _watch_files(args: dict) -> dict:
    """Monitor file changes in a directory by comparing modification times."""
    directory = args.get("directory", str(WORKSPACE_ROOT))
    reset = args.get("reset", False)
    max_results = int(args.get("max_results", 50))

    dir_path = Path(directory).resolve()
    if not _in_workspace(dir_path):
        return {"error": f"无权监视该目录（超出工作区范围）: {directory}"}

    snapshot_key = str(dir_path)

    if reset:
        # Take a new snapshot without reporting changes
        _take_snapshot(snapshot_key, dir_path, max_results)
        return {"directory": str(dir_path), "status": "snapshot_taken", "changes": []}

    # Compare current state with previous snapshot
    previous = _watch_snapshots.get(snapshot_key)
    if previous is None:
        _take_snapshot(snapshot_key, dir_path, max_results)
        return {"directory": str(dir_path), "status": "first_snapshot_taken", "changes": []}

    changes = _detect_changes(snapshot_key, dir_path, max_results)
    _take_snapshot(snapshot_key, dir_path, max_results)

    return {
        "directory": str(dir_path),
        "status": "ok",
        "changes": changes,
        "change_count": len(changes),
    }


def _take_snapshot(key: str, directory: Path, max_results: int) -> None:
    """Record file paths and their modification times."""
    snapshot = {}
    exclude = {"node_modules", ".git", "__pycache__", ".venv", "dist", "build"}
    count = 0
    for p in directory.rglob("*"):
        if p.is_dir():
            continue
        rel = p.relative_to(directory)
        parts = rel.parts
        if any(ex in parts for ex in exclude):
            continue
        try:
            mtime = p.stat().st_mtime
            snapshot[str(rel)] = mtime
            count += 1
            if count >= max_results * 10:
                break
        except OSError:
            continue
    _watch_snapshots[key] = snapshot


def _detect_changes(key: str, directory: Path, max_results: int) -> list[dict]:
    """Compare snapshot with current state and return changes."""
    previous = _watch_snapshots.get(key, {})
    current = {}
    _take_snapshot(key + "_current", directory, max_results * 10)
    current = _watch_snapshots.pop(key + "_current", {})

    changes = []
    exclude = {"node_modules", ".git", "__pycache__", ".venv", "dist", "build"}

    # Check for new and modified files
    for rel_path, mtime in current.items():
        parts = Path(rel_path).parts
        if any(ex in parts for ex in exclude):
            continue
        if rel_path not in previous:
            changes.append({"file": rel_path, "type": "added"})
        elif previous[rel_path] != mtime:
            changes.append({"file": rel_path, "type": "modified"})

    # Check for deleted files
    for rel_path in previous:
        if rel_path not in current:
            parts = Path(rel_path).parts
            if any(ex in parts for ex in exclude):
                continue
            changes.append({"file": rel_path, "type": "deleted"})

    changes.sort(key=lambda c: c["file"])
    return changes[:max_results]


# ═══════════════════════════════════════════════════════════════════
# P2 — Environment Variable Manager (.env)
# ═══════════════════════════════════════════════════════════════════

async def _env_manage(args: dict) -> dict:
    """Read, write, or list environment variables from .env files."""
    action = args.get("action", "list")
    filepath = args.get("filepath", "")
    key = args.get("key", "")
    value = args.get("value", "")

    # Default .env path
    if not filepath:
        candidates = [
            WORKSPACE_ROOT / ".env",
            WORKSPACE_ROOT.parent / ".env",
        ]
        env_path = None
        for c in candidates:
            if c.exists():
                env_path = c
                break
        if env_path is None:
            env_path = candidates[0]
    else:
        env_path = Path(filepath)
        if not _in_workspace(env_path):
            return {"error": f"无权操作该路径（超出工作区范围）: {filepath}"}

    try:
        if action == "list":
            if not env_path.exists():
                return {"env_file": str(env_path), "variables": {}, "total": 0}
            content = env_path.read_text("utf-8", errors="replace")
            variables = _parse_env_content(content)
            # Mask sensitive values
            masked = {}
            for k, v in variables.items():
                if any(s in k.lower() for s in ["key", "secret", "token", "password", "passwd"]):
                    masked[k] = v[:4] + "..." if len(v) > 4 else "****"
                else:
                    masked[k] = v
            return {
                "env_file": str(env_path),
                "variables": masked,
                "total": len(variables),
            }

        elif action == "get":
            if not env_path.exists():
                return {"error": f".env 文件不存在: {env_path}", "key": key}
            if not key:
                return {"error": "请提供 key"}
            content = env_path.read_text("utf-8", errors="replace")
            variables = _parse_env_content(content)
            if key not in variables:
                return {"key": key, "error": f"未找到变量: {key}"}
            val = variables[key]
            # Mask sensitive values
            if any(s in key.lower() for s in ["key", "secret", "token", "password", "passwd"]):
                val = val[:4] + "..." if len(val) > 4 else "****"
            return {"key": key, "value": val}

        elif action == "set":
            if not key:
                return {"error": "请提供 key"}
            content = env_path.read_text("utf-8", errors="replace") if env_path.exists() else ""
            variables = _parse_env_content(content)

            # Update or add
            lines = content.split("\n")
            found = False
            for i, line in enumerate(lines):
                stripped = line.strip()
                if stripped.startswith("#") or "=" not in stripped:
                    continue
                existing_key = stripped.split("=", 1)[0].strip()
                if existing_key == key:
                    lines[i] = f'{key}="{value}"'
                    found = True
                    break
            if not found:
                if content and not content.endswith("\n"):
                    lines.append("")
                lines.append(f'{key}="{value}"')

            env_path.parent.mkdir(parents=True, exist_ok=True)
            env_path.write_text("\n".join(lines), "utf-8")
            return {"action": "set", "key": key, "env_file": str(env_path), "status": "set"}

        elif action == "unset":
            if not env_path.exists():
                return {"error": f".env 文件不存在: {env_path}"}
            if not key:
                return {"error": "请提供 key"}
            content = env_path.read_text("utf-8", errors="replace")
            lines = content.split("\n")
            new_lines = []
            removed = False
            for line in lines:
                stripped = line.strip()
                if stripped.startswith("#") or "=" not in stripped:
                    new_lines.append(line)
                    continue
                existing_key = stripped.split("=", 1)[0].strip()
                if existing_key == key:
                    removed = True
                else:
                    new_lines.append(line)
            env_path.write_text("\n".join(new_lines), "utf-8")
            return {"action": "unset", "key": key, "removed": removed, "env_file": str(env_path)}

        else:
            return {"error": f"不支持的操作: {action}，支持: list/get/set/unset"}

    except PermissionError:
        return {"error": f"无权限操作文件: {env_path}"}
    except Exception as e:
        return {"error": str(e)}


# ── Task Management ─────────────────────────────────────────────────────

TASKS_FILE = os.path.join(get_data_dir(), "tasks.json")


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


async def _task_track(args: dict) -> dict:
    """Create, update, list, delete, or reset tasks for multi-step tracking."""
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
            "content": content,
            "active_form": active_form or content,
            "status": "pending",
            "created_at": datetime.utcnow().isoformat(),
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
        tasks[task_id]["updated_at"] = datetime.utcnow().isoformat()
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
                "created_at": datetime.utcnow().isoformat(),
            }
        _write_tasks(new_tasks)
        return {"task_ids": list(new_tasks.keys()), "total": len(new_tasks)}

    return {"error": f"未知操作: {action}"}


# ── Ask User ────────────────────────────────────────────────────────────

PENDING_QUESTION_FILE = os.path.join(get_data_dir(), "pending_question.json")


def _clear_pending_question():
    if os.path.exists(PENDING_QUESTION_FILE):
        os.remove(PENDING_QUESTION_FILE)


async def _ask_user(args: dict) -> dict:
    """Pause and ask the user a question. Saves to pending file, agent will yield a special SSE event."""
    question = args.get("question", "")
    if not question:
        return {"error": "缺少 question 参数"}

    options = args.get("options", [])
    qid = f"q_{int(time.time() * 1000)}"

    pending = {
        "question_id": qid,
        "question": question,
        "options": options,
        "created_at": datetime.utcnow().isoformat(),
    }
    with open(PENDING_QUESTION_FILE, "w", encoding="utf-8") as f:
        json.dump(pending, f, ensure_ascii=False, indent=2)

    return {
        "__type": "ask_user",
        "question_id": qid,
        "question": question,
        "options": options,
        "status": "pending",
    }


# ── Enter Plan ──────────────────────────────────────────────────────────

async def _enter_plan(args: dict) -> dict:
    """Create a structured plan document for a complex task."""
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
        lines.append(f"")
        lines.append(f"  - [ ] {step}")
    lines.append("")

    content = "\n".join(lines)
    plan_path = os.path.join(plan_dir, f"{plan_id}.md")
    with open(plan_path, "w", encoding="utf-8") as f:
        f.write(content)

    return {
        "plan_id": plan_id,
        "title": title,
        "steps": [{"step": i, "description": s, "status": "pending"} for i, s in enumerate(steps, 1)],
        "total_steps": len(steps),
        "plan_content": content,
        "message": f"计划「{title}」已创建，共 {len(steps)} 个步骤。完成每步后请更新对应的 todo 状态。",
    }


# ── Spawn Subagent ──────────────────────────────────────────────────────

async def _spawn_subagent(args: dict) -> dict:
    """Create an independent sub-task for parallel processing."""
    task_desc = args.get("task_description", "")
    context = args.get("context", "")

    if not task_desc:
        return {"error": "缺少 task_description 参数"}

    sub_id = f"sub_{int(time.time() * 1000)}"
    sub_dir = os.path.join(get_data_dir(), "subagents")
    os.makedirs(sub_dir, exist_ok=True)

    sub_task = {
        "subagent_id": sub_id,
        "task_description": task_desc,
        "context": context,
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        "result": None,
    }
    sub_path = os.path.join(sub_dir, f"{sub_id}.json")
    with open(sub_path, "w", encoding="utf-8") as f:
        json.dump(sub_task, f, ensure_ascii=False, indent=2)

    return {
        "subagent_id": sub_id,
        "task_description": task_desc,
        "status": "pending",
        "message": f"子任务已创建（ID: {sub_id}），可在此任务完成后按顺序处理。",
    }


# ── Schedule Task ───────────────────────────────────────────────────────

async def _schedule_task(args: dict) -> dict:
    """Schedule a task to run at a future time using cron expression."""
    prompt = args.get("prompt", "")
    cron = args.get("cron", "")
    recurring = args.get("recurring", True)

    if not prompt or not cron:
        return {"error": "缺少 prompt 或 cron 参数"}

    sched_id = f"sched_{int(time.time() * 1000)}"
    sched_dir = os.path.join(get_data_dir(), "scheduled")
    os.makedirs(sched_dir, exist_ok=True)

    schedule = {
        "schedule_id": sched_id,
        "prompt": prompt,
        "cron": cron,
        "recurring": recurring,
        "created_at": datetime.now().isoformat(),
        "status": "active",
    }
    sched_path = os.path.join(sched_dir, f"{sched_id}.json")
    with open(sched_path, "w", encoding="utf-8") as f:
        json.dump(schedule, f, ensure_ascii=False, indent=2)

    return {
        "schedule_id": sched_id,
        "prompt": prompt,
        "cron": cron,
        "recurring": recurring,
        "message": f"定时任务已创建（ID: {sched_id}），cron: {cron}，{'重复执行' if recurring else '一次性任务'}。",
    }


def _parse_env_content(content: str) -> dict[str, str]:
    """Parse .env file content into a dict."""
    variables = {}
    for line in content.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            continue
        key, _, val = stripped.partition("=")
        key = key.strip()
        val = val.strip()
        # Remove surrounding quotes
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
            val = val[1:-1]
        variables[key] = val
    return variables
