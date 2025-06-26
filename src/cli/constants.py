from pathlib import Path

# --- 路径定义 ---
MIKUCAST_DIR = Path.home() / ".mikucast"
SETTINGS_FILE_PATH = MIKUCAST_DIR / "settings.toml"
SECRETS_FILE_PATH = MIKUCAST_DIR / ".secrets.toml"

# --- API 端点 ---
MODELS_ENDPOINT = "/models"

# --- HTTP 设置 ---
HTTP_TIMEOUT = 10.0  # HTTP 请求超时时间（秒）

# --- 日志设置 ---
LOGGING_LEVEL = "INFO"  # 日志级别，可配置为 DEBUG, INFO, WARNING, ERROR, CRITICAL
