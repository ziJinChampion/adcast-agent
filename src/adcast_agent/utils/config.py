"""
配置管理模块 - 支持YAML配置文件和环境变量覆盖
"""

import os
import yaml
from pathlib import Path
from typing import Any, Dict, Optional
from dataclasses import dataclass, field


@dataclass
class PlatformConfig:
    """单个平台的配置"""
    name: str
    enabled: bool = True
    mcp_server: Optional[str] = None  # MCP Server标识
    api_base_url: Optional[str] = None
    auth_type: str = "oauth2"  # oauth2 / api_key / token
    credentials: Dict[str, str] = field(default_factory=dict)
    budget_limit_daily: float = 0.0  # 每日预算上限 (0表示无限制)
    require_approval: bool = True  # 写入操作是否需要人工确认
    readonly: bool = False
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SecurityConfig:
    """安全控制配置"""
    global_budget_limit_daily: float = 10000.0  # 全局每日预算上限
    require_approval_for_create: bool = True
    require_approval_for_update: bool = True
    require_approval_for_delete: bool = True
    auto_pause_on_overspend: bool = True  # 超支自动暂停
    overspend_threshold: float = 1.1  # 超支阈值 (110%)
    max_retry_attempts: int = 3
    request_timeout: int = 30


@dataclass
class AgentConfig:
    """Agent全局配置"""
    name: str = "adcast-agent"
    log_level: str = "INFO"
    platforms: Dict[str, PlatformConfig] = field(default_factory=dict)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    decision_engine: Dict[str, Any] = field(default_factory=dict)


class ConfigManager:
    """配置管理器 - 加载和管理所有配置"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._config = None
        return cls._instance

    def __init__(self):
        if self._config is None:
            self._config = self._load_config()

    def _load_config(self) -> AgentConfig:
        """加载配置文件"""
        config_path = self._find_config_file()
        
        if config_path and config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                raw_config = yaml.safe_load(f)
        else:
            raw_config = self._default_config()

        # 环境变量覆盖
        raw_config = self._apply_env_overrides(raw_config)
        
        return self._parse_config(raw_config)

    def _find_config_file(self) -> Optional[Path]:
        """查找配置文件"""
        search_paths = [
            Path("config/settings.yaml"),
            Path("config/settings.yml"),
            Path(os.getenv("ADCAST_CONFIG", "")),
            Path.home() / ".adcast" / "settings.yaml",
        ]
        for path in search_paths:
            if path and path.exists():
                return path
        return None

    def _default_config(self) -> Dict[str, Any]:
        """默认配置"""
        return {
            "name": "adcast-agent",
            "log_level": "INFO",
            "platforms": {},
            "security": {
                "global_budget_limit_daily": 10000.0,
                "require_approval_for_create": True,
                "require_approval_for_update": True,
                "require_approval_for_delete": True,
            },
            "decision_engine": {
                "default_strategy": "roas_maximize",
                "min_budget_per_platform": 100.0,
            },
        }

    def _apply_env_overrides(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """应用环境变量覆盖"""
        # 日志级别
        if log_level := os.getenv("ADCAST_LOG_LEVEL"):
            config["log_level"] = log_level

        # 全局预算上限
        if budget := os.getenv("ADCAST_GLOBAL_BUDGET_LIMIT"):
            config.setdefault("security", {})["global_budget_limit_daily"] = float(budget)

        # 各平台凭证（格式: ADCAST_<PLATFORM>_<KEY>）
        for key, value in os.environ.items():
            if key.startswith("ADCAST_") and key.count("_") >= 2:
                parts = key.split("_")
                if len(parts) >= 3 and parts[1].lower() in [p.lower() for p in config.get("platforms", {})]:
                    platform_name = parts[1].lower()
                    cred_key = "_".join(parts[2:]).lower()
                    config["platforms"][platform_name].setdefault("credentials", {})[cred_key] = value

        return config

    def _parse_config(self, raw: Dict[str, Any]) -> AgentConfig:
        """解析原始配置为结构化配置"""
        platforms = {}
        for name, pconf in raw.get("platforms", {}).items():
            platforms[name] = PlatformConfig(name=name, **pconf)

        security = SecurityConfig(**raw.get("security", {}))

        return AgentConfig(
            name=raw.get("name", "adcast-agent"),
            log_level=raw.get("log_level", "INFO"),
            platforms=platforms,
            security=security,
            decision_engine=raw.get("decision_engine", {}),
        )

    @property
    def config(self) -> AgentConfig:
        return self._config

    def get_platform_config(self, name: str) -> Optional[PlatformConfig]:
        """获取指定平台配置"""
        return self._config.platforms.get(name.lower())

    def list_enabled_platforms(self) -> Dict[str, PlatformConfig]:
        """列出所有启用的平台"""
        return {
            name: pc for name, pc in self._config.platforms.items()
            if pc.enabled
        }


def get_config() -> AgentConfig:
    """获取全局配置快捷函数"""
    return ConfigManager().config
