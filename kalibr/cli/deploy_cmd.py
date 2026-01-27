import os
import shutil
import subprocess
from pathlib import Path

import typer
from rich.console import Console

console = Console()
app = typer.Typer(no_args_is_help=True)


# ────────────────────────────────────────────────────────────────────────────────
# Utility: Ensure Flyctl CLI exists
# ────────────────────────────────────────────────────────────────────────────────
def _ensure_flyctl():
    """Check that Flyctl CLI is installed and in PATH."""
    os.environ["PATH"] += os.pathsep + os.path.expanduser("~/.fly/bin")
    fly_path = shutil.which("flyctl") or shutil.which("fly")
    if not fly_path:
        console.print(
            "❌ [red]Flyctl CLI not found. Install it from https://fly.io/docs/hands-on/install-flyctl/[/red]"
        )
        raise typer.Exit(code=1)
    return fly_path


# ────────────────────────────────────────────────────────────────────────────────
# Main deploy command
# ────────────────────────────────────────────────────────────────────────────────
@app.command()
def deploy(
    file_path: str = typer.Argument(..., help="Path to your Python app file."),
    runtime: str = typer.Option("fly", "--runtime", help="Runtime target (fly, render, or local)."),
    app_name: str = typer.Option("kalibr-app", "--app-name", help="Name of the Fly.io app."),
):
    """
    Deploy a Kalibr app to Fly.io or local runtime.
    """
    console.print(
        f"[bold cyan]─────────────────────────── Deploying {file_path} ───────────────────────────[/bold cyan]"
    )

    # Verify file exists
    app_path = Path(file_path).resolve()
    if not app_path.exists():
        console.print(f"❌ [red]File not found: {app_path}[/red]")
        raise typer.Exit(code=1)

    # ── Dockerfile ──────────────────────────────────────────────────────────────
    dockerfile_path = app_path.parent / "Dockerfile"
    if not dockerfile_path.exists():
        console.print("🧱 Generating Dockerfile ...")
        dockerfile_path.write_text(
            f"""FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install kalibr fastapi uvicorn
CMD ["kalibr", "serve", "{app_path.name}"]
"""
        )
        console.print(f"✅ Created [green]{dockerfile_path}[/green]")

    # ── fly.toml ────────────────────────────────────────────────────────────────
    fly_toml_path = app_path.parent / "fly.toml"
    fly_toml_contents = f"""
app = "{app_name}"
primary_region = "iad"

[build]
  image = "python:3.11"

[env]
  PORT = "8000"

[[services]]
  internal_port = 8000
  protocol = "tcp"

  [[services.ports]]
    port = 80
    handlers = ["http"]

  [[services.ports]]
    port = 443
    handlers = ["tls", "http"]
""".strip()

    fly_toml_path.write_text(fly_toml_contents)
    console.print(
        f"✅ Ensured [green]{fly_toml_path}[/green] includes app name: [bold]{app_name}[/bold]"
    )

    # ── Deploy ─────────────────────────────────────────────────────────────────
    fly_path = _ensure_flyctl()
    console.print(f"🚀 Deploying to Fly.io using [green]{fly_path}[/green]...")

    try:
        subprocess.run(["flyctl", "deploy", "--config", str(fly_toml_path)], check=True)
        console.print(f"✅ [bold green]Deployment complete![/bold green]")
        console.print(f"🌍 Visit your app at [underline]https://{app_name}.fly.dev[/underline]")
    except subprocess.CalledProcessError:
        console.print(f"❌ [red]Fly.io deployment failed[/red]")


# ────────────────────────────────────────────────────────────────────────────────
# Expose CLI entrypoint
# ────────────────────────────────────────────────────────────────────────────────
def get_app():
    return app


# Keep compatibility for `from kalibr.cli.deploy_cmd import deploy`
deploy = deploy
