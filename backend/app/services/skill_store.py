"""File-based skill store — reads/writes skills in .skills/ and tools in .tools/."""

import json
import os
import sys
import glob
import logging
import re

from app.utils import get_data_dir

logger = logging.getLogger(__name__)

SKILL_DIR = os.path.join(get_data_dir(), ".skills")
TOOL_DIR = os.path.join(get_data_dir(), ".tools")

# ── In-memory cache ──────────────────────────────────────────────────────
_cache_skills: list[dict] | None = None
_tool_cache: list[dict] | None = None

def _clear_cache() -> None:
    global _cache_skills, _tool_cache
    _cache_skills = None
    _tool_cache = None

# ── Seed data ───────────────────────────────────────────────────────────

_SEED_MD_SKILLS = [
    {
        "filename": "find-skills.md",
        "content": """---
name: find-skills
description: 帮助用户发现和安装 skills.sh 上的 AI 编码技能包
---

# Find Skills

This skill helps you discover and install skills from the open agent skills ecosystem.

## When to Use This Skill

Use this skill when the user:

- Asks "how do I do X" where X might be a common task with an existing skill
- Says "find a skill for X" or "is there a skill for X"
- Asks "can you do X" where X is a specialized capability
- Expresses interest in extending agent capabilities
- Wants to search for tools, templates, or workflows

## What is the Skills CLI?

The Skills CLI (`npx skills`) is the package manager for the open agent skills ecosystem. Skills are modular packages that extend agent capabilities with specialized knowledge, workflows, and tools.

**Key commands:**
- `npx skills find [query] [--owner <owner>]` - Search for skills
- `npx skills add <package>` - Install a skill from GitHub
- `npx skills check` - Check for skill updates
- `npx skills update` - Update all installed skills

**Browse skills at:** https://skills.sh/

## How to Help Users Find Skills

### Step 1: Understand What They Need

When a user asks for help with something, identify:
1. The domain (e.g., React, testing, design, deployment)
2. The specific task (e.g., writing tests, creating animations, reviewing PRs)
3. Whether this is a common enough task that a skill likely exists

### Step 2: Check the Leaderboard First

Before running a CLI search, check the [skills.sh leaderboard](https://skills.sh/) to see if a well-known skill already exists for the domain. The leaderboard ranks skills by total installs.

Top skills include:
- `vercel-labs/agent-skills` — React, Next.js, web design
- `anthropics/skills` — Frontend design, document processing

### Step 3: Search for Skills

If the leaderboard doesn't cover the user's need, run the find command:

```bash
npx skills find [query] [--owner <owner>]
```

For example:
- `npx skills find react testing` — Find React testing skills
- `npx skills find design --owner vercel-labs` — Find design skills by owner
- `npx skills find` — Interactive search

### Step 4: Install and Activate

Once a skill is found, install it:

```bash
npx skills add <source> -g -y
```

After installation, the skill will be available in the agent's skill system.

## Note on the find_skills Tool

This app also has a built-in **find_skills** function tool that can directly search skills.sh. When the user asks about finding skills, you can use that tool alongside this guide.
""",
    },
]

# ── Builtin function seed skills (all real implementations) ─────────────

_SEED_FUNCTION_SKILLS: list[dict] = [
    {
        "id": "web_search",
        "name": "网络搜索",
        "description": "通过 DuckDuckGo 搜索互联网，获取实时信息",
        "category": "搜索信息",
        "enabled": True,
        "builtin": True,
        "hidden": True,
        "type": "function",
        "tool_definition": {
            "type": "function",
            "function": {
                "name": "web_search",
                "description": "搜索互联网获取实时信息。当用户询问最新消息、技术资料、不确定的事实或需要查阅网络信息时，调用此工具。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "搜索关键词，尽量简洁精确"},
                        "max_results": {"type": "integer", "description": "返回结果数量（最多20条，默认5）"}
                    },
                    "required": ["query"]
                }
            }
        }
    },
    {
        "id": "web_fetch",
        "name": "网页抓取",
        "description": "读取指定 URL 的网页内容",
        "category": "搜索信息",
        "enabled": True,
        "builtin": True,
        "hidden": True,
        "type": "function",
        "tool_definition": {
            "type": "function",
            "function": {
                "name": "web_fetch",
                "description": "获取并读取一个 URL 的文本内容。当需要查看完整的网页文章、文档或 API 响应时，先调用 web_search 获取 URL，再用此工具读取内容。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "要读取的完整 URL"},
                        "max_length": {"type": "integer", "description": "最大返回字符数（默认5000）"}
                    },
                    "required": ["url"]
                }
            }
        }
    },
    {
        "id": "file_read",
        "name": "读取文件",
        "description": "读取本地文件的内容",
        "category": "代码开发",
        "enabled": True,
        "builtin": True,
        "hidden": True,
        "type": "function",
        "tool_definition": {
            "type": "function",
            "function": {
                "name": "file_read",
                "description": "读取指定路径的文件内容。当用户要求查看、分析或审查某个文件时调用此工具。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "文件路径，可以是绝对路径或相对于工作目录的路径"}
                    },
                    "required": ["path"]
                }
            }
        }
    },
    {
        "id": "file_write",
        "name": "写文件",
        "description": "创建或覆写本地文件",
        "category": "代码开发",
        "enabled": True,
        "builtin": True,
        "hidden": True,
        "type": "function",
        "tool_definition": {
            "type": "function",
            "function": {
                "name": "file_write",
                "description": "创建新文件或覆写已有文件的内容。当用户要求生成代码、修改文件或创建新文件时调用此工具。注意：此工具会覆盖目标文件的现有内容。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "文件路径，可以是绝对路径或相对于工作目录的路径"},
                        "content": {"type": "string", "description": "要写入的文件内容"}
                    },
                    "required": ["path", "content"]
                }
            }
        }
    },
    {
        "id": "file_search",
        "name": "搜索文件",
        "description": "按文件名模式或文件内容搜索项目文件",
        "category": "代码开发",
        "enabled": True,
        "builtin": True,
        "hidden": True,
        "type": "function",
        "tool_definition": {
            "type": "function",
            "function": {
                "name": "file_search",
                "description": "在项目文件中搜索。支持两种模式：1) pattern 参数按 glob 文件名匹配 2) search_text 参数在文件内容中搜索指定文本。自动排除 node_modules/.git/__pycache__/dist/build 目录。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "pattern": {"type": "string", "description": "文件名 glob 模式，如 \"**/*.py\" 或 \"src/**/*.tsx\""},
                        "search_text": {"type": "string", "description": "要搜索的文件内容文本"},
                        "root_dir": {"type": "string", "description": "搜索根目录（默认为当前目录）"},
                        "max_results": {"type": "integer", "description": "最大返回结果数（最多100，默认20）"}
                    }
                }
            }
        }
    },
    {
        "id": "shell_command",
        "name": "执行命令",
        "description": "在终端中执行 shell 命令",
        "category": "代码开发",
        "enabled": True,
        "builtin": True,
        "hidden": True,
        "type": "function",
        "tool_definition": {
            "type": "function",
            "function": {
                "name": "shell_command",
                "description": "执行终端命令（git、npm、python、pip、ls 等）。当用户要求运行测试、安装依赖、查看 git 状态、构建项目或执行任何 shell 操作时调用此工具。注意：命令会在本地计算机上实际执行。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "要执行的 shell 命令"},
                        "work_dir": {"type": "string", "description": "工作目录（可选，默认为当前目录）"},
                        "timeout": {"type": "integer", "description": "超时秒数（默认30，最大120）"}
                    },
                    "required": ["command"]
                }
            }
        }
    },
    {
        "id": "code_review",
        "name": "代码审查",
        "description": "使用 flake8 对 Python 代码进行静态检查",
        "category": "代码开发",
        "enabled": True,
        "builtin": True,
        "hidden": True,
        "type": "function",
        "tool_definition": {
            "type": "function",
            "function": {
                "name": "code_review",
                "description": "对 Python 代码进行静态审查，检查代码风格、潜在错误和不良实践。可以审查已有文件（提供 path）或直接审查代码片段（提供 code）。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "要审查的 Python 文件路径"},
                        "code": {"type": "string", "description": "要审查的 Python 代码字符串（与 path 二选一）"}
                    }
                }
            }
        }
    },
    {
        "id": "translator",
        "name": "翻译",
        "description": "在多种语言之间翻译文本",
        "category": "写作内容",
        "enabled": True,
        "builtin": True,
        "hidden": True,
        "type": "function",
        "tool_definition": {
            "type": "function",
            "function": {
                "name": "translator",
                "description": "翻译文本到目标语言。支持100+种语言，自动检测源语言。当用户要求翻译文字或需要将内容转为另一种语言时调用此工具。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "待翻译的文本"},
                        "source": {"type": "string", "description": "源语言代码（默认 auto 自动检测），如 en/zh-CN/ja/fr/de/es"},
                        "target": {"type": "string", "description": "目标语言代码（默认 zh-CN），如 en/zh-CN/ja/fr/de/es"}
                    },
                    "required": ["text"]
                }
            }
        }
    },
    {
        "id": "json_formatter",
        "name": "JSON 格式化",
        "description": "格式化、压缩或验证 JSON 字符串",
        "category": "实用工具",
        "enabled": True,
        "builtin": True,
        "hidden": True,
        "type": "function",
        "tool_definition": {
            "type": "function",
            "function": {
                "name": "json_formatter",
                "description": "对 JSON 字符串进行格式化（美化）、压缩（minify）或验证。当用户需要整理乱序的 JSON 或检查 JSON 格式时调用。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "json_string": {"type": "string", "description": "待处理的 JSON 字符串"},
                        "action": {"type": "string", "description": "操作类型：format（格式化）、minify（压缩）、validate（验证），默认 format"}
                    },
                    "required": ["json_string"]
                }
            }
        }
    },
    {
        "id": "regex_tester",
        "name": "正则测试",
        "description": "测试正则表达式匹配结果",
        "category": "实用工具",
        "enabled": True,
        "builtin": True,
        "hidden": True,
        "type": "function",
        "tool_definition": {
            "type": "function",
            "function": {
                "name": "regex_tester",
                "description": "测试正则表达式在文本上的匹配效果，返回匹配位置、内容和分组信息。支持忽略大小写、多行模式和 dotall 模式。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "pattern": {"type": "string", "description": "正则表达式模式"},
                        "text": {"type": "string", "description": "要匹配的文本"},
                        "ignore_case": {"type": "boolean", "description": "是否忽略大小写"},
                        "multiline": {"type": "boolean", "description": "是否启用多行模式（^/$ 匹配每行）"},
                        "dotall": {"type": "boolean", "description": "是否让 . 匹配换行符"}
                    },
                    "required": ["pattern", "text"]
                }
            }
        }
    },
    {
        "id": "ocr_image",
        "name": "图片文字识别",
        "description": "从图片中提取文字（OCR）",
        "category": "实用工具",
        "enabled": True,
        "builtin": True,
        "hidden": True,
        "type": "function",
        "tool_definition": {
            "type": "function",
            "function": {
                "name": "ocr_image",
                "description": "从一张或多张图片中提取文字，返回识别结果。当用户上传了图片且你需要理解图片中的文字时（如截图、扫描件、拍照的文字），调用此工具。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "image_index": {
                            "type": "integer",
                            "description": "要识别的图片索引（从0开始），当前对话中所有图片按发送顺序排列"
                        }
                    },
                    "required": ["image_index"]
                }
            }
        }
    },
        # ── P0 tools ────────────────────────────────────────────────────
    {
        "id": "search_memory",
        "name": "记忆搜索",
        "description": "搜索对话历史中的记忆摘要",
        "category": "代码开发",
        "enabled": True,
        "builtin": True,
        "hidden": True,
        "type": "function",
        "tool_definition": {
            "type": "function",
            "function": {
                "name": "search_memory",
                "description": "在当前对话的压缩记忆中搜索关键词。当需要回顾之前的决定、约束或上下文时调用此工具。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "搜索关键词，用于匹配记忆摘要内容"}
                    },
                    "required": ["query"]
                }
            }
        }
    },
    {
        "id": "git_operation",
        "name": "Git 操作",
        "description": "执行 Git 版本控制操作",
        "category": "代码开发",
        "enabled": True,
        "builtin": True,
        "hidden": True,
        "type": "function",
        "tool_definition": {
            "type": "function",
            "function": {
                "name": "git_operation",
                "description": "执行 Git 命令（status/diff/log/add/commit/push/pull/branch/checkout/merge）。当用户要求查看或操作 Git 仓库时调用此工具。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "description": "Git 操作类型: status/diff/log/add/commit/push/pull/branch/checkout/merge"},
                        "repo_path": {"type": "string", "description": "仓库路径（可选，默认为当前项目目录）"},
                        "message": {"type": "string", "description": "commit 时的提交信息"},
                        "files": {"type": "string", "description": "add 时的文件列表（默认 .）"},
                        "branch": {"type": "string", "description": "push/pull 时的分支名"},
                        "target": {"type": "string", "description": "checkout 目标（分支名或 commit hash）"},
                        "source": {"type": "string", "description": "merge 源分支名"},
                        "count": {"type": "integer", "description": "log 显示的提交数（默认10）"}
                    },
                    "required": ["action"]
                }
            }
        }
    },
    {
        "id": "edit_file",
        "name": "编辑文件",
        "description": "搜索替换方式编辑文件内容",
        "category": "代码开发",
        "enabled": True,
        "builtin": True,
        "hidden": True,
        "type": "function",
        "tool_definition": {
            "type": "function",
            "function": {
                "name": "edit_file",
                "description": "用搜索替换方式编辑已有文件。当需要修改文件中特定内容而非整体覆写时调用此工具。支持 replace_all 参数替换所有匹配项。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "文件路径"},
                        "old_string": {"type": "string", "description": "要被替换的旧文本"},
                        "new_string": {"type": "string", "description": "替换用的新文本"},
                        "replace_all": {"type": "boolean", "description": "是否替换所有匹配项（默认 false）"}
                    },
                    "required": ["path", "old_string"]
                }
            }
        }
    },
    {
        "id": "read_lines",
        "name": "读取行范围",
        "description": "读取文件的指定行范围",
        "category": "代码开发",
        "enabled": True,
        "builtin": True,
        "hidden": True,
        "type": "function",
        "tool_definition": {
            "type": "function",
            "function": {
                "name": "read_lines",
                "description": "读取文件中指定行范围的内容。当用户需要查看文件中间某段代码或日志时调用此工具。行号从1开始。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "文件路径"},
                        "start": {"type": "integer", "description": "起始行号（默认1）"},
                        "end": {"type": "integer", "description": "结束行号（默认文件末尾）"}
                    },
                    "required": ["path"]
                }
            }
        }
    },
    {
        "id": "db_query",
        "name": "数据库查询",
        "description": "对 SQLite 数据库执行只读查询",
        "category": "代码开发",
        "enabled": True,
        "builtin": True,
        "hidden": True,
        "type": "function",
        "tool_definition": {
            "type": "function",
            "function": {
                "name": "db_query",
                "description": "对应用的 SQLite 数据库执行只读 SELECT 查询。当需要查看对话历史、配置或统计数据时调用此工具。注意：仅支持 SELECT 语句。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "sql": {"type": "string", "description": "要执行的 SELECT SQL 查询语句"}
                    },
                    "required": ["sql"]
                }
            }
        }
    },
    # ── P1 tools ────────────────────────────────────────────────────
    {
        "id": "start_process",
        "name": "启动进程",
        "description": "启动后台进程（如 dev server）",
        "category": "代码开发",
        "enabled": True,
        "builtin": True,
        "hidden": True,
        "type": "function",
        "tool_definition": {
            "type": "function",
            "function": {
                "name": "start_process",
                "description": "在后台启动一个长时间运行的进程（如开发服务器）。进程的输出会被缓冲，可以通过 stop_process 和 read_process_log 管理。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "要执行的命令"},
                        "work_dir": {"type": "string", "description": "工作目录（可选）"},
                        "process_id": {"type": "string", "description": "自定义进程 ID（可选，自动生成）"}
                    },
                    "required": ["command"]
                }
            }
        }
    },
    {
        "id": "stop_process",
        "name": "停止进程",
        "description": "停止一个后台进程",
        "category": "代码开发",
        "enabled": True,
        "builtin": True,
        "hidden": True,
        "type": "function",
        "tool_definition": {
            "type": "function",
            "function": {
                "name": "stop_process",
                "description": "停止一个之前启动的后台进程。可以选择 force 强制终止。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "process_id": {"type": "string", "description": "要停止的进程 ID"},
                        "force": {"type": "boolean", "description": "是否强制终止（默认 false）"}
                    },
                    "required": ["process_id"]
                }
            }
        }
    },
    {
        "id": "read_process_log",
        "name": "读取进程日志",
        "description": "读取后台进程的输出日志",
        "category": "代码开发",
        "enabled": True,
        "builtin": True,
        "hidden": True,
        "type": "function",
        "tool_definition": {
            "type": "function",
            "function": {
                "name": "read_process_log",
                "description": "读取一个后台进程的 stdout 或 stderr 输出。支持指定读取行数。当需要查看 dev server 输出或长时间运行任务的结果时调用。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "process_id": {"type": "string", "description": "进程 ID"},
                        "stream": {"type": "string", "description": "输出流（stdout 或 stderr，默认 stdout）"},
                        "lines": {"type": "integer", "description": "读取最近的行数（默认50）"}
                    },
                    "required": ["process_id"]
                }
            }
        }
    },
    {
        "id": "npm_install",
        "name": "安装 npm 包",
        "description": "安装 npm 依赖包",
        "category": "代码开发",
        "enabled": True,
        "builtin": True,
        "hidden": True,
        "type": "function",
        "tool_definition": {
            "type": "function",
            "function": {
                "name": "npm_install",
                "description": "在包含 package.json 的项目目录中安装 npm 依赖。支持指定包名和 --save-dev。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "packages": {"type": "string", "description": "要安装的包名（多个用空格分隔，不填则安装所有依赖）"},
                        "work_dir": {"type": "string", "description": "项目目录（默认当前目录）"},
                        "save_dev": {"type": "boolean", "description": "是否保存到 devDependencies（默认 false）"}
                    }
                }
            }
        }
    },
    {
        "id": "pip_install",
        "name": "安装 pip 包",
        "description": "安装 Python pip 依赖",
        "category": "代码开发",
        "enabled": True,
        "builtin": True,
        "hidden": True,
        "type": "function",
        "tool_definition": {
            "type": "function",
            "function": {
                "name": "pip_install",
                "description": "安装 Python 包。支持指定包名（如 requests==2.28.0）或 requirements.txt 文件路径。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "packages": {"type": "string", "description": "要安装的包名（多个用空格分隔）"},
                        "requirements": {"type": "string", "description": "requirements.txt 路径（与 packages 二选一）"}
                    }
                }
            }
        }
    },
    {
        "id": "run_tests",
        "name": "运行测试",
        "description": "运行 pytest 或 npm test",
        "category": "代码开发",
        "enabled": True,
        "builtin": True,
        "hidden": True,
        "type": "function",
        "tool_definition": {
            "type": "function",
            "function": {
                "name": "run_tests",
                "description": "自动检测并运行项目的测试（pytest 或 npm test）。支持指定 runner 或自定义命令。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "runner": {"type": "string", "description": "测试框架：pytest/npm/auto（默认 auto 自动检测）"},
                        "path": {"type": "string", "description": "测试路径（可选）"},
                        "work_dir": {"type": "string", "description": "工作目录（可选）"},
                        "command": {"type": "string", "description": "自定义测试命令（与 runner 二选一）"},
                        "timeout": {"type": "integer", "description": "超时秒数（默认120）"}
                    }
                }
            }
        }
    },
    # ── P2 tools ────────────────────────────────────────────────────
    {
        "id": "run_migration",
        "name": "运行迁移",
        "description": "执行 Alembic 数据库迁移",
        "category": "代码开发",
        "enabled": True,
        "builtin": True,
        "hidden": True,
        "type": "function",
        "tool_definition": {
            "type": "function",
            "function": {
                "name": "run_migration",
                "description": "执行 Alembic 数据库迁移操作。支持 upgrade/downgrade/autogenerate/history/current/check/branches。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "迁移命令：upgrade/downgrade/autogenerate/history/current/check/branches（默认 upgrade）"},
                        "revision": {"type": "string", "description": "迁移版本号（默认 head）"},
                        "work_dir": {"type": "string", "description": "工作目录（可选）"},
                        "message": {"type": "string", "description": "autogenerate 的迁移信息"}
                    }
                }
            }
        }
    },
    {
        "id": "api_request",
        "name": "API 请求",
        "description": "发送 HTTP 请求测试 API",
        "category": "代码开发",
        "enabled": True,
        "builtin": True,
        "hidden": True,
        "type": "function",
        "tool_definition": {
            "type": "function",
            "function": {
                "name": "api_request",
                "description": "发送 HTTP 请求测试 API 接口。支持 GET/POST/PUT/PATCH/DELETE/HEAD/OPTIONS。可自定义请求头和请求体。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "method": {"type": "string", "description": "HTTP 方法：GET/POST/PUT/PATCH/DELETE/HEAD/OPTIONS（默认 GET）"},
                        "url": {"type": "string", "description": "请求 URL"},
                        "headers": {"type": "object", "description": "请求头（可选）"},
                        "body": {"type": "string", "description": "请求体（POST/PUT/PATCH 时使用）"},
                        "timeout": {"type": "integer", "description": "超时秒数（默认15）"}
                    },
                    "required": ["url"]
                }
            }
        }
    },
    {
        "id": "watch_files",
        "name": "文件监控",
        "description": "监控目录中的文件变更",
        "category": "代码开发",
        "enabled": True,
        "builtin": True,
        "hidden": True,
        "type": "function",
        "tool_definition": {
            "type": "function",
            "function": {
                "name": "watch_files",
                "description": "监控指定目录中的文件变更（新增、修改、删除）。基于轮询修改时间实现。调用时返回自上次调用以来的变更。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "directory": {"type": "string", "description": "要监控的目录（默认当前项目目录）"},
                        "reset": {"type": "boolean", "description": "重置快照（不返回变更，仅重新建立基准）"},
                        "max_results": {"type": "integer", "description": "最大返回变更数（默认50）"}
                    }
                }
            }
        }
    },
    {
        "id": "env_manage",
        "name": "环境变量管理",
        "description": "管理 .env 环境变量文件",
        "category": "代码开发",
        "enabled": True,
        "builtin": True,
        "hidden": True,
        "type": "function",
        "tool_definition": {
            "type": "function",
            "function": {
                "name": "env_manage",
                "description": "管理 .env 文件中的环境变量。支持 list（列出）、get（获取单个）、set（设置/更新）、unset（删除）操作。敏感值会自动脱敏显示。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "description": "操作：list/get/set/unset（默认 list）"},
                        "key": {"type": "string", "description": "变量名（get/set/unset 时需要）"},
                        "value": {"type": "string", "description": "变量值（set 时需要）"},
                        "filepath": {"type": "string", "description": ".env 文件路径（可选，自动查找）"}
                    }
                }
            }
        }
    },
    {
        "id": "task_track",
        "name": "任务管理",
        "description": "创建、更新、列出、删除或重置任务列表，用于追踪多步复杂任务的进度",
        "category": "实用工具",
        "enabled": True,
        "builtin": True,
        "hidden": True,
        "type": "function",
        "tool_definition": {
            "type": "function",
            "function": {
                "name": "task_track",
                "description": "管理任务列表以追踪多步骤任务的进度。支持 create（创建）、update（更新状态/内容）、list（列出所有）、delete（删除）、reset（重置全部）。开始复杂任务时先创建任务列表，每完成一步更新其状态为 completed。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "description": "操作类型：create（创建）、update（更新）、list（列出）、delete（删除）、reset（重置全部）",
                            "enum": ["create", "update", "list", "delete", "reset"]
                        },
                        "task_id": {"type": "string", "description": "任务 ID（update/delete 时需要）"},
                        "content": {"type": "string", "description": "任务描述（create 时必须，update 时可选的）"},
                        "active_form": {"type": "string", "description": "任务进行中的描述，如'正在修改配置文件'（可选）"},
                        "status": {"type": "string", "description": "任务状态：pending（待处理）、in_progress（进行中）、completed（已完成）", "enum": ["pending", "in_progress", "completed"]},
                        "tasks": {"type": "array", "description": "任务列表（reset 时需要），每项包含 content/active_form/status", "items": {"type": "object"}}
                    },
                    "required": ["action"]
                }
            }
        }
    },
    {
        "id": "ask_user",
        "name": "询问用户",
        "description": "在需要时向用户提问以澄清需求、获取决策或确认操作",
        "category": "实用工具",
        "enabled": True,
        "builtin": True,
        "hidden": True,
        "type": "function",
        "tool_definition": {
            "type": "function",
            "function": {
                "name": "ask_user",
                "description": "向用户提出一个问题并等待回答。当需求不明确、需要用户做选择、或需要确认后才能继续操作时调用此工具。支持提供选项供用户选择。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string", "description": "要向用户提出的问题，清晰描述需要确认的事项"},
                        "options": {
                            "type": "array",
                            "description": "可选的选项列表（非必填），让用户从中选择",
                            "items": {"type": "string"}
                        }
                    },
                    "required": ["question"]
                }
            }
        }
    },
    {
        "id": "enter_plan",
        "name": "制定计划",
        "description": "为复杂任务创建结构化实施计划，包含步骤分解和上下文",
        "category": "实用工具",
        "enabled": True,
        "builtin": True,
        "hidden": True,
        "type": "function",
        "tool_definition": {
            "type": "function",
            "function": {
                "name": "enter_plan",
                "description": "在实施复杂任务前创建结构化计划。将任务分解为清晰的步骤，记录上下文和注意事项。生成计划文档供后续实施参考。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "计划的标题，概括任务名称"},
                        "steps": {
                            "type": "array",
                            "description": "实施步骤列表，每一步是一个字符串描述（必填，至少1步）",
                            "items": {"type": "string"},
                            "minItems": 1
                        },
                        "context": {"type": "string", "description": "背景信息、约束条件、注意事项等补充上下文（可选）"}
                    },
                    "required": ["title", "steps"]
                }
            }
        }
    },
    {
        "id": "spawn_subagent",
        "name": "启动子任务",
        "description": "创建独立运行的子任务用于并行处理",
        "category": "实用工具",
        "enabled": True,
        "builtin": True,
        "hidden": True,
        "type": "function",
        "tool_definition": {
            "type": "function",
            "function": {
                "name": "spawn_subagent",
                "description": "创建一个独立的子任务，用于并行处理或后台执行。适合将大型任务拆分为多个可独立执行的小任务。创建后可通过 subagent_id 查询状态和结果。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task_description": {"type": "string", "description": "子任务的详细描述，说明要做什么"},
                        "context": {"type": "string", "description": "子任务需要的附加上下文信息（可选）"}
                    },
                    "required": ["task_description"]
                }
            }
        }
    },
    {
        "id": "schedule_task",
        "name": "定时任务",
        "description": "安排一个在未来特定时间执行的任务",
        "category": "实用工具",
        "enabled": True,
        "builtin": True,
        "hidden": True,
        "type": "function",
        "tool_definition": {
            "type": "function",
            "function": {
                "name": "schedule_task",
                "description": "安排一个在未来特定时间执行的任务。使用 cron 表达式指定执行时间。当用户说「提醒我」「定时」「每天/每周做某事」时使用此工具。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "prompt": {"type": "string", "description": "定时执行的任务描述"},
                        "cron": {"type": "string", "description": "cron 表达式（5位：分 时 日 月 周），如 '0 9 * * *' 表示每天早上9点"},
                        "recurring": {"type": "boolean", "description": "是否重复执行（默认 true），false 表示一次性任务"}
                    },
                    "required": ["prompt", "cron"]
                }
            }
        }
    },
]
# ── Auto-categorization keyword map ────────────────────────────────────

CATEGORY_KEYWORDS = {
    "论文写作": [
        "论文", "paper", "thesis", "学术", "research", "引用", "citation",
        "参考文献", "期刊", "journal", "publication", "写作", "writing",
        "综述", "literature", "methodology", "方法论", "查重", "剽窃",
        "plagiarism", "参考文献管理", "zotero", "endnote", "latex",
    ],
    "前端开发": [
        "react", "vue", "angular", "css", "html", "javascript", "typescript",
        "前端", "web", "ui", "ux", "frontend", "tailwind", "组件", "component",
        "svelte", "next.js", "nuxt", "vite", "webpack", "babel", "eslint",
        "页面", "界面", "布局", "响应式", "responsive", "dom",
    ],
    "后端开发": [
        "api", "backend", "server", "database", "sql", "nosql",
        "fastapi", "django", "flask", "spring", "rust", "go", "golang",
        "graphql", "rest", "微服务", "microservice", "中间件", "middleware",
        "redis", "mongodb", "postgresql", "mysql", "orm", "alembic",
    ],
    "测试开发": [
        "test", "testing", "pytest", "jest", "unittest", "测试",
        "tdd", "ci/cd", "mock", "assertion", "coverage", "覆盖率",
        "e2e", "integration", "单元测试", "集成测试", "端到端",
        "vitest", "mocha", "chai", "selenium", "playwright", "cypress",
    ],
    "DevOps / 部署": [
        "docker", "kubernetes", "k8s", "deploy", "ci", "cd", "jenkins",
        "github actions", "devops", "nginx", "反向代理", "proxy",
        "容器化", "container", "orchestration", "terraform",
        "ansible", "helm", "监控", "monitoring", "grafana", "prometheus",
    ],
    "数据分析": [
        "data", "analysis", "pandas", "numpy", "可视化", "chart",
        "报表", "数据", "analytics", "matplotlib", "统计", "statistics",
        "machine learning", "深度学习", "deep learning", "neural", "训练",
        "train", "pytorch", "tensorflow", "数据挖掘", "data mining",
        "jupyter", "notebook", "特征工程", "feature",
    ],
    "项目管理": [
        "project", "管理", "management", "agile", "scrum", "jira",
        "需求", "requirement", "规划", "planning", "roadmap",
        "迭代", "sprint", "看板", "kanban", "团队", "team",
    ],
    "提示词工程": [
        "prompt", "提示词", "prompt engineering", "指令",
        "chain-of-thought", "cot", "few-shot", "in-context",
        "角色扮演", "persona", "模板", "template",
    ],
    "数据库": [
        "sql", "database", "数据库", "mysql", "postgresql", "redis",
        "mongodb", "sqlite", "oracle", "查询", "query", "index",
        "索引", "迁移", "migration", "schema", "表", "table",
    ],
    "AI / 大模型": [
        "llm", "gpt", "claude", "deepseek", "大模型", "ai", "人工智能",
        "openai", "langchain", "rag", "agent", "embedding", "token",
        "微调", "fine-tune", "qwen", "glm", "yi",
    ],
}


def _auto_categorize_keywords(skill: dict) -> bool:
    """Match skill name/description/content against keyword map.

    Only acts on skills whose category is empty or the default "实用工具".
    Returns True if a category was assigned, False otherwise.
    """
    current = skill.get("category", "") or ""
    if current and current != "实用工具":
        return False

    text = " ".join([
        skill.get("name", ""),
        skill.get("description", ""),
        skill.get("content", ""),
    ]).lower()

    best_cat = ""
    best_score = 0
    for cat, keywords in CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw.lower() in text)
        if score > best_score:
            best_score = score
            best_cat = cat

    if best_score > 0:
        skill["category"] = best_cat
        return True
    return False


# ── AI-based categorization (fallback when keywords don't match) ─────────

_AI_SYSTEM_PROMPT = (
    "你是一个 AI 编程助手的技能分类器。你收到的技能可能涉及代码开发、"
    "测试、部署、数据分析、写作、项目管理等方向。\n"
    "请分析以下技能的定义，用一个中文分类名概括（2-6个字）。"
    "只返回分类名称，不要任何其他文字、标点或解释。"
)


async def _ai_categorize_one(
    name: str,
    description: str,
    api_key: str,
    base_url: str,
    model: str,
) -> str | None:
    """Call DeepSeek API to classify a single skill. Returns category name or None."""
    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        resp = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _AI_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"名称：{name}\n描述：{description}",
                },
            ],
            temperature=0.1,
            max_tokens=20,
        )
        raw = resp.choices[0].message.content or ""
        raw = raw.strip().strip('"').strip("'")
        return raw if raw else None
    except Exception as e:
        logger.warning("AI categorization failed for '%s': %s", name, e)
        return None


async def auto_categorize_ai(
    api_key: str,
    base_url: str = "https://api.deepseek.com",
    model: str = "deepseek-v4-flash",
) -> int:
    """Run AI categorization on all skills whose category is still "实用工具".

    Persists the assigned category back to the skill file.
    Returns the number of skills that were re-categorized.
    """
    skills = list_skills()
    reclassified = 0

    for skill in skills:
        cat = skill.get("category", "") or ""
        if cat and cat != "实用工具":
            continue

        name = skill.get("name", "") or ""
        description = skill.get("description", "") or ""
        if not name and not description:
            continue

        result = await _ai_categorize_one(name, description, api_key, base_url, model)
        if result and result != "实用工具":
            skill["category"] = result
            # Persist back to the skill file
            path = _skill_path(skill.get("id", ""))
            if os.path.exists(path):
                _write_file(path, skill)
                reclassified += 1
                logger.info("AI categorized '%s' → %s", name, result)
            # Throttle to avoid API rate limits
            import asyncio
            await asyncio.sleep(0.5)

    if reclassified > 0:
        _clear_cache()

    return reclassified


# ── Internal helpers ────────────────────────────────────────────────────


def _skill_path(skill_id: str) -> str:
    """Return the path for a skill/tool file, searching both directories."""
    for base in (SKILL_DIR, TOOL_DIR):
        # Subdirectory layout: {base}/{skill_id}/{skill_id}.{ext}
        for ext in (".json", ".md"):
            path = os.path.join(base, skill_id, f"{skill_id}{ext}")
            if os.path.exists(path):
                return path
        # Flat layout: {base}/{skill_id}.{ext}
        for ext in (".json", ".md"):
            path = os.path.join(base, f"{skill_id}{ext}")
            if os.path.exists(path):
                return path
    # Default: subdirectory layout in SKILL_DIR for writes
    return os.path.join(SKILL_DIR, skill_id, f"{skill_id}.json")


def _read_json(path: str) -> dict | None:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.warning("Failed to read skill file %s: %s", path, e)
        return None

    # Function tools don't have SKILL.md — skip lookup
    if data.get("tool_definition"):
        return data

    # Load prompt content from SKILL.md alongside the JSON
    skill_id = data.get("id", os.path.splitext(os.path.basename(path))[0])
    skill_dir = os.path.dirname(path)
    skill_md_path = os.path.join(skill_dir, "SKILL.md")
    if os.path.isfile(skill_md_path):
        md_data = _parse_md(skill_md_path)
        if md_data and md_data.get("content"):
            data["type"] = "prompt"
            data["content"] = md_data["content"]

    return data


def _parse_md(path: str) -> dict | None:
    """Parse a SKILL.md file with YAML frontmatter into a skill dict."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        return None

    # Extract frontmatter between --- markers
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)", text, re.DOTALL)
    if not m:
        return None

    frontmatter = m.group(1)
    body = m.group(2).strip()

    # Simple YAML key: value parser (no dependencies)
    meta = {}
    for line in frontmatter.split("\n"):
        kv = re.match(r"^\s*(\w+):\s*(.*?)\s*$", line)
        if kv:
            meta[kv.group(1)] = kv.group(2).strip().strip('"').strip("'")

    skill_id = os.path.splitext(os.path.basename(path))[0]
    return {
        "id": skill_id,
        "name": meta.get("name", skill_id),
        "description": meta.get("description", ""),
        "category": meta.get("category", "实用工具"),
        "enabled": meta.get("enabled", "true").lower() == "true",
        "builtin": meta.get("builtin", "true").lower() == "true",
        "config": None,
        "type": "prompt",
        "content": body,
    }


def _read_file(path: str) -> dict | None:
    if path.endswith(".md"):
        skill = _parse_md(path)
    else:
        skill = _read_json(path)
    if skill:
        _auto_categorize_keywords(skill)
    return skill


def _write_json(path: str, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _write_md(path: str, data: dict) -> None:
    """Write a dict as a SKILL.md file with YAML frontmatter."""
    frontmatter = (
        f"---\n"
        f"name: {data.get('name', data['id'])}\n"
        f"description: {data.get('description', '')}\n"
        f"category: {data.get('category', '实用工具')}\n"
        f"enabled: {str(data.get('enabled', True)).lower()}\n"
        f"builtin: {str(data.get('builtin', True)).lower()}\n"
        f"---\n"
        f"{data.get('content', '')}\n"
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(frontmatter)


def _write_file(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if path.endswith(".md"):
        _write_md(path, data)
    else:
        _write_json(path, data)


# ── Public API ──────────────────────────────────────────────────────────


def _seed_if_empty() -> None:
    """Seed builtin prompt skills (.md) if directory is empty."""
    os.makedirs(SKILL_DIR, exist_ok=True)
    existing = glob.glob(os.path.join(SKILL_DIR, "**/*.json"), recursive=True) + glob.glob(os.path.join(SKILL_DIR, "**/*.md"), recursive=True)
    if existing:
        return
    logger.info("Seeding %d prompt skill(s) to %s", len(_SEED_MD_SKILLS), SKILL_DIR)
    for entry in _SEED_MD_SKILLS:
        skill_id = os.path.splitext(entry["filename"])[0]
        subdir = os.path.join(SKILL_DIR, skill_id)
        os.makedirs(subdir, exist_ok=True)
        path = os.path.join(subdir, entry["filename"])
        with open(path, "w", encoding="utf-8") as f:
            f.write(entry["content"])


def _seed_function_skills() -> None:
    """Write builtin function skills (.json) to .tools/ that do not yet exist."""
    os.makedirs(TOOL_DIR, exist_ok=True)
    for skill in _SEED_FUNCTION_SKILLS:
        skill_id = skill["id"]
        skill_subdir = os.path.join(TOOL_DIR, skill_id)
        path = os.path.join(skill_subdir, f"{skill_id}.json")
        if not os.path.exists(path):
            logger.info("Seeding function skill: %s", skill_id)
            os.makedirs(skill_subdir, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(skill, f, ensure_ascii=False, indent=2)


def _migrate_skills_to_subdirs() -> None:
    """One-time migration: move flat skill files into {skill_id}/ subdirectories."""
    if not os.path.isdir(SKILL_DIR):
        return
    for ext in ("*.json", "*.md"):
        for path in glob.glob(os.path.join(SKILL_DIR, ext)):
            basename = os.path.basename(path)
            skill_id = os.path.splitext(basename)[0]
            # Skip if already inside a subdirectory named after the skill
            parent_dir = os.path.basename(os.path.dirname(path))
            if parent_dir == skill_id:
                continue
            subdir = os.path.join(SKILL_DIR, skill_id)
            dest = os.path.join(subdir, basename)
            if os.path.exists(dest):
                # Destination already exists, remove the flat duplicate
                os.remove(path)
                continue
            os.makedirs(subdir, exist_ok=True)
            os.rename(path, dest)
            logger.info("Migrated skill: %s → %s", basename, dest)


def _seed_bundled_skills() -> None:
    """When frozen (PyInstaller), copy bundled .skills/ and .tools/ from
    sys._MEIPASS to get_data_dir() so they persist across runs."""
    if not getattr(sys, 'frozen', False):
        return
    meipass = sys._MEIPASS
    data_dir = get_data_dir()

    for subdir in ('.skills', '.tools'):
        src = os.path.join(meipass, subdir)
        dst = os.path.join(data_dir, subdir)
        if not os.path.isdir(src):
            continue
        if os.path.isdir(dst) and os.listdir(dst):
            continue  # already seeded
        import shutil
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if os.path.isdir(dst):
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        logger.info("Seeded bundled %s → %s (%d files)", subdir, dst, len(os.listdir(dst)))


def init_skills() -> None:
    """Ensure .skills/ exists and seed builtin skills if empty."""
    _seed_bundled_skills()
    _migrate_skills_to_subdirs()
    _seed_if_empty()
    _seed_function_skills()
    _clear_cache()


def _scan_dir(base: str, skills: list[dict]) -> None:
    """Scan a single directory for .md and .json skill/tool files."""
    if not os.path.isdir(base):
        return
    for path in sorted(glob.glob(os.path.join(base, "**/*"), recursive=True)):
        if os.path.isdir(path) or os.path.basename(path).lower() == "skill.md":
            continue
        ext = os.path.splitext(path)[1].lower()
        if ext not in (".md", ".json"):
            continue
        skill = _read_file(path)
        if skill is not None:
            skills.append(skill)


def list_skills() -> list[dict]:
    """Return all skills (.json + .md) from .skills/ and .tools/, sorted by (category, name)."""
    global _cache_skills
    if _cache_skills is not None:
        return _cache_skills
    skills = []
    _scan_dir(SKILL_DIR, skills)
    _scan_dir(TOOL_DIR, skills)
    skills.sort(key=lambda s: (s.get("category", ""), s.get("name", "")))
    _cache_skills = skills
    return skills


def toggle_skill(skill_id: str, enabled: bool) -> dict | None:
    path = _skill_path(skill_id)
    if not os.path.exists(path):
        return None
    skill = _read_file(path)
    if skill is None:
        return None
    skill["enabled"] = enabled
    _write_file(path, skill)
    _clear_cache()
    return skill


def remove_skill(skill_id: str) -> bool:
    path = _skill_path(skill_id)
    if not os.path.exists(path):
        return False
    os.remove(path)
    # Remove the skill subfolder from whichever directory it was in
    base_dir = os.path.dirname(os.path.dirname(path))
    skill_dir = os.path.join(base_dir, skill_id)
    if os.path.isdir(skill_dir):
        import shutil
        shutil.rmtree(skill_dir, ignore_errors=True)
    _clear_cache()
    return True


def get_enabled_tools() -> list[dict]:
    """Return enabled function-type skills as tool_definition dicts for the AI.

    Result is cached in _tool_cache and cleared when any skill is toggled/removed.
    """
    global _tool_cache
    if _tool_cache is not None:
        return _tool_cache
    all_skills = list_skills()
    tools = []
    for s in all_skills:
        if s.get("enabled") and s.get("tool_definition"):
            td = s["tool_definition"]
            tools.append(td)
    _tool_cache = tools
    return tools


def get_enabled_prompts() -> list[str]:
    """Return content of enabled prompt-type skills for system message injection."""
    all_skills = list_skills()
    return [s["content"] for s in all_skills if s.get("enabled") and s.get("type") == "prompt"]
