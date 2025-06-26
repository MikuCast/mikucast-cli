# cli.py
import asyncio
import json
import sys

import questionary
import typer
from loguru import logger
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider
from rich import print

# 导入重构后的模块
from .config import config_manager
from .constants import LOGGING_LEVEL, SECRETS_FILE_PATH, SETTINGS_FILE_PATH
from .interactive import InteractiveSetup

# 配置 Loguru，移除默认 handler，添加 stderr handler
logger.remove()
logger.add(sys.stderr, level=LOGGING_LEVEL)

app = typer.Typer(
    help="MikuCast CLI - Your Intelligent Agent Framework.",
    add_completion=False,  # 不添加 shell 自动补全
    rich_markup_mode="markdown",  # 启用 rich 渲染 markdown
)


@app.callback()
def main_callback(ctx: typer.Context):
    """
    Typer 的主回调函数，在任何子命令执行前运行。
    用于执行全局初始化和配置检查。
    """
    logger.info(f"CLI application started. Command: {ctx.invoked_subcommand}")
    # 在执行 'setup' 或 'config' 命令时，跳过自动设置流程
    if ctx.invoked_subcommand in ["setup", "config"]:
        logger.debug(
            f"Skipping initial validation for '{ctx.invoked_subcommand}' command."
        )
        return

    config_manager.reload()
    if not config_manager.validate():
        print(
            "[yellow]Initial configuration is invalid. Starting interactive setup...[/yellow]"
        )
        interactive_setup_instance = InteractiveSetup(config_manager)
        interactive_setup_instance.run_setup()
        logger.info(
            "Setup completed. Exiting to allow configuration reload on next run."
        )
        raise typer.Exit(code=0)

    print(
        f"✅ Configuration valid. Running in [bold green]'{config_manager.settings.current_env}'[/bold green] environment."
    )
    logger.info("Base configuration validated successfully.")


def _get_configured_agent(
    model_name_override: str | None,
    base_url_override: str | None,
    api_key_override: str | None,
) -> Agent:
    """
    根据当前配置和可选的 CLI 覆盖参数，获取一个配置好的 Agent 实例。
    """
    with config_manager.settings.using_env(config_manager.settings.current_env):
        current_model_name = config_manager.settings.model.provider.model_name
        current_base_url = config_manager.settings.model.provider.base_url
        current_api_key = config_manager.settings.model.provider.api_key

        final_model_name = (
            model_name_override
            if model_name_override is not None
            else current_model_name
        )
        final_base_url = (
            base_url_override if base_url_override is not None else current_base_url
        )
        final_api_key = (
            api_key_override if api_key_override is not None else current_api_key
        )

        if model_name_override:
            print(
                f"Applying CLI override: [bold yellow]model.model_name={model_name_override}[/bold yellow]"
            )
        if base_url_override:
            print(
                f"Applying CLI override: [bold yellow]model.base_url={base_url_override}[/bold yellow]"
            )
        if api_key_override:
            print("Applying CLI override: [bold yellow]model.api_key=***[/bold yellow]")

        try:
            llm_provider = OpenAIProvider(
                base_url=final_base_url,
                api_key=final_api_key if final_api_key else None,
            )
            llm_model = OpenAIModel(final_model_name, provider=llm_provider)

            agent = Agent(
                llm_model,
                instructions="You are MikuCast, a helpful and concise AI assistant.",
            )

            print(
                f"✅ Agent successfully initialized with model [bold green]'{final_model_name}'[/bold green] "
                f"at [bold green]'{final_base_url}'[/bold green]."
            )
            print("--- [bold magenta]call hello world[/bold magenta] ---")
            logger.info(
                f"Agent initialized with model='{final_model_name}' and base_url='{final_base_url}'."
            )
            return agent
        except Exception as e:
            print(f"[bold red]Error initializing Agent: {e}[/bold red]")
            logger.critical(f"Failed to initialize Agent: {e}", exc_info=True)
            raise typer.Exit(code=1)


@app.command()
def ask(  # <-- Changed to synchronous 'def'
    question: str = typer.Argument(..., help="The question to ask the AI agent."),
    model_name: str | None = typer.Option(
        None, "--model", help="Override the default LLM model name."
    ),
    base_url: str | None = typer.Option(
        None, "--url", help="Override the default LLM base URL."
    ),
    api_key: str | None = typer.Option(
        None, "--key", help="Override the default LLM API Key."
    ),
):
    """
    Ask the AI agent a single question and get a concise answer.
    """
    logger.info(f"CLI command 'ask' executed with question: '{question}'")
    agent = _get_configured_agent(model_name, base_url, api_key)
    print(f"\n[bold blue]Asking: '{question}'[/bold blue]")

    async def _run_ask():
        try:
            async with agent.run_stream(question) as result:
                print("\n[bold green]Agent Response:[/bold green]")
                async for message in result.stream_text(delta=True):
                    print(message, end="")
                print("\n")
        except Exception as stream_e:
            print(
                f"[bold red]Error during agent stream execution: {stream_e}[/bold red]"
            )
            logger.error(
                f"Error during agent stream execution: {stream_e}", exc_info=True
            )

    asyncio.run(_run_ask())
    print("\n[bold green]Task execution completed.[/bold green]")


@app.command()
def chat(  # <-- Changed to synchronous 'def'
    model_name: str | None = typer.Option(
        None, "--model", help="Override the default LLM model name."
    ),
    base_url: str | None = typer.Option(
        None, "--url", help="Override the default LLM base URL."
    ),
    api_key: str | None = typer.Option(
        None, "--key", help="Override the default LLM API Key."
    ),
):
    """
    Start an interactive chat session with the AI agent.
    Type 'exit' or 'quit' to end the session.
    """
    logger.info("CLI command 'chat' executed. Starting interactive session.")
    agent = _get_configured_agent(model_name, base_url, api_key)

    async def _run_chat():
        print(
            "\n[bold blue]Starting interactive chat session. Type 'exit' or 'quit' to end.[/bold blue]"
        )
        while True:
            try:
                user_input = await questionary.text("You:").ask_async()
                if user_input is None:
                    break
                if not user_input:
                    continue
                if user_input.lower() in ["exit", "quit"]:
                    break
                print("\n[bold green]Agent:[/bold green]")
                async with agent.run_stream(user_input) as result:
                    async for message in result.stream_text(delta=True):
                        print(message, end="")
                    print("\n")
            except KeyboardInterrupt:
                print("\n[bold blue]Chat session interrupted.[/bold blue]")
                break
            except Exception as e:
                print(f"[bold red]An error occurred during chat: {e}[/bold red]")
                logger.error(f"Error in chat session: {e}", exc_info=True)
                break
        print("[bold blue]Ending chat session.[/bold blue]")

    asyncio.run(_run_chat())
    print("\n[bold green]Chat session ended.[/bold green]")


@app.command()
def shell(  # <-- Changed to synchronous 'def'
    command_prompt: str = typer.Argument(
        ...,
        help="Describe the shell command you need, e.g., 'list files in current directory'.",
    ),
    confirm: bool = typer.Option(
        True,
        "--no-confirm",
        help="Skip confirmation before executing the generated command.",
        is_flag=True,
        show_default=False,
    ),
    model_name: str | None = typer.Option(
        None, "--model", help="Override the default LLM model name."
    ),
    base_url: str | None = typer.Option(
        None, "--url", help="Override the default LLM base URL."
    ),
    api_key: str | None = typer.Option(
        None, "--key", help="Override the default LLM API Key."
    ),
):
    """
    Ask the AI to generate a shell command and optionally execute it.
    """
    logger.info(f"CLI command 'shell' executed with prompt: '{command_prompt}'")
    agent = _get_configured_agent(model_name, base_url, api_key)

    async def _run_shell():
        shell_instructions = (
            "You are an AI assistant that generates shell commands based on user requests. "
            "Provide only the command, without any explanations or additional text. "
            "Ensure the command is safe and portable. If you cannot generate a command, say 'N/A'."
        )
        print(
            f"\n[bold blue]Requesting shell command for: '{command_prompt}'[/bold blue]"
        )
        try:
            full_prompt = (
                f"{shell_instructions}\n\nUser request: {command_prompt}\n\nCommand:"
            )
            generated_command = ""
            print("\n[bold green]Agent Generating Command...[/bold green]")
            async with agent.run_stream(full_prompt) as result:
                async for message in result.stream_text(delta=True):
                    generated_command += message
                    print(message, end="")
            print("\n")
            generated_command = generated_command.strip()
            if not generated_command or generated_command.lower() == "n/a":
                print(
                    "[bold yellow]Agent could not generate a valid command.[/bold yellow]"
                )
                return

            print(f"[bold cyan]Generated Command:[/bold cyan] {generated_command}")
            execute_it = False
            if confirm:
                should_execute = await questionary.confirm(
                    "Execute this command?"
                ).ask_async()
                if should_execute:
                    execute_it = True
            else:
                execute_it = True

            if execute_it:
                print(f"[bold blue]Executing: {generated_command}[/bold blue]")
                process = await asyncio.create_subprocess_shell(
                    generated_command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await process.communicate()
                if stdout:
                    print(
                        f"\n[bold green]Command Output:[/bold green]\n{stdout.decode().strip()}"
                    )
                if stderr:
                    print(
                        f"\n[bold red]Command Error:[/bold red]\n{stderr.decode().strip()}"
                    )
                if process.returncode != 0:
                    print(
                        f"[bold red]Command exited with non-zero status: {process.returncode}[/bold red]"
                    )
                else:
                    print("[bold green]Command executed successfully.[/bold green]")
            else:
                print("[bold yellow]Command execution skipped by user.[/bold yellow]")
        except Exception as e:
            print(f"[bold red]An error occurred during shell workflow: {e}[/bold red]")
            logger.error(f"Error in shell workflow: {e}", exc_info=True)

    asyncio.run(_run_shell())
    print("\n[bold green]Shell task completed.[/bold green]")


@app.command()
def setup():
    """
    Run the interactive setup to configure or re-configure the application.
    """
    logger.info("CLI command 'setup' executed.")
    interactive_setup_instance = InteractiveSetup(config_manager)
    interactive_setup_instance.run_setup()
    typer.echo("Setup process finished. Please re-run your command.")


@app.command()
def config():
    """
    Display the current configuration loaded from files and environment.
    """
    logger.info("CLI command 'config' executed.")
    config_manager.reload()
    print(f"⚙️  Loading configuration from: [cyan]{SETTINGS_FILE_PATH}[/cyan]")
    if SECRETS_FILE_PATH.exists():
        print(f"🔒 Loading secrets from: [cyan]{SECRETS_FILE_PATH}[/cyan]")
    current_config = config_manager.get_current_settings()
    print("\n--- [bold green]Current Configuration[/bold green] ---")
    print(json.dumps(current_config, indent=2))
    print("-----------------------------")
    print("\n--- [bold green]Validation Status[/bold green] ---")
    if config_manager.validate():
        print("[green]✅ Configuration is valid.[/green]")
    else:
        print("[red]❌ Configuration is invalid. Run `mikucast setup` to fix.[/red]")


if __name__ == "__main__":
    app()


def main():
    app()


if __name__ == "__main__":
    app()
