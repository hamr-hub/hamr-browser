from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "info"

    browser_headless: bool = True
    browser_profile_dir: str = "./browser_profile"
    browser_timeout: int = 30000

    flows_dir: str = "./flows"
    secrets_file: str = "./secrets.yaml"
    logs_dir: str = "./logs"

    max_concurrent_flows: int = 1
    flow_timeout: int = 60

    class Config:
        env_file = ".env"
        env_prefix = "HAMR_"


settings = Settings()
