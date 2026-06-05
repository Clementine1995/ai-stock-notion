from __future__ import annotations

import logging
from pathlib import Path

from app.config import PROJECT_ROOT, Settings


def setup_logging(settings: Settings) -> logging.Logger:
    log_path = Path(settings.log_file)
    if not log_path.is_absolute():
        log_path = PROJECT_ROOT / log_path
    log_path.parent.mkdir(parents=True, exist_ok=True)

    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers.clear()

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)

    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    return logging.getLogger("stock_ai_assistant")
