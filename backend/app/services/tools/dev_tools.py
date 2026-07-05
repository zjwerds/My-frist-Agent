"""Shell, git, code review, package management, test runner, migration tools."""

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from app.services.security import WORKSPACE_ROOT, in_workspace, safe_command_split


async def _shell_command(args: dict) -> dict:
    command = args.get("command", "")
    work_dir = args.get("work_dir", None)
    timeout = int(args.get("timeout", 30))

    if not command:
        return {"error": "缺少命令"}

    if work_dir:
        wd_path = Path(work_dir).resolve()
        if not in_workspace(wd_path):
            return {"error": f"无权在该目录执行命令（超出工作区范围）: {work_dir}"}
    else:
        work_dir = str(WORKSPACE_ROOT)

    cmd_list = safe_command_split(command)
    if cmd_list is None:
        return {"error": f"命令包含不安全的 shell 元字符，已阻止: {command}"}

    try:
        result = subprocess.run(
            cmd_list, shell=False, cwd=work_dir,
            capture_output=True, text=True, timeout=timeout,
        )
        output = result.stdout or ""
        error = result.stderr or ""
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


async def _code_review(args: dict) -> dict:
    filepath = args.get("path", "")
    code = args.get("code", "")

    issues = []

    if filepath:
        path = Path(filepath)
        if not path.exists():
            return {"error": f"文件不存在: {filepath}"}
        try:
            result = subprocess.run(["flake8", str(path)], capture_output=True, text=True, timeout=30)
            for line in result.stdout.strip().split("\n"):
                if line:
                    parts = line.split(":", 3)
                    if len(parts) >= 4:
                        issues.append({"line": int(parts[1]), "col": int(parts[2]), "message": parts[3].strip()})
                    else:
                        issues.append({"message": line})
            return {"file": filepath, "issues": issues, "total": len(issues)}
        except subprocess.TimeoutExpired:
            return {"error": "代码审查超时"}
        except FileNotFoundError:
            return {"error": "flake8 未安装"}

    elif code:
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
                f.write(code)
                tmp_path = f.name
            result = subprocess.run(["flake8", tmp_path], capture_output=True, text=True, timeout=30)
            for line in result.stdout.strip().split("\n"):
                if line:
                    parts = line.split(":", 3)
                    if len(parts) >= 4:
                        issues.append({"line": int(parts[1]), "col": int(parts[2]), "message": parts[3].strip()})
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


async def _git_operation(args: dict) -> dict:
    action = args.get("action", "")
    repo_path = args.get("repo_path", str(WORKSPACE_ROOT))

    if not action:
        return {"error": "缺少 action 参数，支持: status/diff/log/add/commit/push/pull/branch/checkout/merge"}

    repo = Path(repo_path)
    if not in_workspace(repo):
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
            cmd.extend(["log", "--oneline", f"-{count}", "--decorate"])
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

        result = subprocess.run(cmd, cwd=str(repo), capture_output=True, text=True, timeout=30)
        return {"action": action, "exit_code": result.returncode, "stdout": result.stdout[:5000] + ("...(truncated)" if len(result.stdout) > 5000 else ""), "stderr": result.stderr[:2000] + ("...(truncated)" if len(result.stderr) > 2000 else "")}
    except subprocess.TimeoutExpired:
        return {"action": action, "error": "git 操作超时（30秒）"}
    except FileNotFoundError:
        return {"action": action, "error": "git 未安装或不在 PATH 中"}
    except Exception as e:
        return {"action": action, "error": str(e)}


async def _npm_install(args: dict) -> dict:
    packages = args.get("packages", "")
    work_dir = args.get("work_dir", str(WORKSPACE_ROOT))
    save_dev = args.get("save_dev", False)

    wd = Path(work_dir).resolve()
    if not in_workspace(wd):
        return {"error": f"无权在该目录操作（超出工作区范围）: {work_dir}"}
    if not (wd / "package.json").exists():
        return {"error": f"该目录没有 package.json: {work_dir}"}

    cmd = ["npm", "install"]
    if packages:
        cmd.extend(packages.split())
    if save_dev:
        cmd.append("--save-dev")

    try:
        result = subprocess.run(cmd, cwd=str(wd), capture_output=True, text=True, timeout=120)
        output = result.stdout or ""
        error = result.stderr or ""
        return {"command": " ".join(cmd), "exit_code": result.returncode, "stdout": output[:3000] + ("...(truncated)" if len(output) > 3000 else ""), "stderr": error[:2000] + ("...(truncated)" if len(error) > 2000 else "")}
    except subprocess.TimeoutExpired:
        return {"error": "npm install 超时（120秒）"}
    except FileNotFoundError:
        return {"error": "npm 未安装或不在 PATH 中"}
    except Exception as e:
        return {"error": str(e)}


async def _pip_install(args: dict) -> dict:
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
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        output = result.stdout or ""
        error = result.stderr or ""
        return {"command": " ".join(cmd), "exit_code": result.returncode, "stdout": output[:3000] + ("...(truncated)" if len(output) > 3000 else ""), "stderr": error[:2000] + ("...(truncated)" if len(error) > 2000 else "")}
    except subprocess.TimeoutExpired:
        return {"error": "pip install 超时（180秒）"}
    except FileNotFoundError:
        return {"error": "pip 未安装或不在 PATH 中"}
    except Exception as e:
        return {"error": str(e)}


async def _run_tests(args: dict) -> dict:
    runner = args.get("runner", "auto")
    work_dir = args.get("work_dir", str(WORKSPACE_ROOT))
    path = args.get("path", "")
    command = args.get("command", "")
    timeout = int(args.get("timeout", 120))

    wd = Path(work_dir).resolve()
    if not in_workspace(wd):
        return {"error": f"无权在该目录操作（超出工作区范围）: {work_dir}"}

    if command:
        cmd_list = safe_command_split(command)
        if cmd_list is None:
            return {"error": f"命令包含不安全的 shell 元字符，已阻止: {command}"}
    elif runner == "pytest":
        cmd_list = [sys.executable, "-m", "pytest", path, "-v", "--tb=short"] if path else [sys.executable, "-m", "pytest", "-v", "--tb=short"]
    elif runner == "npm":
        cmd_list = ["npm", "test"]
    elif runner == "auto":
        if (wd / "pytest.ini").exists() or (wd / "pyproject.toml").exists() or list(wd.glob("test_*.py")) or list(wd.glob("*_test.py")):
            cmd_list = [sys.executable, "-m", "pytest", path, "-v", "--tb=short"] if path else [sys.executable, "-m", "pytest", "-v", "--tb=short"]
        elif (wd / "package.json").exists():
            cmd_list = ["npm", "test"]
        else:
            return {"error": "未检测到测试框架，请显式指定 runner(pytest/npm) 或 command"}
    else:
        return {"error": f"不支持的测试 runner: {runner}，支持: pytest/npm/auto"}

    try:
        result = subprocess.run(cmd_list, shell=False, cwd=str(wd), capture_output=True, text=True, timeout=timeout)
        output = (result.stdout or "") + (result.stderr or "")
        cmd_str = " ".join(cmd_list) if isinstance(cmd_list, list) else cmd_list
        parsed = _parse_test_output(output, runner if runner != "auto" else ("pytest" if "pytest" in str(cmd_list) else "npm"))
        return {"runner": runner, "command": cmd_str, "exit_code": result.returncode, "output": output[:5000] + ("...(truncated)" if len(output) > 5000 else ""), "parsed": parsed}
    except subprocess.TimeoutExpired:
        return {"error": f"测试超时（{timeout}秒）"}
    except FileNotFoundError:
        return {"error": "测试命令未找到"}
    except Exception as e:
        return {"error": str(e)}


def _parse_test_output(output: str, runner: str) -> dict:
    result = {"passed": 0, "failed": 0, "errors": 0, "skipped": 0, "total": 0}

    if runner == "pytest":
        summary = re.search(r"=+\s*(\d+)\s+passed.*?(\d+)\s+failed.*?(\d+)\s+skipped.*?=+", output)
        if summary:
            result["passed"] = int(summary.group(1))
            result["failed"] = int(summary.group(2))
            result["skipped"] = int(summary.group(3))
            result["total"] = result["passed"] + result["failed"] + result["skipped"]
        else:
            result["passed"] = len(re.findall(r"PASSED|\.\.\.", output))
            result["failed"] = len(re.findall(r"FAILED", output))
            result["total"] = result["passed"] + result["failed"]

        failed_tests = re.findall(r"FAILED\s+(\S+)", output)
        if failed_tests:
            result["failed_tests"] = failed_tests[:10]

    elif runner == "npm":
        result["raw_output"] = output[:1000]

    return result


async def _run_migration(args: dict) -> dict:
    command = args.get("command", "upgrade")
    revision = args.get("revision", "head")
    work_dir = args.get("work_dir", str(WORKSPACE_ROOT))
    message = args.get("message", "auto_migration")

    wd = Path(work_dir).resolve()
    if not in_workspace(wd):
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
        result = subprocess.run(cmd, cwd=str(wd), capture_output=True, text=True, timeout=30)
        output = (result.stdout or "") + (result.stderr or "")
        return {"command": command, "revision": revision, "exit_code": result.returncode, "output": output[:3000] + ("...(truncated)" if len(output) > 3000 else "")}
    except FileNotFoundError:
        return {"error": "alembic 未安装或不在 PATH 中（请先 pip install alembic）"}
    except subprocess.TimeoutExpired:
        return {"error": "迁移操作超时（30秒）"}
    except Exception as e:
        return {"error": str(e)}
