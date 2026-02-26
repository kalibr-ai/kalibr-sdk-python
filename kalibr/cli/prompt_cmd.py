"""kalibr prompt - Output a ready-to-paste integration prompt."""

import subprocess

from rich.console import Console

console = Console()

PROMPT_TEXT = (
    "Read https://kalibr.systems/llms.txt for an overview of Kalibr, "
    "then read https://kalibr.systems/setup.txt for the complete setup reference. "
    "Integrate Kalibr outcome-aware routing into my project using the Router pattern. "
    "Set KALIBR_API_KEY and KALIBR_TENANT_ID from dashboard.kalibr.systems/settings."
)


def prompt() -> None:
    """Output a ready-to-paste Claude Code / Cursor prompt."""
    # Print to stdout
    console.print(PROMPT_TEXT)
    console.print()

    # Try to copy to clipboard
    copied = False
    clipboard_commands = [
        ["pbcopy"],          # macOS
        ["xclip", "-selection", "clipboard"],  # Linux (X11)
        ["xsel", "--clipboard", "--input"],    # Linux (X11 alt)
        ["wl-copy"],         # Linux (Wayland)
    ]

    for cmd in clipboard_commands:
        try:
            proc = subprocess.run(
                cmd,
                input=PROMPT_TEXT,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if proc.returncode == 0:
                copied = True
                break
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue

    if copied:
        console.print("[green]Prompt copied to clipboard. Paste into Claude Code or Cursor.[/green]")
    else:
        console.print("[yellow]Could not copy to clipboard. Copy the text above manually.[/yellow]")
