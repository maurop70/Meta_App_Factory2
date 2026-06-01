"""
Loop UI
-------
Simple terminal interface for the autonomous loop.
You type what you want. The loop does the rest.
"""

import sys
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

sys.path.insert(0, str(Path(__file__).parent))
from loop_engine import AutonomousLoop
from ay_client import test_connection

console = Console()


def print_banner():
    console.print(Panel.fit(
        "[bold blue]Meta App Factory[/bold blue]\n"
        "[dim]Claude (Architect) ↔ Antigravity (Executor)[/dim]\n"
        "[dim]Autonomous Loop Engine v1.0[/dim]",
        border_style="blue"
    ))


def check_systems():
    console.print("\n[dim]Checking systems...[/dim]")

    # Check AY connection
    console.print("[dim]  → Antigravity API...[/dim]", end="")
    if test_connection():
        console.print(" [green]✓ Connected[/green]")
    else:
        console.print(" [red]✗ Failed[/red]")
        console.print("[red]Cannot reach Antigravity API. "
                      "Check GEMINI_API_KEY in .env[/red]")
        sys.exit(1)

    # Check MCP bridge telemetry
    telem_log = Path(__file__).parent / "logs" / "telemetry.jsonl"
    console.print("[dim]  → MCP Bridge telemetry...[/dim]", end="")
    if telem_log.exists():
        console.print(" [green]✓ Active[/green]")
    else:
        console.print(" [yellow]⚠ No telemetry yet (Chrome extension "
                      "may not be connected)[/yellow]")

    # Check rules
    rules = Path(__file__).parent / "rules" / "CLAUDE_RULES.md"
    console.print("[dim]  → CLAUDE_RULES.md...[/dim]", end="")
    if rules.exists():
        lines = rules.read_text(encoding="utf-8").count("\n")
        console.print(f" [green]✓ Loaded ({lines} lines)[/green]")
    else:
        console.print(" [red]✗ Missing[/red]")
        sys.exit(1)

    console.print()


def main():
    print_banner()
    check_systems()

    console.print("[bold]You are the CEO. Type what you want built.[/bold]")
    console.print("[dim]Type 'exit' to quit. "
                  "Interrupt anytime by typing your directive.[/dim]\n")

    while True:
        try:
            intent = Prompt.ask("[bold blue]>[/bold blue]").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Session closed.[/dim]")
            break

        if intent.lower() in ("exit", "quit", "q"):
            console.print("[dim]Session closed.[/dim]")
            break

        if not intent:
            continue

        loop = AutonomousLoop()
        loop.run(intent)

        console.print("\n[dim]─────────────────────────────────────[/dim]")
        console.print("[dim]Loop complete. Ready for next intent.[/dim]\n")


if __name__ == "__main__":
    main()
