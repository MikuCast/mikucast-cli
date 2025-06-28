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
from pydantic import config
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
)
config_app = typer.Typer(help="Manage configuration.")
app.add_typer(config_app, name="config")

# --- CLI Commands ---


def is_config_valid(current_settings: AppSettings) -> bool:
    """Checks if the application configuration is present and minimally valid."""
    # 使用 hasattr 来安全地检查，防止因不完整的对象而引发 AttributeError
    if (
        hasattr(current_settings, "model")
        and current_settings.model
        and hasattr(current_settings.model, "name")
        and current_settings.model.name
        and hasattr(current_settings.model, "provider")
        and current_settings.model.provider
    ):
        return True
    return False


def ensure_valid_settings(ctx: typer.Context) -> AppSettings:
    """
    Checks the context. If setup is needed, runs it and returns the new settings.
    Otherwise, returns the existing valid settings.
    """
    context_data = ctx.obj
    if context_data.get("needs_setup"):
        setup_instance = InteractiveSetup()
        new_settings = setup_instance.run_setup()
        return new_settings
    else:
        return context_data.get("settings")


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """
    Gatekeeper: Checks config. If invalid, it "marks" the context so that
    subsequent commands know they need to run setup first.
    """
    if not is_config_valid(settings) and ctx.invoked_subcommand != "config":
        ctx.obj = {"needs_setup": True}
        console.print(
            Panel(
                "[bold yellow]Configuration is missing or invalid.[/bold yellow]\nLet's get you set up first!",
                title="🔧 Configuration Required 🔧",
                border_style="yellow",
            )
        )
    else:
        ctx.obj = {"needs_setup": False, "settings": settings}
    ensure_valid_settings(ctx)


@app.command()
def ask(
    ctx: typer.Context,
    question: str = typer.Argument(..., help="The question to ask the AI agent."),
):
    """Ask the agent a single question and get a direct answer."""

    current_settings = ensure_valid_settings(ctx)

    with AppContext(settings=current_settings) as app_context:
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
def chat(
    ctx: typer.Context,
):
    """Start an interactive chat session with the AI agent."""

    current_settings = ensure_valid_settings(ctx)

    with AppContext(settings=current_settings) as app_context:
        model_name = app_context.settings.model.name
        provider_name = app_context.settings.model.provider

        # 2. 创建一个美观的信息面板
        info_text = Text.from_markup(
            f"Model: [bold green]{model_name}[/bold green]\n"
            f"Provider: [bold green]{provider_name}[/bold green]\n\n"
            "Type your message and press Enter. Use 'exit' or Ctrl+D to quit."
        )
        console.print(
            Panel(
                info_text,
                title="✨ Interactive Chat Session ✨",
                border_style="blue",
                expand=False,
            )
        )
        app_context.logger.info(
            f"Starting chat session with model: {model_name} via {provider_name}"
        )

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


@config_app.command("setup")
def config_setup():
    """Run the interactive setup to configure the application."""
    setup_instance = InteractiveSetup()
    setup_instance.run_setup()


@config_app.command("list")
def config_list():
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


def run_app():
    app()


if __name__ == "__main__":
    run_app()
