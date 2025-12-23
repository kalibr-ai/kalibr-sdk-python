"""
Capsule Reconstruction CLI Command
Fetch and export trace capsules from Kalibr Platform
"""

import json
import sys
from pathlib import Path
from typing import Optional

import requests
import typer
from rich import print as rprint
from rich.console import Console
from rich.table import Table

console = Console()


def capsule(
    trace_id: str = typer.Argument(..., help="Trace ID to reconstruct capsule for"),
    api_url: Optional[str] = typer.Option(
        None,
        "--api-url",
        "-u",
        help="Kalibr API base URL (default: from env KALIBR_API_URL or https://api.kalibr.systems)",
        envvar="KALIBR_API_URL",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file path (JSON format). If not specified, prints to stdout.",
    ),
    export: bool = typer.Option(
        False,
        "--export",
        "-e",
        help="Use export endpoint to download as file",
    ),
    pretty: bool = typer.Option(
        True,
        "--pretty/--no-pretty",
        "-p/-np",
        help="Pretty print JSON output",
    ),
):
    """
    Reconstruct and fetch a trace capsule by trace_id.

    The capsule contains all linked trace events, aggregated metrics,
    and metadata for a complete execution chain.

    Examples:

        # Fetch capsule and display in terminal
        kalibr capsule abc-123-def

        # Save capsule to file
        kalibr capsule abc-123-def --output capsule.json

        # Use export endpoint
        kalibr capsule abc-123-def --export --output capsule.json

        # Specify custom API URL
        kalibr capsule abc-123-def -u https://api.kalibr.systems
    """
    # Determine API base URL
    base_url = api_url or "https://api.kalibr.systems"
    base_url = base_url.rstrip("/")

    # Build endpoint URL
    if export:
        endpoint = f"{base_url}/api/capsule/{trace_id}/export"
    else:
        endpoint = f"{base_url}/api/capsule/{trace_id}"

    console.print(f"[cyan]Fetching capsule for trace_id:[/cyan] [bold]{trace_id}[/bold]")
    console.print(f"[dim]Endpoint: {endpoint}[/dim]")

    try:
        # Make API request
        response = requests.get(endpoint, timeout=30)
        response.raise_for_status()

        # Parse response
        capsule_data = response.json()

        # Display summary
        console.print("\n[green]✓ Capsule reconstructed successfully[/green]\n")

        # Create summary table
        table = Table(title="Capsule Summary", show_header=False)
        table.add_column("Field", style="cyan", no_wrap=True)
        table.add_column("Value", style="white")

        table.add_row("Capsule ID", capsule_data.get("capsule_id", "N/A"))
        table.add_row("Total Cost (USD)", f"${capsule_data.get('total_cost_usd', 0):.6f}")
        table.add_row("Total Latency (ms)", str(capsule_data.get("total_latency_ms", 0)))
        table.add_row("Hop Count", str(capsule_data.get("hop_count", 0)))
        table.add_row("Providers", ", ".join(capsule_data.get("providers", [])))
        table.add_row("Reconstructed At", capsule_data.get("reconstructed_at", "N/A"))

        console.print(table)

        # Output to file or stdout
        if output:
            output_path = Path(output)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, "w") as f:
                if pretty:
                    json.dump(capsule_data, f, indent=2, sort_keys=True)
                else:
                    json.dump(capsule_data, f)

            console.print(f"\n[green]✓ Capsule saved to:[/green] {output_path}")
        else:
            # Print to stdout
            console.print("\n[bold]Capsule Data:[/bold]")
            if pretty:
                rprint(json.dumps(capsule_data, indent=2, sort_keys=True))
            else:
                print(json.dumps(capsule_data))

        # Display event details
        events = capsule_data.get("events", [])
        if events:
            console.print(f"\n[bold]Events ({len(events)}):[/bold]")
            event_table = Table()
            event_table.add_column("Trace ID", style="cyan")
            event_table.add_column("Provider", style="yellow")
            event_table.add_column("Model", style="magenta")
            event_table.add_column("Operation", style="blue")
            event_table.add_column("Duration (ms)", justify="right", style="green")
            event_table.add_column("Cost (USD)", justify="right", style="green")
            event_table.add_column("Status", style="white")

            for event in events:
                event_table.add_row(
                    event.get("trace_id", "")[:12] + "...",
                    event.get("provider", "N/A"),
                    event.get("model_id", "N/A")[:20],
                    event.get("operation", "N/A"),
                    str(event.get("duration_ms", 0)),
                    f"${event.get('cost_usd', 0):.6f}",
                    event.get("status", "N/A"),
                )

            console.print(event_table)

        return 0

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            console.print(f"[red]✗ Capsule not found for trace_id: {trace_id}[/red]")
            console.print("[yellow]Make sure the trace_id exists and has been ingested.[/yellow]")
        else:
            console.print(f"[red]✗ API Error ({e.response.status_code}):[/red] {e.response.text}")
        return 1

    except requests.exceptions.ConnectionError:
        console.print(f"[red]✗ Connection Error:[/red] Unable to connect to {base_url}")
        console.print("[yellow]Make sure the Kalibr backend is running and accessible.[/yellow]")
        return 1

    except requests.exceptions.Timeout:
        console.print("[red]✗ Timeout:[/red] Request took too long to complete")
        return 1

    except Exception as e:
        console.print(f"[red]✗ Unexpected Error:[/red] {str(e)}")
        console.print("[yellow]Run with --help for usage information[/yellow]")
        return 1
