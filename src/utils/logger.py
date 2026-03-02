"""
日志工具
"""
import logging
import structlog
from src.config import settings


def setup_logging():
    """配置结构化日志"""
    # 获取logging模块的级别
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer() if settings.LOG_FORMAT == "json" else structlog.dev.ConsoleRenderer(),
        ],
        context_class=dict,
        cache_logger_on_first_use=True,
    )

    # 设置全局日志级别
    logging.basicConfig(level=log_level)

    return structlog.get_logger()

# 全局日志实例
logger = setup_logging()
