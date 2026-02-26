"""kalibr init - Scan for bare LLM calls and propose Router wrapping."""

import os

import requests
import typer
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax

from kalibr.cli.rewriter import (
    apply_change,
    ensure_env_example,
    ensure_kalibr_in_requirements,
    get_proposed_change,
)
from kalibr.cli.scanner import scan_directory

console = Console()


def _provision_credentials(project_dir: str) -> None:
    """Auto-provision credentials using KALIBR_PROVISIONING_TOKEN."""
    token = os.environ.get("KALIBR_PROVISIONING_TOKEN")
    if not token:
        return

    project_name = os.path.basename(os.path.abspath(project_dir))
    console.print("[cyan]Provisioning credentials...[/cyan]")

    try:
        resp = requests.post(
            "https://kalibr-intelligence.fly.dev/api/provisioning/provision",
            json={
                "provisioning_token": token,
                "name": project_name,
                "source": "kalibr-init",
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        api_key = data.get("api_key", "")
        tenant_id = data.get("tenant_id", "")

        if api_key and tenant_id:
            env_path = os.path.join(project_dir, ".env")
            lines = []
            if os.path.exists(env_path):
                with open(env_path, encoding="utf-8") as f:
                    lines = f.readlines()

            # Update or append keys
            key_set = {"KALIBR_API_KEY": api_key, "KALIBR_TENANT_ID": tenant_id}
            updated_keys = set()
            new_lines = []
            for line in lines:
                replaced = False
                for key, value in key_set.items():
                    if line.startswith(f"{key}="):
                        new_lines.append(f"{key}={value}\n")
                        updated_keys.add(key)
                        replaced = True
                        break
                if not replaced:
                    new_lines.append(line)

            for key, value in key_set.items():
                if key not in updated_keys:
                    new_lines.append(f"{key}={value}\n")

            with open(env_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)

            console.print("[green]Credentials provisioned automatically.[/green]")
        else:
            console.print("[yellow]Provisioning response missing credentials.[/yellow]")
    except requests.RequestException as e:
        console.print(f"[red]Provisioning failed: {e}[/red]")


def _check_credentials() -> None:
    """Check for credentials and print guidance if missing."""
    has_api_key = bool(os.environ.get("KALIBR_API_KEY"))
    has_provisioning = bool(os.environ.get("KALIBR_PROVISIONING_TOKEN"))

    if not has_api_key and not has_provisioning:
        console.print()
        console.print(
            "[yellow]No credentials found. "
            "Get your API key at dashboard.kalibr.systems/settings[/yellow]"
        )
        console.print(
            "[yellow]Or set KALIBR_PROVISIONING_TOKEN to provision "
            "credentials automatically.[/yellow]"
        )


def init(
    directory: str = typer.Argument(".", help="Directory to scan (default: current directory)"),
) -> None:
    """Scan for bare LLM calls and propose wrapping them with Kalibr Router."""
    project_dir = os.path.abspath(directory)

    if not os.path.isdir(project_dir):
        console.print(f"[red]Directory not found: {project_dir}[/red]")
        raise typer.Exit(1)

    console.print(f"[bold]Scanning {project_dir} for bare LLM calls...[/bold]")
    console.print()

    matches = scan_directory(project_dir)

    if not matches:
        console.print("[green]No bare LLM calls found. Your project is already clean.[/green]")
        _check_credentials()
        return

    console.print(f"Found [bold]{len(matches)}[/bold] bare LLM call(s):\n")

    files_modified = set()
    calls_upgraded = 0
    skip_all = False

    for match in matches:
        if skip_all:
            break

        rel_path = os.path.relpath(match.file_path, project_dir)

        # Show file + line number
        console.print(f"[bold cyan]{rel_path}:{match.line_number}[/bold cyan] ({match.pattern_type})")

        # Show current code with context
        current_lines = match.context_before + [match.matched_text] + match.context_after
        current_code = "\n".join(current_lines)
        console.print(Panel(
            Syntax(current_code, "python", theme="monokai", line_numbers=False),
            title="Current",
            border_style="red",
        ))

        # Show proposed replacement
        proposed = get_proposed_change(match)
        console.print(Panel(
            Syntax(proposed, "python", theme="monokai", line_numbers=False),
            title=f'Proposed (goal="{match.inferred_goal}")',
            border_style="green",
        ))

        # Ask for approval
        choice = typer.prompt(
            "Apply this change? [y/n/skip all]",
            default="y",
            show_default=False,
        )
        choice = choice.strip().lower()

        if choice == "skip all":
            skip_all = True
            console.print("[yellow]Skipping remaining changes.[/yellow]")
        elif choice == "y":
            if apply_change(match):
                files_modified.add(match.file_path)
                calls_upgraded += 1
                console.print("[green]Applied.[/green]")
            else:
                console.print("[red]Failed to apply change.[/red]")
        else:
            console.print("[dim]Skipped.[/dim]")

        console.print()

    # Post-apply steps
    if calls_upgraded > 0:
        ensure_kalibr_in_requirements(project_dir)
        ensure_env_example(project_dir)

    # Provision credentials if token is available
    if os.environ.get("KALIBR_PROVISIONING_TOKEN"):
        _provision_credentials(project_dir)

    # Summary
    console.print("[bold]Summary:[/bold]")
    console.print(f"  {len(files_modified)} file(s) modified, {calls_upgraded} LLM call(s) upgraded")

    _check_credentials()
