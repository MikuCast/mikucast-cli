# mikucast/llm_providers.py
import abc
from typing import Any

import httpx
from loguru import logger
from pydantic import BaseModel, Field
from rich import print

from .constants import HTTP_TIMEOUT, MODELS_ENDPOINT


class ProviderConfig(BaseModel):
    """Defines the configuration for a single LLM provider."""

    base_url: str | None = None
    auth_header_prefix: str = "Bearer"
    additional_headers: dict[str, str] | None = Field(default_factory=dict)


PROVIDER_CONFIGS: dict[str, ProviderConfig] = {
    "openai": ProviderConfig(
        base_url="https://api.openai.com/v1", auth_header_prefix="Bearer"
    ),
    "gemini": ProviderConfig(
        base_url="https://generativelanguage.googleapis.com/v1beta",
        auth_header_prefix="Bearer",
    ),
    "anthropic": ProviderConfig(
        base_url="https://api.anthropic.com/v1",
        auth_header_prefix="X-API-Key",
    ),
}


class LLMProvider(abc.ABC):
    """
    LLM 提供商的抽象基类。
    定义了获取模型列表的通用接口和基本实现。
    """

    def __init__(
        self,
        base_url: str,
        api_key: str | None,
        auth_header_prefix: str,
        additional_headers: dict[str, str] | None = None,
    ):
        self._base_url = base_url.rstrip("/") if base_url else ""
        self._api_key = api_key
        self._auth_header_prefix = auth_header_prefix
        self._additional_headers = additional_headers or {}

    def _get_api_headers(self) -> dict[str, str]:
        """
        构造 API 请求所需的 HTTP 头。
        包含授权头和任何额外的提供商特定头。
        """
        headers = self._additional_headers.copy()
        if self._api_key:
            headers["Authorization"] = f"{self._auth_header_prefix} {self._api_key}"
        return {k: v for k, v in headers.items() if v}

    @abc.abstractmethod
    def _parse_models_response(self, response_data: dict[str, Any]) -> list[str]:
        """
        抽象方法：解析 API 响应数据，提取模型 ID 列表。
        不同的提供商可能有不同的响应结构。
        """
        pass

    def fetch_models(self) -> list[str]:
        """
        从 LLM 提供商 API 获取模型列表。
        处理 HTTP 请求、错误和通用响应解析。
        """
        if not self._base_url:
            logger.warning("Base URL is not set for provider, cannot fetch models.")
            return []
        url = f"{self._base_url}{MODELS_ENDPOINT}"
        headers = self._get_api_headers()
        print(f"Fetching models from [bold blue]{url}[/bold blue]...")
        logger.info(f"Attempting to fetch models from {url}")
        try:
            with httpx.Client(timeout=HTTP_TIMEOUT) as client:
                response = client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()
                models = self._parse_models_response(data)
                if not models:
                    print(
                        "[bold yellow]Warning: API returned an empty list of models or an unexpected format.[/bold yellow]"
                    )
                    logger.warning(
                        "API returned an empty list of models or an unexpected format."
                    )
                else:
                    print(f"[green]Found {len(models)} models.[/green]")
                    logger.info(f"Successfully fetched {len(models)} models.")
                return sorted(list(set(models)))
        except httpx.HTTPStatusError as e:
            print(
                f"[bold red]HTTP Error fetching models from {url}: {e.response.status_code} - {e.response.text}[/bold red]"
            )
            logger.error(
                f"HTTP Error fetching models from {url}: {e.response.status_code} - {e.response.text}"
            )
        except httpx.RequestError as e:
            print(f"[bold red]Network Error fetching models from {url}: {e}[/bold red]")
            logger.error(f"Network Error fetching models from {url}: {e}")
        except ValueError as e:
            print(f"[bold red]Invalid JSON response from {url}: {e}[/bold red]")
            logger.error(f"Invalid JSON response from {url}: {e}")
        except Exception as e:
            print(
                f"[bold red]An unexpected error occurred while fetching models: {e}[/bold red]"
            )
            logger.error(
                f"An unexpected error occurred while fetching models: {e}",
                exc_info=True,
            )
        return []


class OpenAIProvider(LLMProvider):
    """OpenAI LLM 提供商的具体实现。"""

    def __init__(self, base_url: str, api_key: str | None):
        config = PROVIDER_CONFIGS["openai"]
        super().__init__(
            base_url=base_url,
            api_key=api_key,
            auth_header_prefix=config.auth_header_prefix,
            additional_headers=config.additional_headers,
        )

    def _parse_models_response(self, response_data: dict[str, Any]) -> list[str]:
        return [m["id"] for m in response_data.get("data", []) if m and "id" in m]


class GeminiProvider(LLMProvider):
    """Gemini LLM 提供商的具体实现。"""

    def __init__(self, base_url: str, api_key: str | None):
        config = PROVIDER_CONFIGS["gemini"]
        super().__init__(
            base_url=base_url,
            api_key=api_key,
            auth_header_prefix=config.auth_header_prefix,
            additional_headers=config.additional_headers,
        )

    def _parse_models_response(self, response_data: dict[str, Any]) -> list[str]:
        return [m["name"] for m in response_data.get("models", []) if m and "name" in m]


class AnthropicProvider(LLMProvider):
    """Anthropic LLM 提供商的具体实现。"""

    def __init__(self, base_url: str, api_key: str | None):
        config = PROVIDER_CONFIGS["anthropic"]
        super().__init__(
            base_url=base_url,
            api_key=api_key,
            auth_header_prefix=config.auth_header_prefix,
            additional_headers=config.additional_headers,
        )

    def _parse_models_response(self, response_data: dict[str, Any]) -> list[str]:
        return [m["id"] for m in response_data.get("data", []) if m and "id" in m]


class CustomProvider(LLMProvider):
    """自定义 LLM 提供商的具体实现。"""

    def __init__(
        self, base_url: str, api_key: str | None, auth_header_prefix: str = "Bearer"
    ):
        super().__init__(base_url, api_key, auth_header_prefix)

    def _parse_models_response(self, response_data: dict[str, Any]) -> list[str]:
        model_ids: set[str] = set()
        if isinstance(response_data, list):
            for item in response_data:
                if isinstance(item, dict):
                    if "id" in item and isinstance(item["id"], str):
                        model_ids.add(item["id"])
                    elif "name" in item and isinstance(item["name"], str):
                        model_ids.add(item["name"])
        elif isinstance(response_data, dict):
            for key in ["data", "models"]:
                if key in response_data and isinstance(response_data[key], list):
                    for item in response_data[key]:
                        if isinstance(item, dict):
                            if "id" in item and isinstance(item["id"], str):
                                model_ids.add(item["id"])
                            elif "name" in item and isinstance(item["name"], str):
                                model_ids.add(item["name"])
        if not model_ids:
            logger.warning(
                f"Custom provider response structure unknown. Could not parse models. Raw response keys: {response_data.keys() if isinstance(response_data, dict) else 'N/A'}"
            )
        return sorted(list(model_ids))


def get_provider_instance(
    provider_key: str, base_url: str, api_key: str | None
) -> LLMProvider | None:
    """
    工厂函数：根据提供商键返回相应的 LLMProvider 实例。
    """
    provider_map = {
        "openai": OpenAIProvider,
        "gemini": GeminiProvider,
        "anthropic": AnthropicProvider,
        "customize": CustomProvider,
    }

    if provider_key in provider_map:
        # Get the provider class from the map
        provider_class = provider_map[provider_key]

        # Get the default base_url from the config if the provided one is empty
        final_base_url = base_url or PROVIDER_CONFIGS[provider_key].base_url or ""

        return provider_class(final_base_url, api_key)

    elif provider_key == "customize":
        return CustomProvider(base_url, api_key)
    else:
        logger.error(f"Unknown LLM provider key: {provider_key}")
        return None
