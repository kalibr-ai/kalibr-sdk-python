"""File scanning and pattern detection for bare LLM calls."""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class LLMCallMatch:
    """A detected bare LLM call in source code."""

    file_path: str
    line_number: int
    pattern_type: str  # openai, anthropic, langchain, crewai, openai_agents
    matched_text: str
    context_before: list[str] = field(default_factory=list)
    context_after: list[str] = field(default_factory=list)
    inferred_goal: str = "llm_task"


# Detection patterns: (regex, pattern_type, description)
DETECTION_PATTERNS = [
    (
        re.compile(r"""(?:^|[^\w.])(\w+)\.chat\.completions\.create\("""),
        "openai",
        "OpenAI chat completion",
    ),
    (
        re.compile(r"""(?:^|[^\w.])(\w+)\.messages\.create\("""),
        "anthropic",
        "Anthropic message",
    ),
    (
        re.compile(r"""(?:^|[^\w.])(\w+)\.invoke\("""),
        "langchain",
        "LangChain invoke",
    ),
    (
        re.compile(r"""Agent\([^)]*llm\s*="""),
        "crewai",
        "CrewAI Agent with hardcoded LLM",
    ),
    (
        re.compile(r"""Runner\.run\("""),
        "openai_agents",
        "OpenAI Agents SDK Runner",
    ),
]

# Directories and files to skip
SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    "node_modules",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "dist",
    "build",
    ".egg-info",
    ".tox",
}

SKIP_FILES = {
    "setup.py",
    "conftest.py",
}


def _infer_goal(file_path: str, line_number: int, lines: list[str]) -> str:
    """Infer a goal string from surrounding context."""
    # Check enclosing function name
    for i in range(line_number - 1, max(line_number - 30, -1), -1):
        if i < 0 or i >= len(lines):
            continue
        func_match = re.match(r"\s*(?:async\s+)?def\s+(\w+)\s*\(", lines[i])
        if func_match:
            name = func_match.group(1)
            # Skip generic names
            if name not in ("main", "__init__", "run", "execute", "call", "process"):
                return name

    # Check variable assignment on or near the match line
    target_line = lines[line_number] if line_number < len(lines) else ""
    var_match = re.match(r"\s*(\w+)\s*=", target_line)
    if var_match:
        name = var_match.group(1)
        if name not in ("result", "response", "output", "res", "resp", "client"):
            return name

    # Check comments above the match line
    for i in range(line_number - 1, max(line_number - 5, -1), -1):
        if i < 0 or i >= len(lines):
            continue
        comment_match = re.match(r"\s*#\s*(.+)", lines[i])
        if comment_match:
            comment = comment_match.group(1).strip().lower()
            # Extract a short goal from the comment
            words = re.findall(r"[a-z_]+", comment)
            if words:
                goal = "_".join(words[:3])
                if len(goal) > 2:
                    return goal

    return "llm_task"


def _is_langchain_invoke(lines: list[str], line_number: int) -> bool:
    """Check if an .invoke() call is likely a LangChain call (llm or chain)."""
    line = lines[line_number] if line_number < len(lines) else ""
    match = re.search(r"""(\w+)\.invoke\(""", line)
    if not match:
        return False
    var_name = match.group(1).lower()
    langchain_indicators = {"llm", "chain", "model", "chat", "prompt", "runnable", "pipe"}
    return any(indicator in var_name for indicator in langchain_indicators)


def scan_file(file_path: str) -> list[LLMCallMatch]:
    """Scan a single file for bare LLM calls."""
    matches = []
    try:
        with open(file_path, encoding="utf-8", errors="ignore") as f:
            content = f.read()
            lines = content.splitlines()
    except (OSError, UnicodeDecodeError):
        return []

    for line_idx, line in enumerate(lines):
        for pattern, pattern_type, _desc in DETECTION_PATTERNS:
            if pattern.search(line):
                # For langchain .invoke(), verify it's actually a chain/llm
                if pattern_type == "langchain" and not _is_langchain_invoke(lines, line_idx):
                    continue

                # Gather context lines
                start = max(0, line_idx - 1)
                end = min(len(lines), line_idx + 2)
                context_before = lines[start:line_idx]
                context_after = lines[line_idx + 1 : end]

                goal = _infer_goal(file_path, line_idx, lines)

                match = LLMCallMatch(
                    file_path=file_path,
                    line_number=line_idx + 1,  # 1-indexed
                    pattern_type=pattern_type,
                    matched_text=line.rstrip(),
                    context_before=context_before,
                    context_after=context_after,
                    inferred_goal=goal,
                )
                matches.append(match)
                break  # Only match one pattern per line

    return matches


def scan_directory(
    directory: str, file_extensions: Optional[set[str]] = None
) -> list[LLMCallMatch]:
    """Scan a directory recursively for bare LLM calls."""
    if file_extensions is None:
        file_extensions = {".py"}

    all_matches = []
    root_path = Path(directory)

    for dirpath, dirnames, filenames in os.walk(root_path):
        # Filter out directories to skip (modify in-place for os.walk)
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]

        rel_dir = Path(dirpath).relative_to(root_path)
        # Skip if any parent dir component starts with '.'
        if any(part.startswith(".") for part in rel_dir.parts):
            continue

        for filename in filenames:
            if filename in SKIP_FILES:
                continue
            if Path(filename).suffix not in file_extensions:
                continue

            file_path = os.path.join(dirpath, filename)
            matches = scan_file(file_path)
            all_matches.extend(matches)

    return all_matches
