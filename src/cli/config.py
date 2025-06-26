from typing import Any
from urllib.parse import urlparse

import toml
from dynaconf import Dynaconf, Validator
from dynaconf.validator import ValidationError as DynaconfValidationError
from loguru import logger
from rich import print

from .constants import MIKUCAST_DIR, SECRETS_FILE_PATH, SETTINGS_FILE_PATH


def ensure_config_directory():
    """确保配置目录存在。在模块加载时调用一次。"""
    MIKUCAST_DIR.mkdir(parents=True, exist_ok=True)
    logger.debug(f"Ensured config directory: {MIKUCAST_DIR}")


# 确保在任何配置操作之前目录已存在
ensure_config_directory()


def is_valid_url(value: str) -> bool:
    """Dynaconf 验证器：检查一个值是否是有效的 HTTP/HTTPS URL。"""
    if not isinstance(value, str):
        return False
    try:
        result = urlparse(value)
        # 必须有 scheme (http/https) 和 netloc (domain name)
        return all([result.scheme in ["http", "https"], result.netloc])
    except ValueError:
        return False


class ConfigManager:
    """
    负责应用程序的配置和秘密管理。
    使用 Dynaconf 加载、验证和保存配置。
    """

    def __init__(self):
        self.settings = Dynaconf(
            envvar_prefix="MIKUCAST",  # 环境变量前缀
            settings_files=[
                str(SETTINGS_FILE_PATH),
                str(SECRETS_FILE_PATH),
            ],  # 配置文件路径
            env_nested_delimiter="__",  # 环境变量嵌套分隔符
            merge_enabled=True,  # 启用配置合并
            environments=True,  # 启用多环境支持
            env_switcher="MIKUCAST_ENV",  # 环境切换器环境变量
            load_dotenv=True,  # 加载 .env 文件
            # 定义配置验证器
            validators=[
                # 确保 model.model_name 和 model.base_url 存在且不为空
                Validator(
                    "model.provider.model_name",
                    "model.provider.base_url",
                    must_exist=True,
                    ne="",
                ),
                # 验证 model.base_url 必须是有效的 URL
                Validator(
                    "model.provider.base_url",
                    condition=is_valid_url,
                    messages={
                        "condition": "model.provider.base_url must be a valid and complete URL (e.g., https://api.openai.com/v1)"
                    },
                ),
            ],
        )

    def reload(self):
        """从文件和环境变量重新加载配置。"""
        self.settings.reload()
        logger.debug("Configuration reloaded.")

    def validate(self) -> bool:
        """
        验证当前加载的配置。
        如果验证失败，打印错误信息并返回 False。
        """
        try:
            self.settings.validators.validate()
            logger.info("Configuration is valid.")
            return True
        except DynaconfValidationError as e:
            print(f"[bold red]Configuration validation error:[/bold red]\n{e}")
            print("\nPlease run `mikucast setup` to fix the settings.")
            return False

    def validate_url_input(self, url: str) -> bool:
        """
        验证单个 URL 输入是否有效，不依赖于完整的 Dynaconf 验证。
        用于交互式输入时的即时验证。
        """
        return is_valid_url(url)

    def save_config(self, config_data: dict[str, Any], secrets_data: dict[str, Any]):
        """
        将配置和秘密分别写入对应的 TOML 文件。
        确保只保存默认环境下的配置到文件。
        """
        try:
            # Dynaconf 会将配置包装在环境中，所以这里也模拟结构
            # 确保保存到文件的总是 'default' 环境
            final_config = {"default": config_data.get("default", {})}
            final_secrets = {"default": secrets_data.get("default", {})}

            with open(SETTINGS_FILE_PATH, "w", encoding="utf-8") as f:
                toml.dump(final_config, f)
            with open(SECRETS_FILE_PATH, "w", encoding="utf-8") as f:
                toml.dump(final_secrets, f)

            print(
                f"\n✅ Configuration saved successfully to [cyan]{MIKUCAST_DIR}[/cyan]"
            )
            logger.info(
                f"Configuration saved to {SETTINGS_FILE_PATH} and {SECRETS_FILE_PATH}"
            )
        except OSError as e:  # 更具体的错误捕获：文件系统操作错误
            print(f"\n❌ Failed to save configuration due to file system error: {e}")
            logger.error(f"Failed to save configuration: {e}")
        except Exception as e:  # 捕获其他未知错误
            print(f"\n❌ An unexpected error occurred while saving configuration: {e}")
            logger.error(f"Unexpected error saving configuration: {e}", exc_info=True)

    def get_current_settings(self) -> dict[str, Any]:
        """返回当前加载的设置作为字典。"""
        # Dynaconf.as_dict() 默认返回当前环境的配置
        return self.settings.as_dict(env=self.settings.current_env)

    def set_value(self, key: str, value: Any):
        """动态设置配置值。"""
        self.settings.set(key, value)
        logger.debug(f"Set config value: {key}={value}")


# 全局配置管理器实例，供其他模块导入使用
config_manager = ConfigManager()
