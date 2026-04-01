"""kalibr verify - Check that Kalibr is configured correctly."""

import os

import typer
from rich.console import Console

console = Console()


def verify() -> None:
    """Check that Kalibr is configured correctly."""
    all_ok = True

    # Step 1: Check KALIBR_API_KEY
    api_key = os.environ.get("KALIBR_API_KEY")
    if not api_key:
        console.print("[red]KALIBR_API_KEY is not set.[/red]")
        console.print("  Fix: export KALIBR_API_KEY=your-key")
        console.print("  Get your key at: https://dashboard.kalibr.systems/settings")
        all_ok = False
    else:
        console.print("[green]KALIBR_API_KEY is set.[/green]")

    # Step 2: Check KALIBR_TENANT_ID
    tenant_id = os.environ.get("KALIBR_TENANT_ID")
    if not tenant_id:
        console.print("[red]KALIBR_TENANT_ID is not set.[/red]")
        console.print("  Fix: export KALIBR_TENANT_ID=your-tenant-id")
        console.print("  Find it at: https://dashboard.kalibr.systems/settings")
        all_ok = False
    else:
        console.print("[green]KALIBR_TENANT_ID is set.[/green]")

    # Step 3: Attempt to instantiate Router with a test goal
    if all_ok:
        try:
            from kalibr import Router

            _router = Router(goal="kalibr_verify_test", auto_register=False)
            console.print("[green]Router instantiation succeeded.[/green]")
        except Exception as e:
            console.print(f"[red]Router instantiation failed: {e}[/red]")
            console.print("  Fix: Ensure your KALIBR_API_KEY and KALIBR_TENANT_ID are valid.")
            all_ok = False

    # Step 4: Check provider API keys (warning only)
    provider_keys = {
        "ANTHROPIC_API_KEY": "for claude-* models",
        "OPENAI_API_KEY": "for gpt-* and o1-*, o3-* models",
        "DEEPSEEK_API_KEY": "for deepseek-* models",
        "HF_TOKEN": "for HuggingFace models",
    }
    has_provider = any(os.environ.get(k) for k in provider_keys)
    if not has_provider:
        console.print()
        console.print("[yellow]⚠️  No provider API keys detected.[/yellow]")
        console.print("[yellow]     Router.completion() requires at least one:[/yellow]")
        for key, desc in provider_keys.items():
            console.print(f"[yellow]       {key:<20s} — {desc}[/yellow]")
        console.print("[yellow]     Export the key(s) for the models you plan to use.[/yellow]")

    # Final result
    if all_ok:
        console.print()
        console.print(
            "[bold green]Kalibr is configured correctly. "
            "Dashboard: https://dashboard.kalibr.systems[/bold green]"
        )
    else:
        console.print()
        console.print("[bold red]Kalibr configuration has issues. See errors above.[/bold red]")
        raise typer.Exit(1)
