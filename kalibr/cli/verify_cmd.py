"""kalibr verify - Check that Kalibr is configured correctly."""

import os
import uuid

import httpx
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

    # Step 4: Live round-trip test
    if all_ok:
        console.print("Testing live connectivity...")

        base_url = os.environ.get("KALIBR_INTELLIGENCE_URL", "https://kalibr-intelligence.fly.dev")
        headers = {
            "X-API-Key": api_key,
            "X-Tenant-ID": tenant_id,
            "Content-Type": "application/json",
        }
        test_goal = f"__verify__{uuid.uuid4().hex[:8]}"
        path_id = None

        try:
            # Register a test path
            r1 = httpx.post(
                f"{base_url}/api/v1/routing/paths",
                json={"goal": test_goal, "model_id": "gpt-4o-mini", "risk_level": "low"},
                headers=headers,
                timeout=10,
            )
            if r1.status_code != 200:
                console.print(f"[red]✗ Intelligence service unreachable: {r1.status_code}[/red]")
                console.print("  Fix: Check that your API key and tenant ID are valid.")
                raise typer.Exit(1)
            path_id = r1.json().get("path_id")

            # Request a routing decision
            r2 = httpx.post(
                f"{base_url}/api/v1/routing/decide",
                json={"goal": test_goal, "task_risk_level": "low"},
                headers=headers,
                timeout=10,
            )
            if r2.status_code != 200:
                console.print(f"[red]✗ Routing decision failed: {r2.status_code}[/red]")
                raise typer.Exit(1)
            trace_id = r2.json().get("trace_id")

            # Report outcome
            r3 = httpx.post(
                f"{base_url}/api/v1/intelligence/report-outcome",
                json={"trace_id": trace_id, "goal": test_goal, "success": True},
                headers=headers,
                timeout=10,
            )
            if r3.status_code != 200:
                console.print(f"[red]✗ Outcome reporting failed: {r3.status_code}[/red]")
                raise typer.Exit(1)

            console.print("[green]✓ Live round-trip: register → decide → report → OK[/green]")

        except typer.Exit:
            all_ok = False
            raise
        except httpx.TimeoutException:
            console.print("[red]✗ Intelligence service timed out[/red]")
            console.print("  Check your network connection or try again in a moment.")
            all_ok = False
            raise typer.Exit(1)
        except Exception as e:
            console.print(f"[red]✗ Connectivity check failed: {e}[/red]")
            all_ok = False
            raise typer.Exit(1)
        finally:
            # Clean up: delete the test path regardless of outcome
            if path_id:
                try:
                    httpx.delete(
                        f"{base_url}/api/v1/routing/paths/{path_id}",
                        headers=headers,
                        timeout=5,
                    )
                except Exception:
                    pass  # Best-effort cleanup

    # Step 5: Check provider API keys (warning only)
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
