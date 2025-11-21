import getpass

from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LINUX_MCP_", env_ignore_empty=True)

    user: str = getpass.getuser()


CONFIG = Config()
