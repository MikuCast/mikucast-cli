"""
Main CLI entry point for MikuCast.

This module defines the command-line interface using Typer and follows the
pydantic-ai dependency injection pattern for all core functionality.
"""

# In your cli.py file

import asyncio
import json

import questionary
import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

# Make sure this import points to your new context file
from .core.context import AppContext
from .core.settings import AppSettings, settings
from .interactive import InteractiveSetup

# --- Initial Setup ---
console = Console()
app = typer.Typer(
    name="mikucast",
    help="MikuCast CLI - Your Intelligent Agent Framework.",
    add_completion=False,
    rich_markup_mode="markdown",
    no_args_is_help=True,
)

# --- CLI Commands ---


# main callback remains the same...
@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """Main callback. Handles initial checks and displays a welcome message."""
    if ctx.invoked_subcommand is None:
        try:
            welcome_text = Text.from_markup(
                f"Welcome to [bold magenta]MikuCast CLI[/bold magenta]!\n"
                f"Active Model: [green]{settings.model.name}[/green] via Provider: [green]{settings.model.provider}[/green]"
            )
            console.print(
                Panel(
                    welcome_text,
                    title="✨ Status ✨",
                    border_style="blue",
                    expand=False,
                )
            )
            console.print(
                "Use `[bold]mikucast --help[/bold]` to see available commands."
            )
        except Exception:
            console.print(
                "[bold yellow]Configuration is not set.[/bold yellow] Run `mikucast setup`."
            )
    elif ctx.invoked_subcommand not in ["setup", "config"]:
        try:
            # We only validate settings here, context is created in async command
            _ = AppSettings.model_validate(settings.model_dump())
        except Exception as e:
            console.print(
                f"[bold red]Configuration Error:[/bold red] {e}\n"
                "Please run `[bold cyan]mikucast setup[/bold cyan]` to configure the application."
            )
            raise typer.Exit(1)


@app.command()
def ask(question: str = typer.Argument(..., help="The question to ask the AI agent.")):
    """Ask the agent a single question and get a direct answer."""

    # Use a standard synchronous 'with' block to manage the AppContext
    with AppContext(settings=settings) as app_context:
        app_context.logger.info(f"Executing 'ask' command with question: '{question}'")

        # The core async logic is kept in its own function
        async def _run_ask_async():
            try:
                # The agent from the context is used here for the async operation
                # NOTE: The 'deps=app_context' argument might not be necessary if your
                # agent's tools don't need access to the full context, but it's harmless.
                async with app_context.agent.run_stream(question) as result:
                    async for message in result.stream_text(delta=True):
                        console.print(message, end="")
                    console.print("\n")
            except Exception as e:
                console.print(
                    f"\n[bold red]Error during agent execution:[/bold red] {e}"
                )
                # The logger from the context is available here
                app_context.logger.error(f"Agent execution failed: {e}", exc_info=True)

        # Run the async function from within the synchronous 'with' block.
        # This ensures __exit__ is called after the async operation completes.
        try:
            asyncio.run(_run_ask_async())
        except Exception as e:
            # Catch potential errors from the asyncio part itself if needed
            console.print(f"\n[bold red]An application error occurred:[/bold red] {e}")
            app_context.logger.error(f"Async task runner failed: {e}", exc_info=True)


@app.command()
def chat():
    """Start an interactive chat session with the AI agent."""

    # This part is synchronous setup
    console.print(
        "\n[bold blue]Starting interactive chat. (Press Ctrl+D or type 'exit' to end)[/bold blue]"
    )

    with AppContext(settings=settings) as app_context:
        app_context.logger.info("Chat context created.")

        # The async logic remains inside its own function
        async def _run_chat_async():
            while True:
                try:
                    prompt = await questionary.text("You:").ask_async()
                    if prompt is None or prompt.lower() in ["exit", "quit"]:
                        break
                    if not prompt.strip():
                        continue

                    console.print("\n[bold green]Agent:[/bold green] ", end="")
                    # The agent from the context is used here
                    async with app_context.agent.run_stream(prompt) as result:
                        async for message in result.stream_text(delta=True):
                            console.print(message, end="")
                    console.print("\n")

                except KeyboardInterrupt:
                    break
                except Exception as e:
                    console.print(f"\n[bold red]An error occurred:[/bold red] {e}")
                    app_context.logger.error(f"Chat session error: {e}", exc_info=True)
                    break

        # We run the async part from within the synchronous 'with' block
        try:
            asyncio.run(_run_chat_async())
        finally:
            # The 'with' block will now call __exit__ automatically,
            # ensuring cleanup happens even if asyncio.run() has an error.
            console.print("\n[bold blue]Chat session ended.[/bold blue]")


@app.command()
def setup():
    """Run the interactive setup to configure the application."""
    try:
        setup_instance = InteractiveSetup()
        setup_instance.run_setup()
    except Exception as e:
        console.print(f"\n[bold red]An error occurred during setup:[/bold red] {e}")
        # We may not have a logger here, so print to console
        print(f"Setup failed: {e}")


@app.command()
def config():
    """Display the current application configuration."""
    # This command is synchronous, so we don't need the async context
    app_context = AppContext(settings=settings)
    app_context.logger.info("Executing 'config' command.")

    console.print("[bold blue]--- Current Configuration ---[/bold blue]")

    config_dict = app_context.settings.model_dump(mode="json")

    # Redact all API keys before printing
    if "providers" in config_dict:
        for provider in config_dict["providers"]:
            if (
                config_dict["providers"][provider]
                and "api_key" in config_dict["providers"][provider]
                and config_dict["providers"][provider]["api_key"]
            ):
                config_dict["providers"][provider]["api_key"] = "********"

    # console.print_json can now safely handle the data
    # As an alternative, you can convert to a string yourself for full control
    console.print(json.dumps(config_dict, indent=2))


# main and __main__ block remain the same
def main():
    app()


if __name__ == "__main__":
    main()
