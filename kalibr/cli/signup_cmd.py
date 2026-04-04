"""kalibr signup - Create a Kalibr account from the CLI (agent-driven onboarding)."""

import os

import requests
import typer
from rich.console import Console

console = Console()
BACKEND_URL = os.environ.get("KALIBR_BACKEND_URL", "https://kalibr-backend.fly.dev")


def signup(
    email: str = typer.Argument(..., help="Real email address for the account owner — credentials are returned immediately and a claim link is sent to this address"),
    agent_name: str = typer.Option("kalibr-agent", "--agent-name", help="Name for this agent (for identification in the dashboard)"),
    org_name: str = typer.Option(None, "--org", help="(unused, kept for backward compat)"),
) -> None:
    """Create a Kalibr account and get API credentials immediately. Recommended for agent-driven onboarding."""

    console.print(f"[bold]Creating Kalibr account for {email}...[/bold]")

    try:
        resp = requests.post(
            f"{BACKEND_URL}/api/cli-auth/signup-and-provision",
            json={"human_email": email, "agent_name": agent_name},
            timeout=20,
        )

        if resp.status_code == 409:
            console.print("[yellow]Account already exists for this email.[/yellow]")
            console.print("[yellow]Visit dashboard.kalibr.systems/sign-in or set KALIBR_API_KEY manually.[/yellow]")
            raise typer.Exit(1)

        if resp.status_code == 429:
            console.print("[red]Too many signup attempts. Try again in an hour.[/red]")
            raise typer.Exit(1)

        if resp.status_code != 200:
            console.print(f"[red]Signup failed (HTTP {resp.status_code}): {resp.text[:200]}[/red]")
            raise typer.Exit(1)

        data = resp.json()

    except requests.RequestException as e:
        console.print(f"[red]Signup failed: {e}[/red]")
        raise typer.Exit(1)

    api_key = data["api_key"]
    tenant_id = data["tenant_id"]
    claim_url = data.get("claim_url")

    # Write to .env
    env_path = os.path.join(os.getcwd(), ".env")
    lines = []
    if os.path.exists(env_path):
        with open(env_path) as f:
            lines = f.readlines()

    key_map = {
        "KALIBR_API_KEY": api_key,
        "KALIBR_TENANT_ID": tenant_id,
    }
    updated = set()
    new_lines = []
    for line in lines:
        replaced = False
        for k, v in key_map.items():
            if line.startswith(f"{k}="):
                new_lines.append(f"{k}={v}\n")
                updated.add(k)
                replaced = True
                break
        if not replaced:
            new_lines.append(line)

    for k, v in key_map.items():
        if k not in updated:
            new_lines.append(f"{k}={v}\n")

    with open(env_path, "w") as f:
        f.writelines(new_lines)

    console.print("\n[bold green]✓ Account created![/bold green]")
    console.print(f"  API Key:   {api_key[:12]}...")
    console.print(f"  Tenant ID: {tenant_id}")
    console.print(f"  Saved to:  {env_path}")
    if claim_url:
        console.print(f"\n[cyan]Dashboard access:[/cyan] {claim_url}")
        console.print("[dim]Share this link with the account owner to claim the dashboard.[/dim]")
    console.print("\n[bold]Next: run kalibr verify to confirm routing is live[/bold]")
