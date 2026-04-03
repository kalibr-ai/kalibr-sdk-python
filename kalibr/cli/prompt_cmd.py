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

2. kalibr auth --agent --email <ASK_USER_FOR_EMAIL>
   Ask the user: "What email should I use to provision your Kalibr account?"
   Then run: kalibr auth --agent --email <that_email>

3. Source credentials into shell:
   - If ~/.zshrc exists: append KALIBR_API_KEY and KALIBR_TENANT_ID exports
   - Else if ~/.bashrc exists: append to ~/.bashrc
   - Run: source ~/.zshrc (or ~/.bashrc)

4. openclaw plugin install kalibr && openclaw plugin configure kalibr

5. Create ~/clawd workspace scaffold:
   - ~/clawd/SOUL.md — ask the user: "What does your agent do in one sentence?"
     Write: # SOUL.md\\n\\n<their answer>
   - ~/clawd/USER.md — ask: "What is your role and timezone?"
     Write: # USER.md\\n\\nRole: <role>\\nTimezone: <timezone>
   - ~/clawd/HEARTBEAT.md — write a minimal heartbeat file:
     # HEARTBEAT.md\\n\\nLast checked: <current datetime>\\nStatus: active
   - ~/clawd/AGENTS.md — write a routing table:
     # AGENTS.md\\n\\n## Routing Table\\n\\n| Task Type | Load | Route |\\n|-----------|------|-------|\\n| code_generation / code_review / system_design | high | Sonnet → GPT-4o |\\n| research / outreach_generation | medium | Llama → DeepSeek |\\n| web_scraping / classification / summarization / data_pipeline | low | DeepSeek → Llama |

6. Create ~/clawd/kalibr-integration/ directory and download pipeline files:
   - https://raw.githubusercontent.com/kalibr-ai/kalibr-sdk-python/main/examples/kalibr_pipeline.py
   - https://raw.githubusercontent.com/kalibr-ai/kalibr-sdk-python/main/examples/kalibr_taxonomy.py
   - https://raw.githubusercontent.com/kalibr-ai/kalibr-sdk-python/main/examples/kalibr_eval.py
   - Create an empty ~/clawd/kalibr-integration/__init__.py

7. kalibr init && kalibr verify

8. Smoke test — run in Python:
   from kalibr_integration.kalibr_pipeline import classify_and_route
   result = classify_and_route("Summarize this document")
   print(result)

9. Report done:
   - Print: "✅ Kalibr + OpenClaw setup complete."
   - Print: "Dashboard: https://dashboard.kalibr.systems"
   - Print the claim email confirmation URL returned by `kalibr auth --agent`
   - Ask: "Do you have any provider API keys to add? (OPENAI_API_KEY, ANTHROPIC_API_KEY, DEEPSEEK_API_KEY, HF_TOKEN)"
     If yes, append them to ~/.zshrc and source it.
"""


def prompt(
    openclaw: bool = typer.Option(
        False,
        "--openclaw",
        help="Output the full autonomous OpenClaw / Hermes agent onboarding prompt.",
    ),
) -> None:
    """Output a ready-to-paste Claude Code / Cursor integration prompt.

    With --openclaw: outputs the full autonomous onboarding sequence for
    OpenClaw / Hermes agent orchestrators. Zero human steps after pasting.
    """
    text = OPENCLAW_PROMPT_TEXT if openclaw else PROMPT_TEXT

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
