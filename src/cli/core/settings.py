"""
Centralized Configuration Management for MikuCast CLI.

This module loads settings from files and environment variables, then validates
them using a Pydantic model. This provides a single, reliable source of truth
for all application settings.
"""

import sys
from pathlib import Path

from dynaconf import Dynaconf
from pydantic import BaseModel, Field, HttpUrl, ValidationError
from rich import print

from . import constants

# --- Pydantic Models for Typed Configuration ---


class LogSettings(BaseModel):
    level: str = Field("DEBUG", description="The minimum log level to record.")
    logfile: Path | None = Field(None, description="Path for storing logs.")


class LLMSettings(BaseModel):
    provider: str | None = Field(None, description="The key of the selected provider.")
    name: str | None = Field(None, description="The name of the model to use.")


class ProviderSettings(BaseModel):
    base_url: HttpUrl
    auth_header_prefix: str = "Bearer"
    models_endpoint: str = "/models"
    models_response_path: str = "data"
    model_id_key: str = "id"
    api_key: str | None = None


class AppSettings(BaseModel):
    log: LogSettings = Field(default_factory=LogSettings)
    model: LLMSettings = Field(default_factory=LLMSettings)
    providers: dict[str, ProviderSettings] = Field(default_factory=dict)


# --- Loading and Validation Logic ---


def load_settings() -> AppSettings:
    """
    Loads settings from all sources and validates them into a Pydantic model.
    This is the single entry point for configuration.
    """
    try:
        # Step 1: Ensure config files exist to prevent Dynaconf errors.
        ensure_config_files_exist()

        # Step 2: Use Dynaconf to load raw data from all sources.
        loader = Dynaconf(
            envvar_prefix=constants.APP_NAME.upper(),
            settings_files=[
                str(Path(__file__).parent / constants.DEFAULT_PROVIDERS_FILE_NAME),
                str(constants.SETTINGS_FILE_PATH),
                str(constants.SECRETS_FILE_PATH),
            ],
            merge_enabled=True,
            env_nested_delimiter="__",
        )

        # Step 3: Convert the loaded data to a dictionary and lowercase keys.
        settings_dict = loader.as_dict()
        lowercased_settings = {k.lower(): v for k, v in settings_dict.items()}

        # Step 4: Validate the dictionary with Pydantic.
        return AppSettings.model_validate(lowercased_settings)

    except ValidationError as e:
        print(f"[bold red]Configuration Error:[/bold red] {e}")
        sys.exit(1)
    except Exception as e:
        print(
            f"[bold red]An unexpected error occurred while loading settings:[/bold red] {e}"
        )
        sys.exit(1)


def get_current_provider_settings() -> ProviderSettings:
    """Retrieves the configuration for the currently active provider."""
    provider_key = settings.model.provider
    provider_conf = settings.providers.get(provider_key)

    if not provider_conf:
        print(
            f"[bold red]Configuration Error:[/bold red] The provider '{provider_key}' is selected "
            f"but not defined in the [providers] section of your settings.",
            file=sys.stderr,
        )
        raise sys.exit(1)

    return provider_conf


def ensure_config_files_exist():
    """Ensures that the configuration directory and essential files exist."""
    try:
        constants.APP_DIR.mkdir(parents=True, exist_ok=True)
        if not constants.SETTINGS_FILE_PATH.exists():
            constants.SETTINGS_FILE_PATH.touch()
        if not constants.SECRETS_FILE_PATH.exists():
            constants.SECRETS_FILE_PATH.touch()
    except OSError as e:
        print(
            f"[bold red]Error:[/bold red] Could not create config directory at '{constants.APP_DIR}'. Reason: {e}",
            file=sys.stderr,
        )
        raise sys.exit(1)


# --- Global Settings Instance ---

# Load the settings once and make them available for import.
settings = load_settings()
