from typing import Any

import questionary
from rich import print

from .config import ConfigManager
from .llm_providers import PROVIDER_CONFIGS, LLMProvider, get_provider_instance


class InteractiveSetup:
    """
    负责MikuCast的交互式设置流程。
    依赖于 ConfigManager 和 LLMProvider 工厂函数。
    """

    def __init__(self, config_mgr: ConfigManager):
        self._config_mgr = config_mgr

    def run_setup(self):
        """
        引导用户进行交互式配置。
        """
        print("👋 Welcome to MikuCast CLI! Let's set up your LLM provider.")

        provider_choices = [
            # Use .capitalize() for a nicer display name (e.g., "Openai" -> "OpenAI")
            questionary.Choice(title=key.capitalize(), value=key)
            for key in PROVIDER_CONFIGS.keys()
        ]

        # 3. Add the special "Customize" option with a helpful description
        provider_choices.append(
            questionary.Choice(
                title="Customize (for other OpenAI-compatible APIs)", value="customize"
            )
        )

        provider_key = questionary.select(
            "Choose your LLM provider:",
            choices=provider_choices,
            use_indicator=True,
        ).ask()

        if not provider_key:
            print("[yellow]Setup cancelled. No provider selected.[/yellow]")
            return

        base_url = PROVIDER_CONFIGS[provider_key].base_url

        if not base_url:
            # 如果是自定义或预设中没有 base_url，则要求用户输入
            while True:
                base_url = questionary.text(
                    "Enter the Base URL for your provider:"
                ).ask()
                if not base_url:
                    print("[yellow]Base URL not provided. Setup cancelled.[/yellow]")
                    return
                # 即时验证 URL
                if self._config_mgr.validate_url_input(base_url):
                    break
                else:
                    print(
                        "[bold red]Invalid URL. Please enter a valid HTTP/HTTPS URL.[/bold red]"
                    )

        api_key = questionary.password(
            "Enter API Key (can be optional for local models):"
        ).ask()

        llm_provider_instance: LLMProvider | None = get_provider_instance(
            provider_key, base_url, api_key
        )

        models: list[str] = []
        if llm_provider_instance:
            models = llm_provider_instance.fetch_models()
        else:
            print(
                "[bold red]Error: Could not initialize LLM provider. Cannot fetch models.[/bold red]"
            )

        model_name: str | None = None
        if models:
            model_name = questionary.select(
                "Select a default model to use:", choices=models, use_indicator=True
            ).ask()
        else:
            print(
                "\n⚠️ Could not fetch model list from the provided API. You may need to manually enter the model name."
            )
            model_name = questionary.text(
                "Please manually enter a default model name:"
            ).ask()

        if not model_name:
            print("[yellow]Model name not provided. Setup cancelled.[/yellow]")
            return

        # 构建要保存的配置数据结构，确保符合 Dynaconf 的环境嵌套格式
        config_to_save: dict[str, Any] = {
            "default": {
                "model": {
                    "base_url": base_url,
                    "model_name": model_name,
                }
            }
        }
        secrets_to_save: dict[str, Any] = {
            "default": {
                "model": {
                    "api_key": api_key or "",
                }
            }
        }

        self._config_mgr.save_config(config_to_save, secrets_to_save)
        print("Please re-run your desired command with the new configuration.")
