"""Main CLI entry point for Kalibr"""

import typer
from kalibr.cli.capsule_cmd import capsule
from kalibr.cli.deploy_cmd import deploy
from kalibr.cli.run import run

# Import command functions
from kalibr.cli.serve import serve
from rich.console import Console

app = typer.Typer(
    name="kalibr",
    help="Kalibr SDK - Multi-Model AI Integration Framework",
    add_completion=False,
)

console = Console()

# Register commands directly
app.command(name="serve")(serve)
app.command(name="deploy")(deploy)
app.command(name="capsule")(capsule)
app.command(name="run")(run)


@app.command()
def version():
    """Show Kalibr SDK version"""
    from kalibr import __version__

    console.print(f"[bold]Kalibr SDK version:[/bold] {__version__}")
    console.print("LLM Observability & Execution Intelligence")
    console.print("Auto-instrumentation for OpenAI, Anthropic, Google AI")
    console.print("GitHub: https://github.com/kalibr-ai/kalibr-sdk-python")


@app.command()
def package():
    """Create a deployable MCP bundle (code + schemas + metadata)."""
    console.print("[yellow]📦 Package feature coming soon[/yellow]")
    console.print("This will create a deployment bundle with all schemas.")


@app.command()
def validate():
    """Validate MCP manifest against minimal JSON schema & version hint."""
    console.print("[yellow]✓ Validation feature coming soon[/yellow]")


@app.command()
def update_schemas():
    """Stub: instruct users to upgrade SDK and regenerate manifests."""
    console.print("[cyan]ℹ️  To update schemas:[/cyan]")
    console.print("1. pip install --upgrade kalibr")
    console.print("2. Restart your kalibr serve command")
    console.print("3. Schemas will be auto-regenerated")


@app.command()
def status():
    """Check status of a deployed Kalibr app."""
    console.print("[yellow]📊 Status checking coming soon[/yellow]")


if __name__ == "__main__":
    app()
