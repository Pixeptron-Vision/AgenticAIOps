"""
CLI application for LLMOps Agent.

Provides command-line interface for common tasks like
environment verification, AWS setup, and server management.
"""

import typer
from rich.console import Console

app = typer.Typer(
    name="llmops",
    help="LLMOps Agent - Multi-agent platform for autonomous ML training",
)
console = Console()


@app.command()
def version():
    """Show version information."""
    from llmops_agent import __version__

    console.print(f"[bold green]LLMOps Agent[/bold green] version {__version__}")


@app.command()
def verify():
    """Verify environment configuration."""
    from llmops_agent.scripts.verify_env import main as verify_main

    verify_main()


@app.command()
def setup():
    """Run AWS infrastructure setup."""
    console.print("[yellow]AWS setup not yet implemented[/yellow]")
    console.print("Follow the guide at: docs/setup/aws-setup.md")


if __name__ == "__main__":
    app()
