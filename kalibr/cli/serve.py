"""Serve command for local development"""

import importlib.util
from pathlib import Path

import typer
from rich.console import Console

console = Console()


def serve(
    file_path: str = typer.Argument(..., help="Path to your Kalibr app (e.g. app.py)"),
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="Host to bind to"),
    port: int = typer.Option(8000, "--port", "-p", help="Port to bind to"),
):
    """Serve a Kalibr-powered API locally."""
    path = Path(file_path)

    if not path.exists():
        console.print(f"[red]❌ Error: File '{file_path}' not found[/red]")
        raise typer.Exit(1)

    try:
        # Load the module
        spec = importlib.util.spec_from_file_location("user_app", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Find Kalibr app instance
        app_instance = None
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if hasattr(attr, "app") and hasattr(attr.app, "openapi"):
                app_instance = attr
                break

        if not app_instance:
            console.print(f"[red]❌ Error loading {file_path}: No Kalibr app found[/red]")
            raise typer.Exit(1)

        # Display startup info
        console.print(f"[bold green]🚀 Starting Kalibr server from {path.name}[/bold green]")
        display_host = "localhost" if host == "0.0.0.0" else host
        console.print(f"📍 GPT (OpenAPI):     http://{display_host}:{port}/openapi.json")
        console.print(f"📍 Claude (MCP):      http://{display_host}:{port}/mcp.json")
        console.print(f"📍 Swagger UI:        http://{display_host}:{port}/docs")
        console.print(
            f"🔌 Actions registered: {[action['name'] for action in app_instance.actions]}"
        )

        # Run the server
        import uvicorn

        uvicorn.run(app_instance.app, host=host, port=port)

    except Exception as e:
        console.print(f"[red]❌ Error loading {file_path}: {str(e)}[/red]")
        raise typer.Exit(1)
