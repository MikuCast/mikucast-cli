"""
Service Factories for MikuCast CLI.

This module provides simple, standalone functions to create and configure
the core services of the application, such as the logger and the AI agent.
"""

import sys

from loguru import logger as loguru_logger
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings

# Make sure these imports match your settings file structure
from .settings import AppSettings, LLMSettings, LogSettings


def create_logger(settings: LogSettings) -> loguru_logger:
    """
    Creates a Loguru logger instance based on the provided LogSettings.
    If no logfile is specified, the logger will be disabled.
    """
    loguru_logger.remove()  # Always remove default handlers first.

    log_level = settings.level.upper()
    log_file = settings.logfile

    # Only configure a logger if a log file path is provided.
    if log_file:
        loguru_logger.add(
            log_file,
            level=log_level,
            rotation="10 MB",
            retention="7 days",
            enqueue=True,  # Good for performance in some cases
            backtrace=True,
            diagnose=True,  # Useful for debugging exceptions
        )

        # This message will only appear if logging is actually enabled.
        loguru_logger.info(
            f"Logger initialized with level '{log_level}' and file '{log_file}'."
        )

    return loguru_logger


def create_agent(settings: AppSettings) -> Agent:
    """
    Creates and configures an AI Agent based on application settings,
    following the OpenAI-compatible model structure.
    """
    # 1. Get the name of the active provider (e.g., "openai", "groq")
    provider_name = settings.model.provider
    if provider_name not in settings.providers:
        raise ValueError(
            f"Provider '{provider_name}' is selected but not configured in settings.providers."
        )

    # 2. Get the configuration for that specific provider
    provider_config = settings.providers[provider_name]

    # 3. Extract the required values, just like os.getenv does in the example
    model_name = settings.model.name
    base_url = str(provider_config.base_url)  # Ensure it's a string
    api_key = provider_config.api_key if provider_config.api_key else None

    # 4. Perform the same validation as the reference example
    if not model_name or not base_url:
        raise ValueError(
            "Model name and base URL must be set and non-empty in your configuration."
        )

    # 5. Create the OpenAIModel and OpenAIProvider, exactly as in the reference
    #    This assumes the provider you use (like Groq) is OpenAI-compatible.
    model = OpenAIModel(
        model_name=model_name,
        provider=OpenAIProvider(
            base_url=base_url,
            api_key=api_key,
        ),
    )

    # 6. Create and return the final Agent with the configured model
    agent = Agent(
        model=model,
        instructions="You are MikuCast, a helpful and friendly AI assistant.",
        model_settings=ModelSettings(timeout=15),
    )

    return agent
