import os
from pathlib import Path
from fastapi import APIRouter, Query, HTTPException

router = APIRouter(prefix="/api/files")

# Restrict file access to the project directory and below
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent  # backend/
PROJECTS_DIR = WORKSPACE_ROOT.parent / "projects"  # agent-platform/projects/

ALLOWED_EXTENSIONS = {
    ".txt", ".md", ".json", ".py", ".js", ".ts", ".tsx", ".jsx",
    ".html", ".css", ".xml", ".yaml", ".yml", ".toml", ".ini", ".cfg",
    ".csv", ".log", ".env", ".sh", ".bat", ".ps1", ".sql",
    ".java", ".c", ".cpp", ".h", ".hpp", ".rs", ".go", ".rb",
}

MAX_FILE_SIZE = 1024 * 1024  # 1MB preview limit
MAX_CONTENT_CHARS = 50000


def _should_show(name: str) -> bool:
    """Filter out hidden files/dirs and common noise."""
    if name.startswith("."):
        return False
    if name.startswith("__") and name != "__init__.py":
        return False
    if name in ("node_modules", ".venv", ".git", "__pycache__", "dist", "build"):
        return False
    return True


def _resolve_path(path: str, root: str | None = None) -> Path:
    """Resolve a path, optionally relative to a project root, with security boundary check."""
    try:
        if root:
            root_path = Path(root).resolve()
            if not root_path.is_dir():
                raise HTTPException(400, f"项目根路径不是有效目录: {root}")
            # SECURITY: Reject filesystem roots (C:\, /) to prevent path traversal
            workspace = WORKSPACE_ROOT.resolve()
            allowed_parents = [workspace, workspace.parent]  # backend/ and agent-platform/
            if not any(ap in root_path.parents or root_path == ap for ap in allowed_parents):
                raise HTTPException(403, f"项目根路径超出允许范围: {root}")
            p = (root_path / path).resolve()
            # Must stay within the project root
            if root_path not in p.parents and p != root_path:
                raise HTTPException(403, f"无权访问该路径: {path}")
            return p
        else:
            # Fall back to default workspace check
            p = Path(path)
            resolved = p.resolve()
            workspace = WORKSPACE_ROOT.resolve()
            if workspace in resolved.parents or resolved == workspace:
                return resolved
            agent_root = workspace.parent
            if agent_root in resolved.parents or resolved == agent_root:
                return resolved
            raise HTTPException(403, f"无权访问该路径: {path}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


def _get_base_rel(p: Path, root: str | None = None) -> str:
    """Return a display-friendly relative path for the given resolved path."""
    if root:
        root_path = Path(root).resolve()
        try:
            return str(p.relative_to(root_path))
        except ValueError:
            return str(p)
    try:
        return str(p.relative_to(WORKSPACE_ROOT.parent))
    except ValueError:
        return str(p)


@router.get("")
def list_dir(path: str = Query(".", description="Directory to list"), root: str | None = Query(None, description="Project root path")):
    """List files and directories in a given path."""
    try:
        p = _resolve_path(path, root)
        if not p.is_dir():
            raise HTTPException(400, f"路径不是目录: {path}")

        entries = []
        for child in sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
            if not _should_show(child.name):
                continue
            try:
                st = child.stat()
                entries.append({
                    "name": child.name,
                    "path": _get_base_rel(child, root),
                    "type": "dir" if child.is_dir() else "file",
                    "size": st.st_size if child.is_file() else 0,
                    "ext": child.suffix.lower() if child.is_file() else "",
                })
            except (PermissionError, OSError):
                continue

        parent_rel = _get_base_rel(p.parent, root) if p != p.parent else None
        return {
            "path": _get_base_rel(p, root),
            "parent": parent_rel,
            "entries": entries,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/read")
def read_file(path: str = Query(..., description="File path to read"), root: str | None = Query(None, description="Project root path")):
    """Read a text file's content."""
    try:
        p = _resolve_path(path, root)
        if not p.is_file():
            raise HTTPException(400, f"路径不是文件: {path}")

        ext = p.suffix.lower()
        size = p.stat().st_size

        # ── Binary document formats (docx/xlsx/pdf) ──
        if ext in (".docx", ".doc", ".xlsx", ".xls", ".pdf"):
            return {
                "path": _get_base_rel(p, root),
                "name": p.name,
                "ext": ext,
                "size": size,
                "content": "此文件是文档格式，无法直接预览文本内容。可上传到对话中，AI 将自动读取其文字。",
                "truncated": False,
                "lines": 1,
                "binary": True,
                "binary_type": "document",
            }

        # ── Image files ──
        if ext in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg", ".ico"):
            return {
                "path": _get_base_rel(p, root),
                "name": p.name,
                "ext": ext,
                "size": size,
                "content": "此文件为图片文件，无法以文本方式预览。可将图片发送给 AI 助手进行分析。",
                "truncated": False,
                "lines": 1,
                "binary": True,
                "binary_type": "image",
            }

        if size > MAX_FILE_SIZE:
            raise HTTPException(413, f"文件过大（{size} bytes），最大支持 1MB")

        content = p.read_text("utf-8", errors="replace")
        truncated = len(content) > MAX_CONTENT_CHARS

        return {
            "path": _get_base_rel(p, root),
            "name": p.name,
            "ext": ext,
            "size": size,
            "content": content[:MAX_CONTENT_CHARS] + ("\n...(截断)" if truncated else ""),
            "truncated": truncated,
            "lines": len(content.split("\n")),
        }
    except HTTPException:
        raise
    except UnicodeDecodeError:
        raise HTTPException(422, "无法以文本方式读取该文件（二进制文件）")
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/create-dir")
def create_dir(body: dict, root: str | None = Query(None, description="Project root path")):
    """Create a new directory at the given path."""
    try:
        dir_path_str = body.get("path", "")
        if not dir_path_str:
            raise HTTPException(400, "请提供要创建的目录路径")

        # When creating a project (no root), default to projects/ under installation path
        effective_root = root or str(PROJECTS_DIR)
        if root is None:
            PROJECTS_DIR.mkdir(parents=True, exist_ok=True)

        p = _resolve_path(dir_path_str, effective_root)
        if p.exists():
            raise HTTPException(409, f"路径已存在: {dir_path_str}")

        p.mkdir(parents=True, exist_ok=False)
        # Return absolute path when creating under projects dir (so frontend can use as project root)
        return_path = str(p) if root is None else _get_base_rel(p, effective_root)
        return {"success": True, "path": return_path}
    except HTTPException:
        raise
    except PermissionError:
        raise HTTPException(403, "无权限创建该目录")
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/create-file")
def create_file(body: dict, root: str | None = Query(None, description="Project root path")):
    """Create a new file at the given path."""
    try:
        file_path_str = body.get("path", "")
        content = body.get("content", "")
        if not file_path_str:
            raise HTTPException(400, "请提供要创建的文件路径")

        effective_root = root or str(PROJECTS_DIR)
        if root is None:
            PROJECTS_DIR.mkdir(parents=True, exist_ok=True)

        p = _resolve_path(file_path_str, effective_root)
        if p.exists():
            raise HTTPException(409, f"文件已存在: {file_path_str}")

        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")

        return_path = str(p) if root is None else _get_base_rel(p, effective_root)
        return {"success": True, "path": return_path}
    except HTTPException:
        raise
    except PermissionError:
        raise HTTPException(403, "无权限创建该文件")
    except Exception as e:
        raise HTTPException(500, str(e))


@router.delete("")
def delete_file(path: str = Query(...), root: str | None = Query(None, description="Project root path")):
    """Delete a file or empty directory at the given path."""
    try:
        p = _resolve_path(path, root)
        if not p.exists():
            raise HTTPException(404, f"路径不存在: {path}")

        # Security: prevent deleting workspace root or project root
        workspace = WORKSPACE_ROOT.resolve()
        agent_root = workspace.parent
        if p == workspace or p == agent_root:
            raise HTTPException(403, "不允许删除项目根目录")

        if p.is_dir():
            # Only allow deleting empty directories for safety
            try:
                p.rmdir()
            except OSError:
                raise HTTPException(409, "目录非空，无法删除（请先删除其中的文件）")
        else:
            p.unlink()

        return {"success": True, "path": _get_base_rel(p, root)}
    except HTTPException:
        raise
    except PermissionError:
        raise HTTPException(403, "无权限删除该路径")
    except Exception as e:
        raise HTTPException(500, str(e))
