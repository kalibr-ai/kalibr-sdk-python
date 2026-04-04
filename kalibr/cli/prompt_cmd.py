"""kalibr prompt - Output a ready-to-paste integration prompt."""

import subprocess
from typing import Optional

import typer
from rich.console import Console

console = Console()

PROMPT_TEXT = (
    "Read https://kalibr.systems/llms.txt for an overview of Kalibr, "
    "then read https://kalibr.systems/setup.txt for the complete setup reference. "
    "Integrate Kalibr outcome-aware routing into my project using the Router pattern. "
    "Set KALIBR_API_KEY and KALIBR_TENANT_ID from dashboard.kalibr.systems/settings."
)

OPENCLAW_PROMPT_TEXT = """\
Read https://kalibr.systems/llms.txt then https://kalibr.systems/setup.txt

Then run autonomously — zero human steps:

1. pip install kalibr huggingface_hub

2. kalibr signup <YOUR_EMAIL>
   (Creates your Kalibr account. Credentials saved to .env immediately.)

3. Source credentials into shell:
   export $(grep -v '^#' .env | xargs)
   To persist across sessions, append to ~/.zshrc:
     grep 'KALIBR_API_KEY\\|KALIBR_TENANT_ID' .env >> ~/.zshrc
     source ~/.zshrc

4. openclaw plugins install @kalibr/openclaw
   openclaw config set plugins.entries.kalibr.config.apiKey "$KALIBR_API_KEY"
   openclaw config set plugins.entries.kalibr.config.tenantId "$KALIBR_TENANT_ID"
   openclaw config set plugins.entries.kalibr.config.enableRouting true
   openclaw gateway restart

5. Create ~/clawd workspace scaffold:
   - ~/clawd/SOUL.md — ask the user: "What does your agent do in one sentence?"
     Write: # SOUL.md\\n\\n<their answer>
   - ~/clawd/USER.md — ask: "What is your role and timezone?"
     Write: # USER.md\\n\\nRole: <role>\\nTimezone: <timezone>
   - ~/clawd/HEARTBEAT.md — write a minimal heartbeat file:
     # HEARTBEAT.md\\n\\nLast checked: <current datetime>\\nStatus: active
   - ~/clawd/AGENTS.md — write a routing table:
     # AGENTS.md\\n\\n## Routing Table\\n\\n| Task Type | Load | Route |\\n|-----------|------|-------|\\n| code_generation / code_review / system_design | high | Sonnet → GPT-4o |\\n| research / outreach_generation | medium | Llama → DeepSeek |\\n| web_scraping / classification / summarization / data_pipeline | low | DeepSeek → Llama |

6. Create ~/clawd/kalibr-integration/ directory and write these files:

   Create ~/clawd/kalibr-integration/__init__.py (empty file)

   Create ~/clawd/kalibr-integration/kalibr_pipeline.py with this content:
   """
OPENCLAW_PIPELINE_FILE = '''"""Kalibr pipeline integration — classify and route tasks."""
import os
from kalibr import Router


def classify_and_route(task: str, context: dict = None) -> dict:
    """Classify a task and route it through Kalibr."""
    goal_id = classify_task(task)
    router = Router(goal=goal_id, paths=get_paths_for_goal(goal_id))
    result = router.completion(messages=[{"role": "user", "content": task}])
    return {"goal": goal_id, "result": result.choices[0].message.content}


def classify_task(task: str) -> str:
    """Classify a task string to a Kalibr goal_id."""
    t = task.lower()
    if any(w in t for w in ["scrape", "extract from url", "fetch page"]): return "web_scraping"
    if any(w in t for w in ["enrich", "fill in", "lookup missing"]): return "data_enrichment"
    if any(w in t for w in ["score lead", "lead score", "rate prospect"]): return "lead_scoring"
    if any(w in t for w in ["classify", "categorize", "label"]): return "classification"
    if any(w in t for w in ["summarize", "summary", "tldr"]): return "summarization"
    if any(w in t for w in ["pipeline", "transform data", "process rows"]): return "data_pipeline"
    if any(w in t for w in ["research", "investigate", "analyze market"]): return "research"
    if any(w in t for w in ["draft email", "cold email", "outreach", "write message"]): return "outreach_generation"
    if any(w in t for w in ["write code", "implement", "build function", "create script"]): return "code_generation"
    if any(w in t for w in ["review code", "code review", "check this code"]): return "code_review"
    if any(w in t for w in ["design system", "architecture", "system design"]): return "system_design"
    return "research"


def get_paths_for_goal(goal_id: str) -> list:
    """Return default model paths for a goal_id."""
    paths = {
        "web_scraping": ["deepseek-chat", "meta-llama/Llama-3.3-70B-Instruct", "mistralai/Mixtral-8x7B-Instruct-v0.1", "gpt-4o-mini"],
        "data_enrichment": ["deepseek-chat", "meta-llama/Llama-3.3-70B-Instruct", "Qwen/Qwen2.5-72B-Instruct", "gpt-4o-mini"],
        "lead_scoring": ["deepseek-chat", "meta-llama/Llama-3.3-70B-Instruct", "mistralai/Mixtral-8x7B-Instruct-v0.1", "gpt-4o-mini"],
        "classification": ["deepseek-chat", "meta-llama/Llama-3.3-70B-Instruct", "Qwen/Qwen2.5-72B-Instruct", "gpt-4o-mini"],
        "summarization": ["deepseek-chat", "meta-llama/Llama-3.3-70B-Instruct", "mistralai/Mixtral-8x7B-Instruct-v0.1", "claude-haiku-3-5-20241022"],
        "data_pipeline": ["deepseek-chat", "meta-llama/Llama-3.3-70B-Instruct", "Qwen/Qwen2.5-72B-Instruct", "gpt-4o-mini"],
        "research": ["meta-llama/Llama-3.3-70B-Instruct", "deepseek-chat", "deepseek-reasoner", "claude-sonnet-4-20250514"],
        "outreach_generation": ["meta-llama/Llama-3.3-70B-Instruct", "deepseek-chat", "mistralai/Mixtral-8x22B-Instruct-v0.1", "claude-sonnet-4-20250514"],
        "code_generation": ["claude-sonnet-4-20250514", "gpt-4o", "o3-mini", "deepseek-reasoner"],
        "code_review": ["claude-sonnet-4-20250514", "gpt-4o", "deepseek-reasoner", "o3-mini"],
        "system_design": ["claude-sonnet-4-20250514", "deepseek-reasoner", "gpt-4o", "o3-mini"],
        "agent_orchestration": ["claude-sonnet-4-20250514", "gpt-4o", "deepseek-reasoner", "o3-mini"],
    }
    return paths.get(goal_id, paths["research"])
'''

OPENCLAW_PROMPT_TEXT_PART2 = """\

7. kalibr init && kalibr verify

8. Smoke test — run in Python:
   from kalibr_integration.kalibr_pipeline import classify_and_route
   result = classify_and_route("Summarize this document")
   print(result)

9. Report done:
   - Print: "✅ Kalibr + OpenClaw setup complete."
   - Print: "Dashboard: https://dashboard.kalibr.systems"
   - Print the claim_url returned by kalibr signup (the human uses it to access the dashboard)
   - Ask: "Do you have any provider API keys to add? (OPENAI_API_KEY, ANTHROPIC_API_KEY, DEEPSEEK_API_KEY, HF_TOKEN)"
     If yes, append them to ~/.zshrc and source it.
"""

OPENCLAW_FULL_PROMPT = (
    OPENCLAW_PROMPT_TEXT
    + OPENCLAW_PIPELINE_FILE
    + OPENCLAW_PROMPT_TEXT_PART2
)


def prompt(
    openclaw: bool = typer.Option(
        False,
        "--openclaw",
        help="Output the full autonomous OpenClaw / Hermes agent onboarding prompt.",
    ),
    email: Optional[str] = typer.Option(
        None,
        "--email",
        help="Pre-fill user email for OpenClaw onboarding (avoids prompting). Example: kalibr prompt --openclaw --email user@example.com",
    ),
) -> None:
    """Output a ready-to-paste Claude Code / Cursor integration prompt.

    With --openclaw: outputs the full autonomous onboarding sequence for
    OpenClaw / Hermes agent orchestrators. Zero human steps after pasting.
    """
    if openclaw:
        if email:
            text = OPENCLAW_FULL_PROMPT.replace(
                "kalibr signup <YOUR_EMAIL>",
                f"kalibr signup {email}",
            )
        else:
            text = OPENCLAW_FULL_PROMPT
    else:
        text = PROMPT_TEXT

    console.print(text)
    console.print()

    # Try to copy to clipboard
    copied = False
    clipboard_commands = [
        ["pbcopy"],                                  # macOS
        ["xclip", "-selection", "clipboard"],        # Linux (X11)
        ["xsel", "--clipboard", "--input"],          # Linux (X11 alt)
        ["wl-copy"],                                 # Linux (Wayland)
    ]

    for cmd in clipboard_commands:
        try:
            proc = subprocess.run(
                cmd,
                input=text,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if proc.returncode == 0:
                copied = True
                break
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue

    if openclaw:
        label = "OpenClaw / Hermes agent"
    else:
        label = "Claude Code or Cursor"

    if copied:
        console.print(
            f"[green]Prompt copied to clipboard. Paste into {label}.[/green]"
        )
    else:
        console.print(
            f"[yellow]Could not copy to clipboard. Copy the text above and paste into {label}.[/yellow]"
        )
