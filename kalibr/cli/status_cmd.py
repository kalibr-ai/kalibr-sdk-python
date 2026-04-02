"""kalibr status - Show Kalibr SDK and service health."""

import os

import httpx
from rich.console import Console
from rich.rule import Rule

console = Console()


def _mask(value: str, visible: int = 10) -> str:
    """Mask a credential, showing only the first `visible` characters."""
    if len(value) <= visible:
        return value
    return value[:visible] + "..."


def _check_service(url: str, headers: dict) -> str:
    """
    Hit a /health endpoint and return a status string.
    Returns a Rich-formatted string.
    """
    try:
        r = httpx.get(url, headers=headers, timeout=8)
        if r.status_code == 200:
            data = r.json()
            parts = []
            # Collect sub-service statuses from common health response shapes
            for key in ("clickhouse", "redis", "database"):
                val = data.get(key) or data.get("services", {}).get(key)
                if val:
                    label = "connected" if str(val).lower() in ("ok", "connected", "healthy", "true") else str(val)
                    parts.append(f"{key}: {label}")
            detail = f" ({', '.join(parts)})" if parts else ""
            return f"[green]✓ healthy{detail}[/green]"
        else:
            return f"[red]✗ unhealthy (HTTP {r.status_code})[/red]"
    except httpx.TimeoutException:
        return "[red]✗ timed out[/red]"
    except Exception as e:
        return f"[red]✗ unreachable ({e})[/red]"


def status() -> None:
    """Show Kalibr SDK version, credentials, and live service health."""
    from kalibr import __version__

    api_key = os.environ.get("KALIBR_API_KEY", "")
    tenant_id = os.environ.get("KALIBR_TENANT_ID", "")
    base_url = os.environ.get("KALIBR_INTELLIGENCE_URL", "https://kalibr-intelligence.fly.dev")
    backend_url = "https://kalibr-backend.fly.dev"

    headers = {}
    if api_key:
        headers["X-API-Key"] = api_key
    if tenant_id:
        headers["X-Tenant-ID"] = tenant_id

    console.print()
    console.print("[bold]Kalibr Status[/bold]")
    console.print(Rule(style="dim"))

    # SDK version
    console.print(f"  [dim]SDK version:[/dim]     {__version__}")

    # Credentials
    if api_key:
        console.print(f"  [dim]API key:[/dim]         {_mask(api_key)}  [green]✓ set[/green]")
    else:
        console.print("  [dim]API key:[/dim]         [red]✗ not set[/red]  (export KALIBR_API_KEY=...)")

    if tenant_id:
        console.print(f"  [dim]Tenant ID:[/dim]       {_mask(tenant_id)}  [green]✓ set[/green]")
    else:
        console.print("  [dim]Tenant ID:[/dim]       [red]✗ not set[/red]  (export KALIBR_TENANT_ID=...)")

    # Service health
    console.print(f"  [dim]Intelligence:[/dim]   {_check_service(f'{base_url}/api/v1/intelligence/health', headers)}")
    console.print(f"  [dim]Backend:[/dim]        {_check_service(f'{backend_url}/api/health', headers)}")

    console.print(Rule(style="dim"))
    console.print()
