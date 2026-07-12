"""File read/write/search/edit tools."""

import glob as glob_module
import json
import os
from pathlib import Path

from app.services.security import WORKSPACE_ROOT, in_workspace, ALLOWED_WRITE_EXTENSIONS
from app.services.file_parser_service import parse_file


async def _file_read(args: dict, context: dict | None = None) -> dict:
    filepath = args.get("path", "")
    if not filepath:
        return {"error": "缺少文件路径"}

    project_path = (context or {}).get("project_path", "")

    try:
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
                if candidate.exists() and candidate.is_file() and in_workspace(candidate):
                    resolved_path = candidate
                    break
            except (PermissionError, OSError):
                continue

        if resolved_path is None:
            p = Path(filepath).resolve()
            if not in_workspace(p):
                hint = f" (项目目录: {project_path})" if project_path else ""
                return {"error": f"文件不存在或无权访问: {filepath}{hint}"}
            return {"error": f"文件不存在: {filepath}"}

        ext = resolved_path.suffix.lower()

        if ext in (".pdf", ".docx", ".doc", ".xlsx", ".xls"):
            file_bytes = resolved_path.read_bytes()
            result = parse_file(file_bytes, resolved_path.name)
            if "error" in result:
                return {"error": result["error"]}
            content = result.get("text", "")
            metadata = {k: v for k, v in result.items() if k not in ("text", "filename")}
            lines = content.split("\n")
            return {"path": str(resolved_path), "size": len(content), "lines": len(lines), "content": content, **metadata}

        content = resolved_path.read_text("utf-8", errors="replace")
        lines = content.split("\n")
        return {"path": str(resolved_path), "size": len(content), "lines": len(lines), "content": content}
    except PermissionError:
        return {"error": f"无权限读取: {filepath}"}
    except Exception as e:
        return {"error": str(e)}


async def _file_write(args: dict, context: dict | None = None) -> dict:
    filepath = args.get("path", "")
    content = args.get("content", "")
    project_path = (context or {}).get("project_path", "")

    if not filepath:
        return {"error": "缺少文件路径"}

    ext = Path(filepath).suffix.lower()
    if ext and ext not in ALLOWED_WRITE_EXTENSIONS:
        return {"error": f"不支持写入该文件类型: {ext}，允许: {', '.join(sorted(ALLOWED_WRITE_EXTENSIONS))}"}

    try:
        path = Path(filepath)
        if not path.is_absolute() and project_path:
            path = Path(project_path) / filepath
        if not in_workspace(path):
            return {"error": f"无权写入该路径（超出工作区范围）: {filepath}"}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, "utf-8")
        return {"path": str(path.resolve()), "size": len(content), "status": "written"}
    except PermissionError:
        return {"error": f"无权限写入: {filepath}"}
    except Exception as e:
        return {"error": str(e)}


async def _file_search(args: dict) -> dict:
    pattern = args.get("pattern", "")
    search_text = args.get("search_text", "")
    root_dir = args.get("root_dir", ".")
    max_results = min(int(args.get("max_results", 20)), 100)
    exclude_dirs = {"node_modules", ".git", "__pycache__", ".venv", "dist", "build", ".skills", ".tools"}

    root_path = Path(root_dir).resolve()
    if root_dir != "." and not in_workspace(root_path):
        return {"error": f"无权搜索该目录（超出工作区范围）: {root_dir}"}

    results = []

    if pattern and not search_text:
        for p in glob_module.glob(pattern, root_dir=root_dir, recursive=True):
            full = os.path.join(root_dir, p) if root_dir != "." else p
            if not any(excluded in full.split(os.sep) for excluded in exclude_dirs):
                results.append({"path": full})
                if len(results) >= max_results:
                    break
        return {"pattern": pattern, "matches": results, "total": len(results)}

    elif search_text:
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


async def _edit_file(args: dict) -> dict:
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
    if not in_workspace(path):
        return {"error": f"无权编辑该文件（超出工作区范围）: {filepath}"}

    try:
        content = path.read_text("utf-8", errors="replace")

        if replace_all:
            if old_string not in content:
                return {"error": f"未在文件中找到匹配文本（replace_all）: {old_string[:100]}"}
            new_content = content.replace(old_string, new_string)
            count = content.count(old_string)
        else:
            idx = content.find(old_string)
            if idx == -1:
                return {"error": f"未在文件中找到匹配文本: {old_string[:100]}"}
            new_content = content[:idx] + new_string + content[idx + len(old_string):]
            count = 1

        path.write_text(new_content, "utf-8")
        return {"path": str(path.resolve()), "replaced": count, "size_before": len(content), "size_after": len(new_content), "status": "edited"}
    except PermissionError:
        return {"error": f"无权限编辑: {filepath}"}
    except Exception as e:
        return {"error": str(e)}


async def _file_delete(args: dict) -> dict:
    """Delete a file or empty directory."""
    filepath = args.get("path", "")
    if not filepath:
        return {"error": "缺少文件路径"}

    path = Path(filepath)
    if not path.exists():
        return {"error": f"文件或目录不存在: {filepath}"}
    if not in_workspace(path):
        return {"error": f"无权删除（超出工作区范围）: {filepath}"}

    try:
        if path.is_dir():
            # Only allow deleting empty directories for safety
            if any(path.iterdir()):
                return {"error": f"目录不为空，无法删除: {filepath}"}
            path.rmdir()
        else:
            path.unlink()
        return {"path": str(path.resolve()), "status": "deleted"}
    except PermissionError:
        return {"error": f"无权限删除: {filepath}"}
    except Exception as e:
        return {"error": str(e)}


async def _file_rename(args: dict) -> dict:
    """Rename or move a file/directory."""
    filepath = args.get("path", "")
    new_name = args.get("new_name", "")
    if not filepath or not new_name:
        return {"error": "请提供 path（原路径）和 new_name（新名称）"}

    path = Path(filepath)
    if not path.exists():
        return {"error": f"文件或目录不存在: {filepath}"}
    if not in_workspace(path):
        return {"error": f"无权操作（超出工作区范围）: {filepath}"}

    try:
        new_path = path.parent / new_name
        if new_path.exists():
            return {"error": f"目标文件已存在: {new_name}"}
        if not in_workspace(new_path):
            return {"error": f"无权写入目标路径（超出工作区范围）: {new_name}"}
        path.rename(new_path)
        return {"path": str(new_path.resolve()), "old_path": str(path.resolve()), "status": "renamed"}
    except PermissionError:
        return {"error": f"无权限重命名: {filepath}"}
    except Exception as e:
        return {"error": str(e)}


async def _read_lines(args: dict) -> dict:
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
    if not in_workspace(path):
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
        return {"path": str(path.resolve()), "total_lines": total, "start_line": start, "end_line": end, "lines": len(selected), "content": "\n".join(selected)}
    except PermissionError:
        return {"error": f"无权限读取: {filepath}"}
    except Exception as e:
        return {"error": str(e)}


async def _dir_list(args: dict, context: dict | None = None) -> dict:
    """List files and directories at the given path."""
    dir_path = args.get("path", "")
    project_path = (context or {}).get("project_path", "")

    try:
        path = Path(dir_path) if dir_path else Path(".")
        if not path.is_absolute() and project_path:
            path = Path(project_path) / dir_path if dir_path else Path(project_path)
        if not path.exists():
            return {"error": f"目录不存在: {dir_path or '.'}"}
        if not path.is_dir():
            return {"error": f"路径不是目录: {dir_path or '.'}"}
        if not in_workspace(path):
            return {"error": f"无权访问该目录: {dir_path or '.'}"}

        entries = []
        for entry in sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
            entries.append({
                "name": entry.name,
                "type": "dir" if entry.is_dir() else "file",
                "size": entry.stat().st_size if entry.is_file() else 0,
            })

        return {"path": str(path.resolve()), "entries": entries, "total": len(entries)}
    except PermissionError:
        return {"error": f"无权限访问: {dir_path or '.'}"}
    except Exception as e:
        return {"error": str(e)}
