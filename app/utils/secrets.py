import os
import yaml
from typing import Any, Dict, Optional
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

_secrets: Optional[Dict[str, Any]] = None


def load_secrets() -> Dict[str, Any]:
    global _secrets
    if _secrets is not None:
        return _secrets

    path = settings.secrets_file
    if not os.path.exists(path):
        logger.warning(f"secrets 文件不存在：{path}，认证功能将不可用")
        _secrets = {}
        return _secrets

    with open(path, "r", encoding="utf-8") as f:
        _secrets = yaml.safe_load(f) or {}
    return _secrets


def get_secret(key: str) -> Optional[Dict[str, Any]]:
    secrets = load_secrets()
    return secrets.get(key)
