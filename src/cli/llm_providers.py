# mikucast/llm_providers.py
import abc
from typing import Any, Dict, List, Optional, Set

import httpx
from loguru import logger
from rich import print

from .constants import DEFAULT_PROVIDERS, HTTP_TIMEOUT, MODELS_ENDPOINT


class LLMProvider(abc.ABC):
    """
    LLM 提供商的抽象基类。
    定义了获取模型列表的通用接口和基本实现。
    """

    def __init__(
        self,
        base_url: str,
        api_key: Optional[str],
        auth_header_prefix: str,
        additional_headers: Optional[Dict[str, str]] = None,
    ):
        self._base_url = base_url.rstrip("/") if base_url else ""
        self._api_key = api_key
        self._auth_header_prefix = auth_header_prefix
        self._additional_headers = (
            additional_headers if additional_headers is not None else {}
        )

    def _get_api_headers(self) -> Dict[str, str]:
        """
        构造 API 请求所需的 HTTP 头。
        包含授权头和任何额外的提供商特定头。
        """
        headers = self._additional_headers.copy()
        if self._api_key:
            headers["Authorization"] = f"{self._auth_header_prefix} {self._api_key}"
        # 移除值为空的头，避免发送无用的Header
        return {k: v for k, v in headers.items() if v}

    @abc.abstractmethod
    def _parse_models_response(self, response_data: Dict[str, Any]) -> List[str]:
        """
        抽象方法：解析 API 响应数据，提取模型 ID 列表。
        不同的提供商可能有不同的响应结构。
        """
        pass

    def fetch_models(self) -> List[str]:
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
                response.raise_for_status()  # 针对 4xx/5xx 响应抛出 HTTPStatusError
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

                # 使用 set 去重，然后转换为 list 并排序
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
        except ValueError as e:  # 捕获 json.JSONDecodeError (ValueError 的子类)
            print(f"[bold red]Invalid JSON response from {url}: {e}[/bold red]")
            logger.error(f"Invalid JSON response from {url}: {e}")
        except Exception as e:  # 捕获其他所有未预料的错误
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

    def __init__(self, base_url: str, api_key: Optional[str]):
        super().__init__(
            base_url, api_key, DEFAULT_PROVIDERS["openai"]["auth_header_prefix"]
        )

    def _parse_models_response(self, response_data: Dict[str, Any]) -> List[str]:
        """解析 OpenAI API 的模型列表响应。"""
        return [m["id"] for m in response_data.get("data", []) if m and "id" in m]


class GeminiProvider(LLMProvider):
    """Gemini LLM 提供商的具体实现。"""

    def __init__(self, base_url: str, api_key: Optional[str]):
        super().__init__(
            base_url, api_key, DEFAULT_PROVIDERS["gemini"]["auth_header_prefix"]
        )

    def _parse_models_response(self, response_data: Dict[str, Any]) -> List[str]:
        """解析 Gemini API 的模型列表响应。"""
        # 假设 Gemini API 的模型列表在 "models" 键下，且模型ID为 "name"
        return [m["name"] for m in response_data.get("models", []) if m and "name" in m]


class AnthropicProvider(LLMProvider):
    """Anthropic LLM 提供商的具体实现。"""

    def __init__(self, base_url: str, api_key: Optional[str]):
        super().__init__(
            base_url,
            api_key,
            DEFAULT_PROVIDERS["anthropic"]["auth_header_prefix"],
            DEFAULT_PROVIDERS["anthropic"]["additional_headers"],
        )

    def _parse_models_response(self, response_data: Dict[str, Any]) -> List[str]:
        """解析 Anthropic API 的模型列表响应。"""
        # 注意：Anthropic 的 /v1/models 端点行为可能与 OpenAI 不同，
        # 实际上它可能返回的是单个模型对象而非列表，或者需要不同的端点。
        # 此处假设其行为类似 OpenAI，如果实际 API 不同，需要进一步调整。
        return [m["id"] for m in response_data.get("data", []) if m and "id" in m]


class CustomProvider(LLMProvider):
    """自定义 LLM 提供商的具体实现。"""

    def __init__(
        self, base_url: str, api_key: Optional[str], auth_header_prefix: str = "Bearer"
    ):
        super().__init__(base_url, api_key, auth_header_prefix)

    def _parse_models_response(self, response_data: Dict[str, Any]) -> List[str]:
        """
        解析自定义 LLM 提供商的模型列表响应。
        尝试从多种常见结构中提取模型 ID (例如，直接的列表，或在 'data' 键下)。
        """
        model_ids: Set[str] = set()

        if isinstance(response_data, list):
            # 如果响应是直接的模型列表
            for item in response_data:
                if isinstance(item, dict):
                    if "id" in item and isinstance(item["id"], str):
                        model_ids.add(item["id"])
                    elif "name" in item and isinstance(item["name"], str):
                        model_ids.add(item["name"])
        elif isinstance(response_data, dict):
            # 如果响应是一个字典，可能包含 "data" 或 "models" 键
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
                "Custom provider response structure unknown. Could not parse models. "
                f"Raw response keys: {response_data.keys() if isinstance(response_data, dict) else 'N/A'}"
            )

        return sorted(list(model_ids))


def get_provider_instance(
    provider_key: str, base_url: str, api_key: Optional[str]
) -> Optional[LLMProvider]:
    """
    工厂函数：根据提供商键返回相应的 LLMProvider 实例。
    """
    if provider_key == "openai":
        return OpenAIProvider(base_url, api_key)
    elif provider_key == "gemini":
        return GeminiProvider(base_url, api_key)
    elif provider_key == "anthropic":
        return AnthropicProvider(base_url, api_key)
    elif provider_key == "customize":
        # 对于自定义提供商，目前默认 Bearer，未来可以扩展让用户输入前缀
        return CustomProvider(base_url, api_key)
    else:
        logger.error(f"Unknown LLM provider key: {provider_key}")
        return None
