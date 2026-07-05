"""Background process management tools."""

import subprocess
import threading
import time as time_module
from pathlib import Path

from app.services.security import WORKSPACE_ROOT, in_workspace, safe_command_split

_processes: dict[str, dict] = {}
_process_counter = 0
_process_lock = threading.Lock()


async def _start_process(args: dict) -> dict:
    global _process_counter
    command = args.get("command", "")
    work_dir = args.get("work_dir", str(WORKSPACE_ROOT))
    process_id = args.get("process_id", "")

    if not command:
        return {"error": "请提供 command（要执行的命令）"}

    wd = Path(work_dir).resolve()
    if not in_workspace(wd):
        return {"error": f"无权在该目录启动进程（超出工作区范围）: {work_dir}"}

    cmd_list = safe_command_split(command)
    if cmd_list is None:
        return {"error": f"命令包含不安全的 shell 元字符，已阻止: {command}"}

    try:
        proc = subprocess.Popen(
            cmd_list, shell=False, cwd=str(wd),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )

        if not process_id:
            with _process_lock:
                _process_counter += 1
                process_id = f"proc_{_process_counter}"

        with _process_lock:
            _processes[process_id] = {
                "process": proc, "command": command, "work_dir": str(wd),
                "started_at": time_module.strftime("%H:%M:%S"),
                "stdout_buf": [], "stderr_buf": [], "running": True,
            }

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

        return {"process_id": process_id, "command": command, "work_dir": str(wd), "status": "started", "pid": proc.pid}
    except FileNotFoundError:
        return {"error": "命令未找到"}
    except Exception as e:
        return {"error": str(e)}


async def _stop_process(args: dict) -> dict:
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

        return {"process_id": process_id, "command": entry["command"], "exit_code": proc.returncode, "status": "stopped"}
    except Exception as e:
        return {"error": str(e)}


async def _read_process_log(args: dict) -> dict:
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

    return {"process_id": process_id, "command": entry["command"], "stream": stream, "lines": len(selected), "content": "\n".join(selected), "running": is_running, "exit_code": exit_code}
