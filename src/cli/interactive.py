"""
Handles the interactive setup process for MikuCast CLI.

This module guides the user through configuring their LLM provider and model,
leveraging the dependency injection system to access necessary services.
"""

from typing import Any

import questionary
import toml
from pydantic import HttpUrl
from rich.console import Console

from .core import constants
from .core.context import AppContext
from .core.settings import AppSettings, ProviderSettings, load_settings, settings
from .llm_providers import GenericLLMProvider

console = Console()


class InteractiveSetup:
    """Manages the interactive setup and configuration of the CLI."""

    def __init__(self):
        # Create a temporary context for the setup process
        self._ctx = AppContext(settings=settings)
        self._settings = self._ctx.settings
        self._logger = self._ctx.logger

    def run_setup(self) -> AppSettings:
        """Guides the user through the full interactive setup process."""
        console.print("👋 Welcome to MikuCast CLI! Let's set up your LLM provider.")

        # --- Provider Selection ---
        provider_key = self._select_provider()
        if not provider_key:
            return

        # --- Base URL Configuration ---
        base_url = self._configure_base_url(provider_key)
        if not base_url:
            return

        # --- API Key Configuration ---
        api_key = questionary.password(
            "Enter your API Key (optional, press Enter to skip):"
        ).ask()

        # --- Model Selection ---
        provider_config_for_fetch = self._build_temp_provider_config(
            provider_key, base_url, api_key
        )
        model_name = self._select_model(provider_config_for_fetch)
        if not model_name:
            return

        # --- Save Configuration ---
        self._save_configuration(provider_key, base_url, model_name, api_key)

        console.print(
            "\n[bold green]✅ Setup complete![/bold green] Your settings have been saved."
        )
        return load_settings()

    def _select_provider(self) -> str | None:
        """Asks the user to select an LLM provider."""
        provider_choices = ["custom"]
        provider_choices.extend(
            [p for p in list(self._settings.providers.keys()) if p != "custom"]
        )

        selected_provider = questionary.select(
            "Choose your LLM provider:",
            choices=provider_choices,
            use_indicator=True,
        ).ask()

        if not selected_provider:
            console.print("[yellow]Setup cancelled. No provider selected.[/yellow]")
            return None
        return selected_provider

    def _configure_base_url(self, provider_key: str) -> HttpUrl | None:
        """Asks the user for the provider's base URL."""
        default_url = ""
        if provider_key != "custom":
            default_url = str(self._settings.providers[provider_key].base_url)

        while True:
            url_str = questionary.text(
                "Enter the API base URL:", default=default_url
            ).ask()

            if not url_str:
                console.print("[yellow]Setup cancelled. Base URL is required.[/yellow]")
                return None
            try:
                # Validate the URL with Pydantic
                return HttpUrl(url_str)
            except ValueError:
                console.print(
                    "[bold red]Invalid URL.[/bold red] Please enter a complete URL (e.g., 'https://api.example.com')."
                )

    def _build_temp_provider_config(
        self, provider_key: str, base_url: HttpUrl, api_key: str | None
    ) -> ProviderSettings:
        """Creates a temporary ProviderSettings object for fetching models."""
        # Get defaults from the selected provider, or create a blank slate for 'custom'
        base_config = (
            self._settings.providers.get(provider_key, {})
            if provider_key != "custom"
            else {}
        )
        # Ensure base_config is a dict for unpacking
        if not isinstance(base_config, dict):
            base_config = (
                base_config.model_dump() if hasattr(base_config, "model_dump") else {}
            )

        # Remove conflicting keys that are being passed explicitly
        base_config.pop("base_url", None)
        base_config.pop("api_key", None)

        return ProviderSettings(
            base_url=base_url,
            api_key=api_key,
            # Carry over other settings like headers, endpoints, etc.
            **base_config,
        )

    def _select_model(self, provider_config: ProviderSettings) -> str | None:
        """Fetches and asks the user to select a model."""
        provider_instance = GenericLLMProvider(
            config=provider_config, logger=self._logger
        )
        models = provider_instance.fetch_models()

        if not models:
            console.print(
                "\n[bold yellow]⚠️ Could not automatically fetch model list.[/bold yellow]"
            )
            model_name = questionary.text(
                "Please manually enter the model name you want to use:",
            ).ask()
        else:
            model_name = questionary.select(
                "Select a default model to use:", choices=models, use_indicator=True
            ).ask()

        if not model_name:
            console.print("[yellow]Setup cancelled. No model selected.[/yellow]")
            return None
        return model_name

    def _save_configuration(
        self, provider: str, base_url: HttpUrl, model_name: str, api_key: str | None
    ):
        """Saves the chosen configuration to the user's settings files."""
        # --- Prepare settings for user's settings.toml ---
        user_settings = {
            "model": {"provider": provider, "name": model_name},
            "providers": {
                provider: {"base_url": str(base_url)}  # Only save the URL override
            },
        }

        # --- Prepare secrets for user's .secrets.toml ---
        user_secrets = {"providers": {provider: {"api_key": api_key or ""}}}

        try:
            # Write to the main settings file
            with open(constants.SETTINGS_FILE_PATH, "w", encoding="utf-8") as f:
                toml.dump(user_settings, f)

            # Write to the secrets file
            with open(constants.SECRETS_FILE_PATH, "w", encoding="utf-8") as f:
                toml.dump(user_secrets, f)

        except OSError as e:
            console.print(f"\n[bold red]Error saving configuration:[/bold red] {e}")
