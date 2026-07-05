"""Security utilities — workspace scoping, command validation, safe execution."""

import re
import shlex
from pathlib import Path

# Workspace scope: restrict file operations to the project directory
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent.parent  # backend/
ALLOWED_WRITE_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx",
    ".html", ".css", ".json", ".md", ".txt",
    ".yaml", ".yml", ".toml", ".ini", ".cfg",
    ".sh", ".bat", ".ps1", ".sql", ".xml",
    ".env", ".gitignore",
}

DANGEROUS_COMMANDS = ["rm", "del", "rd", "format", "shutdown", "reboot"]
DANGEROUS_ARGS = [">", ">>", "|", "2>", "&"]
DANGEROUS_PATTERNS = [
    r"(^|\s)(rm|del|rd)(\s|$)",
    r"(^|\s)format(\s|$)",
    r"(^|\s)shutdown(\s|$)",
    r"(^|\s)reboot(\s|$)",
    r"(^|\s)dd(\s|$)",
    r"(^|\s)mkfs(\s|$)",
    r"(^|\s):(){ :|:& };:(\s|$)",
    r"(^|\s)wget\s+.*\||curl\s+.*\|",
]

_SHELL_METACHARS = re.compile(r'[|;&`$(){}<>]')


def in_workspace(path: Path) -> bool:
    """Check if a resolved path is within the workspace scope."""
    try:
        resolved = path.resolve()
        workspace = WORKSPACE_ROOT.resolve()
        agent_root = workspace.parent
        if workspace in resolved.parents or resolved == workspace:
            return True
        if agent_root in resolved.parents or resolved == agent_root:
            return True
        return False
    except Exception:
        return False


def safe_command_split(command: str) -> list[str] | None:
    """Split a command string into args, rejecting dangerous patterns. Returns None if blocked."""
    command_stripped = command.strip()
    if not command_stripped:
        return None

    # Check for dangerous commands
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, command_stripped, re.IGNORECASE):
            return None

    # Check for dangerous args in the raw string
    for arg in DANGEROUS_ARGS:
        if arg in command_stripped:
            return None

    # Reject shell metacharacters
    if _SHELL_METACHARS.search(command_stripped):
        return None

    try:
        return shlex.split(command_stripped)
    except ValueError:
        return None
