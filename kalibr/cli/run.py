"""
kalibr run - Managed runtime lifecycle for MCP servers
Phase 3E - CLI Command
"""

import atexit
import os
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Optional

import httpx
import typer
from rich.console import Console

console = Console()


def run(
    file_path: str = typer.Argument(..., help="Path to your Python agent file"),
    runtime: str = typer.Option(
        "local", "--runtime", "-r", help="Runtime provider (local, fly.io)"
    ),
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="Host to bind to (local only)"),
    port: int = typer.Option(8000, "--port", "-p", help="Port to bind to (local only)"),
    backend_url: Optional[str] = typer.Option(None, "--backend-url", help="Kalibr backend URL"),
):
    """
    Run a Kalibr agent with managed runtime lifecycle.

    Automatically:
    - Registers runtime in backend
    - Injects tracing middleware
    - Emits capsules on completion
    - Updates runtime status

    Examples:

        # Run locally
        kalibr run weather.py

        # Run on Fly.io
        kalibr run weather.py --runtime fly.io

        # Custom backend
        kalibr run weather.py --backend-url https://api.kalibr.systems
    """
    # Validate file exists
    agent_path = Path(file_path).resolve()
    if not agent_path.exists():
        console.print(f"[red]❌ Error: File '{file_path}' not found[/red]")
        raise typer.Exit(1)

    # Configure backend
    backend = backend_url or os.getenv("KALIBR_BACKEND_URL", "https://api.kalibr.systems")
    api_key = os.getenv("KALIBR_API_KEY")
    if not api_key:
        console.print("[yellow]⚠️  KALIBR_API_KEY not set. Set it for trace authentication.[/yellow]")
        api_key = ""

    # Generate runtime metadata
    runtime_id = str(uuid.uuid4())
    context_token = str(uuid.uuid4())
    agent_name = agent_path.stem

    console.print(f"[bold cyan]🚀 Starting Kalibr Runtime[/bold cyan]")
    console.print(f"[dim]Agent:[/dim] {agent_name}")
    console.print(f"[dim]Runtime ID:[/dim] {runtime_id}")
    console.print(f"[dim]Context Token:[/dim] {context_token}")
    console.print(f"[dim]Provider:[/dim] {runtime}")

    # Register runtime
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                f"{backend}/api/runtimes/register",
                json={
                    "runtime_id": runtime_id,
                    "agent_name": agent_name,
                    "runtime_provider": runtime,
                    "context_token": context_token,
                },
            )
            response.raise_for_status()
            console.print(f"[green]✓[/green] Runtime registered")
    except Exception as e:
        console.print(f"[yellow]⚠️ Failed to register runtime: {e}[/yellow]")
        console.print("[yellow]Continuing without backend registration...[/yellow]")

    # Setup environment variables
    env = os.environ.copy()
    env.update(
        {
            "KALIBR_RUNTIME_ID": runtime_id,
            "KALIBR_CONTEXT_TOKEN": context_token,
            "KALIBR_TRACE_ENABLED": "true",
            "KALIBR_COLLECTOR_URL": f"{backend}/api/ingest",
            "KALIBR_API_KEY": api_key,
            "KALIBR_BACKEND_URL": backend,
        }
    )

    # Store runtime metadata for cleanup
    runtime_metadata = {
        "runtime_id": runtime_id,
        "backend": backend,
        "api_key": api_key,
        "start_time": time.time(),
        "trace_count": 0,
    }

    # Register cleanup handler
    def cleanup_runtime():
        """Stop runtime and update backend"""
        try:
            duration = time.time() - runtime_metadata["start_time"]

            with httpx.Client(timeout=10.0) as client:
                client.patch(
                    f"{backend}/api/runtimes/{runtime_id}/stop",
                    json={
                        "total_traces": runtime_metadata.get("trace_count", 0),
                        "total_cost_usd": 0.0,  # Will be updated by capsule emission
                        "total_latency_ms": int(duration * 1000),
                    },
                    headers={"X-API-Key": api_key},
                )
            console.print(f"[green]✓[/green] Runtime stopped")
        except Exception as e:
            console.print(f"[yellow]⚠️ Failed to stop runtime: {e}[/yellow]")

    atexit.register(cleanup_runtime)

    # Launch based on runtime provider
    if runtime == "local":
        # Local subprocess execution
        console.print(f"\n[bold]Starting agent on {host}:{port}[/bold]")

        try:
            # Use kalibr serve to run the agent
            cmd = [
                sys.executable,
                "-m",
                "kalibr.cli.main",
                "serve",
                str(agent_path),
                "--host",
                host,
                "--port",
                str(port),
            ]

            process = subprocess.Popen(
                cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            # Stream output
            console.print("[dim]─" * 80 + "[/dim]")
            for line in process.stdout:
                print(line, end="")

            process.wait()

        except KeyboardInterrupt:
            console.print("\n[yellow]⚠️ Received interrupt, stopping runtime...[/yellow]")
            process.terminate()
            process.wait(timeout=5)
        except Exception as e:
            console.print(f"[red]❌ Runtime error: {e}[/red]")
            raise typer.Exit(1)

    elif runtime == "fly.io":
        # Fly.io deployment
        console.print(f"\n[bold]Deploying to Fly.io[/bold]")

        # Use existing deploy command
        from kalibr.cli.deploy_cmd import deploy

        deploy(
            file_path=str(agent_path),
            runtime="fly",
            app_name=f"kalibr-{agent_name}",
        )

        console.print(f"[green]✓[/green] Deployed to Fly.io")

    else:
        console.print(f"[red]❌ Unsupported runtime: {runtime}[/red]")
        console.print("[yellow]Supported runtimes: local, fly.io[/yellow]")
        raise typer.Exit(1)

    # Cleanup
    cleanup_runtime()
    console.print("\n[bold green]✓ Runtime completed[/bold green]")
