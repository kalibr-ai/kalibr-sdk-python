"""kalibr signup - Create a Kalibr account from the CLI."""

import os
import time

import requests
import typer
from rich.console import Console

console = Console()
BACKEND_URL = os.environ.get("KALIBR_BACKEND_URL", "https://kalibr-backend.fly.dev")


def signup(
    email: str = typer.Argument(..., help="Email address for your Kalibr account"),
    org_name: str = typer.Option(None, "--org", help="Organization name (default: email prefix)"),
) -> None:
    """Create a Kalibr account and get API credentials. Human clicks one email link."""

    console.print(f"[bold]Creating Kalibr account for {email}...[/bold]")

    # Start signup
    try:
        resp = requests.post(
            f"{BACKEND_URL}/api/cli-auth/signup",
            json={"email": email, "org_name": org_name},
            timeout=15,
        )

        if resp.status_code == 409:
            console.print("[yellow]Account already exists for this email.[/yellow]")
            console.print("[yellow]Visit dashboard.kalibr.systems/sign-in or set KALIBR_API_KEY manually.[/yellow]")
            raise typer.Exit(1)

        if resp.status_code == 429:
            console.print("[red]Too many signup attempts. Try again in an hour.[/red]")
            raise typer.Exit(1)

        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        console.print(f"[red]Signup failed: {e}[/red]")
        raise typer.Exit(1)

    signup_id = data["signup_id"]
    console.print(f"\n[green]✓ Verification email sent to {email}[/green]")
    console.print("[cyan]Click the link in your email to activate your account...[/cyan]\n")

    # Poll for verification
    poll_url = f"{BACKEND_URL}/api/cli-auth/signup/{signup_id}/status"
    max_wait = 300  # 5 minutes
    start = time.time()

    with console.status("[bold cyan]Waiting for email verification...") as spinner:
        while time.time() - start < max_wait:
            try:
                resp = requests.get(poll_url, timeout=10)
                if resp.status_code == 200:
                    result = resp.json()

                    if result["status"] == "verified":
                        api_key = result["api_key"]
                        tenant_id = result["tenant_id"]

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
                        console.print("\n[bold]Next: run 'kalibr init' to instrument your code[/bold]")
                        return

                    elif result["status"] == "expired":
                        console.print("\n[red]Signup expired. Please try again.[/red]")
                        raise typer.Exit(1)

            except requests.RequestException:
                pass  # Retry on network errors

            time.sleep(5)

    console.print("\n[red]Timed out waiting for email verification (5 minutes).[/red]")
    console.print("[yellow]Check your inbox and spam folder, then run 'kalibr signup' again.[/yellow]")
    raise typer.Exit(1)
