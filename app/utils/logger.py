import logging
import os
from app.config import settings

os.makedirs(settings.logs_dir, exist_ok=True)

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(settings.logs_dir, "run.log"), encoding="utf-8"),
    ],
)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
