"""kalibr auth - Link this agent to a Kalibr account via device code flow."""

import os
import sys
import time
import webbrowser

import requests
import typer
from rich.console import Console

console = Console()
BACKEND_URL = os.environ.get("KALIBR_BACKEND_URL", "https://kalibr-backend.fly.dev")


def _write_env(api_key: str, tenant_id: str) -> str:
    """Write KALIBR_API_KEY and KALIBR_TENANT_ID to .env, returning the path."""
    env_path = os.path.join(os.getcwd(), ".env")
    lines = []
    if os.path.exists(env_path):
        with open(env_path) as f:
            lines = f.readlines()

    key_map = {
        "KALIBR_API_KEY": api_key,
        "KALIBR_TENANT_ID": tenant_id,
    }
    updated: set[str] = set()
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

    return env_path


def _agent_signup(email: str | None) -> None:
    """Handle --agent signup flow."""
    if not email:
        console.print("[red]Error: Agent signup requires --email <human_email>[/red]")
        console.print("  Your human's email address so they can claim the dashboard.")
        raise typer.Exit(1)

    try:
        resp = requests.post(
            f"{BACKEND_URL}/api/cli-auth/signup-and-provision",
            json={"agent_name": "kalibr-agent", "human_email": email},
            timeout=15,
        )
    except requests.RequestException as e:
        console.print(f"[red]Failed to connect: {e}[/red]")
        raise typer.Exit(1)

    if resp.status_code == 409:
        console.print(f"Account already exists for {email}. Visit dashboard.kalibr.systems/sign-in")
        raise typer.Exit(1)

    if resp.status_code != 200:
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text or f"HTTP {resp.status_code}"
        console.print(f"[red]Error: {detail}[/red]")
        raise typer.Exit(1)

    data = resp.json()
    api_key = data["api_key"]
    tenant_id = data["tenant_id"]

    _write_env(api_key, tenant_id)

    console.print(f"[bold green]✓ Account created. {email} will receive an email to access the dashboard.[/bold green]")
    console.print("  Next: run 'kalibr init' to instrument your code")


def auth(
    agent: bool = typer.Option(False, "--agent", help="Autonomous agent signup (skip device code flow)"),
    email: str = typer.Option(None, "--email", help="Human email for agent signup"),
) -> None:
    """Link this agent to your Kalibr account. Human enters a code in the browser."""

    if agent:
        _agent_signup(email)
        return

    # Step 1: Request device code
    try:
        resp = requests.post(
            f"{BACKEND_URL}/api/cli-auth/device-code",
            json={},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        console.print(f"[red]Failed to start auth: {e}[/red]")
        raise typer.Exit(1)

    device_code = data["device_code"]
    user_code = data["user_code"]
    verification_url = data["verification_url"]
    expires_in = data.get("expires_in", 900)
    poll_interval = data.get("poll_interval_seconds", 5)

    # Step 2: Display code and URL
    direct_url = f"{verification_url}?code={user_code}"

    console.print()
    console.print("[bold]Link this agent to your Kalibr account[/bold]")
    console.print()
    console.print(f"   Go to:     [cyan]{verification_url}[/cyan]")
    console.print(f"   Enter code: [bold yellow]{user_code}[/bold yellow]")
    console.print()
    console.print(f"   Or open directly: [dim]{direct_url}[/dim]")
    console.print()

    # Try to open browser
    try:
        webbrowser.open(direct_url)
        console.print("[dim]   (Opened in your browser)[/dim]")
    except Exception:
        pass

    # Step 3: Poll for approval
    start = time.time()

    with console.status("[bold cyan]Waiting for approval...") as spinner:
        while time.time() - start < expires_in:
            try:
                resp = requests.post(
                    f"{BACKEND_URL}/api/cli-auth/token",
                    json={"device_code": device_code},
                    timeout=10,
                )

                if resp.status_code == 200:
                    result = resp.json()

                    if result["status"] == "approved":
                        api_key = result["api_key"]
                        tenant_id = result["tenant_id"]

                        env_path = _write_env(api_key, tenant_id)

                        console.print()
                        console.print("[bold green]Agent linked![/bold green]")
                        console.print(f"  API Key:   {api_key[:12]}...")
                        console.print(f"  Tenant ID: {tenant_id}")
                        console.print(f"  Saved to:  {env_path}")
                        console.print()
                        console.print("[bold]Next: run 'kalibr init' to instrument your code[/bold]")
                        return

                    elif result["status"] == "expired":
                        console.print()
                        console.print("[red]Code expired. Run 'kalibr auth' again.[/red]")
                        raise typer.Exit(1)

                    # status == "pending" -- keep polling

            except requests.RequestException:
                pass  # Retry on network errors

            time.sleep(poll_interval)

    console.print()
    console.print("[red]Timed out waiting for approval (15 minutes).[/red]")
    console.print("[yellow]Run 'kalibr auth' to try again.[/yellow]")
    raise typer.Exit(1)
