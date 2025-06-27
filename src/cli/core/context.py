from __future__ import annotations

from .services import create_agent, create_logger
from .settings import AppSettings


class AppContext:
    """
    A simple, synchronous context manager to prepare resources like the logger and agent.
    """

    def __init__(self, settings: AppSettings):
        """Initializes settings and logger."""
        self.settings = settings
        self.logger = create_logger(settings.log)
        self.agent = None

    def __enter__(self) -> AppContext:
        """Creates the agent when entering the 'with' block."""
        self.logger.info("Entering context, creating agent...")
        self.agent = create_agent(self.settings)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Exits the context. No special cleanup is needed here, as the process
        exit will handle resource cleanup.
        """
        self.logger.info("Exiting context.")
        pass
