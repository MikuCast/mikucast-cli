from typing import Any, Dict, List, Optional

import questionary
from loguru import logger
from rich import print

from .config import ConfigManager
from .constants import DEFAULT_PROVIDERS
from .llm_providers import LLMProvider, get_provider_instance


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

        provider_key = questionary.select(
            "Choose your LLM provider:",
            choices=list(DEFAULT_PROVIDERS.keys()),
            use_indicator=True,
        ).ask()

        if not provider_key:
            print("[yellow]Setup cancelled. No provider selected.[/yellow]")
            return

        provider_config_template = DEFAULT_PROVIDERS[provider_key]
        base_url = provider_config_template.get("base_url")

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

        llm_provider_instance: Optional[LLMProvider] = get_provider_instance(
            provider_key, base_url, api_key
        )

        models: List[str] = []
        if llm_provider_instance:
            models = llm_provider_instance.fetch_models()
        else:
            print(
                "[bold red]Error: Could not initialize LLM provider. Cannot fetch models.[/bold red]"
            )

        model_name: Optional[str] = None
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
        config_to_save: Dict[str, Any] = {
            "default": {
                "model": {
                    "base_url": base_url,
                    "model_name": model_name,
                }
            }
        }
        secrets_to_save: Dict[str, Any] = {
            "default": {
                "model": {
                    "api_key": api_key or "",
                }
            }
        }

        self._config_mgr.save_config(config_to_save, secrets_to_save)
        print("Please re-run your desired command with the new configuration.")
