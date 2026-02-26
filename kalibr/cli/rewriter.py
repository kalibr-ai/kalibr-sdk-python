"""Applies Router replacements to source files."""

import os
import re
from pathlib import Path

from kalibr.cli.scanner import LLMCallMatch


def _build_router_replacement(match: LLMCallMatch) -> str:
    """Build the Router replacement code for a detected LLM call."""
    goal = match.inferred_goal
    indent = re.match(r"(\s*)", match.matched_text).group(1)

    if match.pattern_type == "openai":
        return (
            f'{indent}from kalibr import Router\n'
            f'{indent}router = Router(goal="{goal}")\n'
            f'{indent}response = router.completion(messages=messages)'
        )
    elif match.pattern_type == "anthropic":
        return (
            f'{indent}from kalibr import Router\n'
            f'{indent}router = Router(goal="{goal}")\n'
            f'{indent}response = router.completion(messages=messages)'
        )
    elif match.pattern_type == "langchain":
        return (
            f'{indent}from kalibr import Router\n'
            f'{indent}router = Router(goal="{goal}")\n'
            f'{indent}response = router.completion(messages=messages)'
        )
    elif match.pattern_type == "crewai":
        return (
            f'{indent}from kalibr import Router\n'
            f'{indent}router = Router(goal="{goal}")\n'
            f'{indent}# Use router instead of hardcoded llm= in Agent()\n'
            f'{indent}# agent = Agent(llm=router.as_langchain(), ...)'
        )
    elif match.pattern_type == "openai_agents":
        return (
            f'{indent}from kalibr import Router\n'
            f'{indent}router = Router(goal="{goal}")\n'
            f'{indent}# Use router.completion() instead of Runner.run()'
        )
    else:
        return (
            f'{indent}from kalibr import Router\n'
            f'{indent}router = Router(goal="{goal}")\n'
            f'{indent}response = router.completion(messages=messages)'
        )


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

        # The match line_number is 1-indexed
        line_idx = match.line_number - 1
        if line_idx >= len(lines):
            return False

        original_line = lines[line_idx]
        replacement = _build_router_replacement(match)

        # Replace the matched line with the Router code
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
    # Check pyproject.toml first
    pyproject_path = os.path.join(project_dir, "pyproject.toml")
    if os.path.exists(pyproject_path):
        with open(pyproject_path, encoding="utf-8") as f:
            content = f.read()
        if "kalibr" not in content:
            # Find dependencies section and add kalibr
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

    # Fall back to requirements.txt
    req_path = os.path.join(project_dir, "requirements.txt")
    if os.path.exists(req_path):
        with open(req_path, encoding="utf-8") as f:
            content = f.read()
        if "kalibr" not in content:
            with open(req_path, "a", encoding="utf-8") as f:
                f.write("\nkalibr\n")
            return True
        return False

    # Create requirements.txt if neither exists
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
