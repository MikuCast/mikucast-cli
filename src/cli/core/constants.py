"""
Core Constants for MikuCast CLI.

This module defines static, non-configurable values and paths used throughout the application.
It ensures that file locations and key names are centralized and consistent.
"""

from pathlib import Path

# --- Application Identity ---
APP_NAME = "mikucast"

# --- Core Directories ---
APP_DIR = Path.home() / f".{APP_NAME}"
"""The main configuration directory for the application."""

# --- Configuration File Names ---
SETTINGS_FILE_NAME = "settings.toml"
"""The main settings file, intended to be user-editable."""

SECRETS_FILE_NAME = ".secrets.toml"
"""The secrets file for sensitive data like API keys. Should be in .gitignore."""

DEFAULT_PROVIDERS_FILE_NAME = "default_providers.toml"
"""The built-in provider configuration file, shipped with the application."""

# --- Full File Paths ---
SETTINGS_FILE_PATH = APP_DIR / SETTINGS_FILE_NAME
"""The absolute path to the user's main settings file."""

SECRETS_FILE_PATH = APP_DIR / SECRETS_FILE_NAME
"""The absolute path to the user's secrets file."""
