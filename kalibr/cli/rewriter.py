"""Applies Router replacements to source files."""

import os
import re
from pathlib import Path

from kalibr.cli.scanner import LLMCallMatch, HF_TASK_DEFAULT_PATHS


# Default multi-provider paths for LLM completion calls.
# Always suggest at least two paths so Thompson Sampling has something to learn from.
# Model IDs must be valid — verified against router.py docstring and examples.
DEFAULT_LLM_PATHS = [
    '{"model": "gpt-4o-mini"}',
    '{"model": "claude-sonnet-4-20250514"}',
]


def _build_router_replacement(match: LLMCallMatch) -> str:
    """Build the Router replacement code for a detected LLM call."""
    goal = match.inferred_goal
    indent = re.match(r"(\s*)", match.matched_text).group(1)

    if match.pattern_type in ("huggingface", "huggingface_pipeline"):
        return _build_hf_replacement(match, indent, goal)

    return _build_completion_replacement(match, indent, goal)


def _build_completion_replacement(match: LLMCallMatch, indent: str, goal: str) -> str:
    """Router.completion() replacement for LLM chat/message calls."""
    paths_str = _format_paths(DEFAULT_LLM_PATHS, indent)

    if match.pattern_type == "crewai":
        return (
            f'{indent}import kalibr\n'
            f'{indent}from kalibr import Router\n'
            f'{indent}router = Router(\n'
            f'{indent}    goal="{goal}",\n'
            f'{indent}    paths=[\n'
            f'{paths_str}\n'
            f'{indent}    ],\n'
            f'{indent})\n'
            f'{indent}# Use router instead of hardcoded llm= in Agent()\n'
            f'{indent}# agent = Agent(llm=router.as_langchain(), ...)'
        )
    elif match.pattern_type == "openai_agents":
        return (
            f'{indent}import kalibr\n'
            f'{indent}from kalibr import Router\n'
            f'{indent}router = Router(\n'
            f'{indent}    goal="{goal}",\n'
            f'{indent}    paths=[\n'
            f'{paths_str}\n'
            f'{indent}    ],\n'
            f'{indent})\n'
            f'{indent}# Use router.completion() instead of Runner.run()'
        )
    else:
        return (
            f'{indent}import kalibr\n'
            f'{indent}from kalibr import Router\n'
            f'{indent}router = Router(\n'
            f'{indent}    goal="{goal}",\n'
            f'{indent}    paths=[\n'
            f'{paths_str}\n'
            f'{indent}    ],\n'
            f'{indent})\n'
            f'{indent}response = router.completion(messages=messages)'
        )


def _build_hf_replacement(match: LLMCallMatch, indent: str, goal: str) -> str:
    """Router.execute() replacement for HuggingFace task calls."""
    task = match.inferred_task or "text_generation"

    raw_paths = HF_TASK_DEFAULT_PATHS.get(task, [
        '{"model": "mistralai/Mixtral-8x7B-Instruct-v0.1"}',
        '{"model": "meta-llama/Meta-Llama-3-8B-Instruct"}',
    ])
    paths_str = _format_paths(raw_paths, indent)

    return (
        f'{indent}import kalibr\n'
        f'{indent}from kalibr import Router\n'
        f'{indent}router = Router(\n'
        f'{indent}    goal="{goal}",\n'
        f'{indent}    paths=[\n'
        f'{paths_str}\n'
        f'{indent}    ],\n'
        f'{indent})\n'
        f'{indent}response = router.execute(task="{task}", input_data=input_data)'
    )


def _format_paths(raw_paths: list[str], indent: str) -> str:
    """Format a list of path strings into indented Router paths= block."""
    return "\n".join(f"{indent}        {p}," for p in raw_paths)


def get_proposed_change(match: LLMCallMatch) -> str:
    """Get the proposed replacement for display purposes."""
    return _build_router_replacement(match)


def apply_change(match: LLMCallMatch) -> bool:
    """Apply a single Router replacement to a file.

    Returns True if the change was applied successfully.
    """
    try:
        with open(match.file_path, encoding="utf-8") as f:
            lines = f.readlines()

        line_idx = match.line_number - 1
        if line_idx >= len(lines):
            return False

        replacement = _build_router_replacement(match)
        lines[line_idx] = replacement + "\n"

        with open(match.file_path, "w", encoding="utf-8") as f:
            f.writelines(lines)

        return True
    except OSError:
        return False


def ensure_kalibr_in_requirements(project_dir: str) -> bool:
    """Add kalibr to requirements.txt or pyproject.toml if not present.

    Returns True if a change was made.
    """
    pyproject_path = os.path.join(project_dir, "pyproject.toml")
    if os.path.exists(pyproject_path):
        with open(pyproject_path, encoding="utf-8") as f:
            content = f.read()
        if "kalibr" not in content:
            if "dependencies" in content:
                content = re.sub(
                    r'(dependencies\s*=\s*\[)',
                    r'\1\n    "kalibr",',
                    content,
                    count=1,
                )
                with open(pyproject_path, "w", encoding="utf-8") as f:
                    f.write(content)
                return True
        return False

    req_path = os.path.join(project_dir, "requirements.txt")
    if os.path.exists(req_path):
        with open(req_path, encoding="utf-8") as f:
            content = f.read()
        if "kalibr" not in content:
            with open(req_path, "a", encoding="utf-8") as f:
                f.write("\nkalibr\n")
            return True
        return False

    with open(req_path, "w", encoding="utf-8") as f:
        f.write("kalibr\n")
    return True


def ensure_env_example(project_dir: str) -> bool:
    """Add KALIBR_API_KEY and KALIBR_TENANT_ID to .env.example if not present.

    Returns True if a change was made.
    """
    env_path = os.path.join(project_dir, ".env.example")
    changed = False

    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as f:
            content = f.read()
    else:
        content = ""

    additions = []
    if "KALIBR_API_KEY" not in content:
        additions.append("KALIBR_API_KEY=your-kalibr-api-key")
        changed = True
    if "KALIBR_TENANT_ID" not in content:
        additions.append("KALIBR_TENANT_ID=your-kalibr-tenant-id")
        changed = True

    if changed:
        separator = "\n" if content and not content.endswith("\n") else ""
        header = "\n# Kalibr Configuration\n" if additions else ""
        with open(env_path, "a" if content else "w", encoding="utf-8") as f:
            f.write(separator + header + "\n".join(additions) + "\n")

    return changed
