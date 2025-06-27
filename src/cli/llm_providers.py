"""
LLM Provider Abstraction for MikuCast CLI.

This module defines a generic, data-driven way to interact with LLM providers.
It is responsible for fetching available models from any provider configured
in the settings files.
"""

import abc
from typing import Any

import httpx
import jmespath
from loguru import logger
from rich.console import Console

from .core.settings import ProviderSettings

console = Console()


class LLMProvider(abc.ABC):
    """Abstract base class for all LLM providers."""

    @abc.abstractmethod
    def fetch_models(self) -> list[str]:
        """Fetches a list of available model names from the provider."""
        pass


class GenericLLMProvider(LLMProvider):
    """
    A generic implementation of an LLM provider that is configured entirely
    by a ProviderSettings object. It can adapt to any OpenAI-compatible API
    and many others by specifying the correct paths and keys in the config.
    """

    def __init__(self, config: ProviderSettings, logger: logger):
        self._config = config
        self._logger = logger

    def _get_api_headers(self) -> dict[str, str]:
        """Constructs the necessary HTTP headers for the API request."""
        headers = {}
        if self._config.api_key:
            headers["Authorization"] = (
                f"{self._config.auth_header_prefix} {self._config.api_key}"
            )
        return headers

    def fetch_models(self) -> list[str]:
        """Fetches the list of models from the configured endpoint."""
        if not self._config.base_url:
            self._logger.warning("Base URL is not set; cannot fetch models.")
            return []

        url = f"{str(self._config.base_url).rstrip('/')}{self._config.models_endpoint}"
        headers = self._get_api_headers()

        console.print(f"Fetching models from [bold blue]{url}[/bold blue]...")
        self._logger.info(f"Attempting to fetch models from {url}")

        try:
            with httpx.Client(timeout=15.0) as client:
                response = client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()

                # Use JMESPath to extract the list of models
                models_list = jmespath.search(self._config.models_response_path, data)

                if not isinstance(models_list, list):
                    self._logger.warning(
                        f"Expected a list from JMESPath expression, but got {type(models_list)}."
                    )
                    console.print(
                        f"[bold yellow]Warning:[/bold yellow] Could not find a list of models at path ''{self._config.models_response_path}'' in the API response."
                    )
                    return []

                # Extract model IDs using the specified key
                model_ids = [
                    jmespath.search(self._config.model_id_key, item)
                    for item in models_list
                    if isinstance(item, dict)
                ]

                # Filter out any None results from the search
                valid_models = sorted([str(mid) for mid in model_ids if mid])

                if not valid_models:
                    console.print(
                        "[bold yellow]Warning:[/bold yellow] API returned an empty list of models or the response format was unexpected."
                    )
                    self._logger.warning(
                        f"Parsed model list was empty. Check `models_response_path` and `model_id_key` settings. Raw data keys: {data.keys() if isinstance(data, dict) else 'N/A'}"
                    )
                else:
                    console.print(f"[green]Found {len(valid_models)} models.[/green]")
                    self._logger.info(
                        f"Successfully fetched {len(valid_models)} models."
                    )

                return valid_models

        except httpx.HTTPStatusError as e:
            console.print(
                f"[bold red]HTTP Error:[/bold red] Could not fetch models from {url}. Status: {e.response.status_code}"
            )
            self._logger.error(
                f"HTTP Error fetching models: {e.response.status_code} - {e.response.text}"
            )
        except httpx.RequestError as e:
            console.print(
                f"[bold red]Network Error:[/bold red] Could not connect to {url}. Reason: {e}"
            )
            self._logger.error(f"Network Error fetching models: {e}")
        except jmespath.exceptions.JMESPathError as e:
            console.print(
                f"[bold red]Configuration Error:[/bold red] Invalid JMESPath expression for models: {e}"
            )
            self._logger.error(f"JMESPath parsing error: {e}")
        except Exception as e:
            console.print(f"[bold red]An unexpected error occurred:[/bold red] {e}")
            self._logger.error(f"Unexpected error fetching models: {e}", exc_info=True)

        return []

