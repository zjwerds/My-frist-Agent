"""File change monitoring tools (polling-based)."""

from pathlib import Path

from app.services.security import WORKSPACE_ROOT, in_workspace

_watch_snapshots: dict[str, dict] = {}


async def _watch_files(args: dict) -> dict:
    directory = args.get("directory", str(WORKSPACE_ROOT))
    reset = args.get("reset", False)
    max_results = int(args.get("max_results", 50))

    dir_path = Path(directory).resolve()
    if not in_workspace(dir_path):
        return {"error": f"无权监视该目录（超出工作区范围）: {directory}"}

    snapshot_key = str(dir_path)

    if reset:
        _take_snapshot(snapshot_key, dir_path, max_results)
        return {"directory": str(dir_path), "status": "snapshot_taken", "changes": []}

    previous = _watch_snapshots.get(snapshot_key)
    if previous is None:
        _take_snapshot(snapshot_key, dir_path, max_results)
        return {"directory": str(dir_path), "status": "first_snapshot_taken", "changes": []}

    changes = _detect_changes(snapshot_key, dir_path, max_results)
    _take_snapshot(snapshot_key, dir_path, max_results)

    return {"directory": str(dir_path), "status": "ok", "changes": changes, "change_count": len(changes)}


def _take_snapshot(key: str, directory: Path, max_results: int) -> None:
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
    previous = _watch_snapshots.get(key, {})
    _take_snapshot(key + "_current", directory, max_results * 10)
    current = _watch_snapshots.pop(key + "_current", {})

    changes = []
    exclude = {"node_modules", ".git", "__pycache__", ".venv", "dist", "build"}

    for rel_path, mtime in current.items():
        parts = Path(rel_path).parts
        if any(ex in parts for ex in exclude):
            continue
        if rel_path not in previous:
            changes.append({"file": rel_path, "type": "added"})
        elif previous[rel_path] != mtime:
            changes.append({"file": rel_path, "type": "modified"})

    for rel_path in previous:
        if rel_path not in current:
            parts = Path(rel_path).parts
            if any(ex in parts for ex in exclude):
                continue
            changes.append({"file": rel_path, "type": "deleted"})

    changes.sort(key=lambda c: c["file"])
    return changes[:max_results]
