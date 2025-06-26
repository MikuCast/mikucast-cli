from pathlib import Path

# --- 路径定义 ---
MIKUCAST_DIR = Path.home() / ".mikucast"
SETTINGS_FILE_PATH = MIKUCAST_DIR / "settings.toml"
SECRETS_FILE_PATH = MIKUCAST_DIR / ".secrets.toml"

# --- 默认提供商配置 ---
# 包含提供商的默认URL、认证头前缀以及任何额外的HTTP头
DEFAULT_PROVIDERS = {
    "openai": {"base_url": "https://api.openai.com/v1", "auth_header_prefix": "Bearer"},
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "auth_header_prefix": "Bearer",
    },
    "anthropic": {
        "base_url": "https://api.anthropic.com/v1",
        "auth_header_prefix": "X-API-Key",
    },
    "customize": {"base_url": None, "auth_header_prefix": "Bearer"},  # 自定义提供商
}

# --- API 端点 ---
MODELS_ENDPOINT = "/models"

# --- HTTP 设置 ---
HTTP_TIMEOUT = 10.0  # HTTP 请求超时时间（秒）

# --- 日志设置 ---
LOGGING_LEVEL = "INFO"  # 日志级别，可配置为 DEBUG, INFO, WARNING, ERROR, CRITICAL
