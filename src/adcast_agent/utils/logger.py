"""
结构化日志模块 - 支持JSON格式输出，便于后续分析
"""

import logging
import sys
import json
from datetime import datetime
from typing import Any, Dict, Optional


class JSONFormatter(logging.Formatter):
    """JSON格式日志格式化器"""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # 添加额外字段
        if hasattr(record, "platform"):
            log_data["platform"] = record.platform
        if hasattr(record, "action"):
            log_data["action"] = record.action
        if hasattr(record, "campaign_id"):
            log_data["campaign_id"] = record.campaign_id
        if hasattr(record, "extra"):
            log_data.update(record.extra)

        # 异常信息
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, ensure_ascii=False, default=str)


def setup_logger(
    name: str = "adcast",
    level: str = "INFO",
    use_json: bool = True,
    log_file: Optional[str] = None,
) -> logging.Logger:
    """
    设置日志记录器

    Args:
        name: 日志名称
        level: 日志级别
        use_json: 是否使用JSON格式
        log_file: 日志文件路径（可选）
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.handlers = []  # 清除已有handler

    # 控制台输出
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)

    if use_json:
        console_handler.setFormatter(JSONFormatter())
    else:
        console_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s - %(message)s"
            )
        )

    logger.addHandler(console_handler)

    # 文件输出
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(JSONFormatter())
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str = "adcast") -> logging.Logger:
    """获取日志记录器快捷函数"""
    logger = logging.getLogger(name)
    if not logger.handlers:
        return setup_logger(name)
    return logger


class PlatformLogAdapter:
    """平台日志适配器 - 自动添加平台相关字段"""

    def __init__(self, logger: logging.Logger, platform: str):
        self.logger = logger
        self.platform = platform

    def _log(self, level: int, msg: str, action: str = "", extra: Optional[Dict] = None, **kwargs):
        """内部日志方法"""
        merged_extra = {"platform": self.platform, "action": action}
        if extra:
            merged_extra.update(extra)

        # 通过kwargs设置额外属性
        for key, value in kwargs.items():
            merged_extra[key] = value

        # 创建LogRecord时传递extra
        log_kwargs = {"extra": {"platform": self.platform, "action": action}}
        if extra:
            log_kwargs["extra"].update(extra)

        self.logger.log(level, msg, **log_kwargs)

    def debug(self, msg: str, action: str = "", **kwargs):
        self._log(logging.DEBUG, msg, action, **kwargs)

    def info(self, msg: str, action: str = "", **kwargs):
        self._log(logging.INFO, msg, action, **kwargs)

    def warning(self, msg: str, action: str = "", **kwargs):
        self._log(logging.WARNING, msg, action, **kwargs)

    def error(self, msg: str, action: str = "", **kwargs):
        self._log(logging.ERROR, msg, action, **kwargs)

    def critical(self, msg: str, action: str = "", **kwargs):
        self._log(logging.CRITICAL, msg, action, **kwargs)
