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
    mcp_server: Optional[str] = None
    api_base_url: Optional[str] = None
    auth_type: str = "oauth2"
    credentials: Dict[str, str] = field(default_factory=dict)
    budget_limit_daily: float = 0.0
    require_approval: bool = True
    readonly: bool = False
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SecurityConfig:
    """安全控制配置"""
    global_budget_limit_daily: float = 10000.0
    require_approval_for_create: bool = True
    require_approval_for_update: bool = True
    require_approval_for_delete: bool = True
    auto_pause_on_overspend: bool = True
    overspend_threshold: float = 1.1
    max_retry_attempts: int = 3
    request_timeout: int = 30


@dataclass
class LLMConfig:
    """LLM配置"""
    provider: str = "openai"
    model: str = "gpt-4o"
    api_key: str = ""
    base_url: Optional[str] = None
    temperature: float = 0.3
    max_tokens: int = 4096


@dataclass
class CheckpointConfig:
    """Checkpoint配置"""
    backend: str = "memory"
    postgres: Dict[str, Any] = field(default_factory=lambda: {
        "host": "localhost",
        "port": 5432,
        "database": "adcast",
        "user": "adcast",
        "password": "",
        "table_name": "checkpoints",
    })


@dataclass
class LoopConfig:
    """Loop配置"""
    interval_minutes: int = 60
    max_iterations: int = 10
    auto_resume_after_pause: bool = False


@dataclass
class AgentConfig:
    """Agent全局配置"""
    name: str = "adcast-agent"
    log_level: str = "INFO"
    llm: LLMConfig = field(default_factory=LLMConfig)
    checkpoint: CheckpointConfig = field(default_factory=CheckpointConfig)
    loop: LoopConfig = field(default_factory=LoopConfig)
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
            "llm": {
                "provider": "openai",
                "model": "gpt-4o",
                "api_key": "",
                "base_url": None,
                "temperature": 0.3,
                "max_tokens": 4096,
            },
            "checkpoint": {
                "backend": "memory",
                "postgres": {
                    "host": "localhost",
                    "port": 5432,
                    "database": "adcast",
                    "user": "adcast",
                    "password": "",
                    "table_name": "checkpoints",
                },
            },
            "loop": {
                "interval_minutes": 60,
                "max_iterations": 10,
                "auto_resume_after_pause": False,
            },
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

        # LLM API Key
        if llm_key := os.getenv("ADCAST_LLM_API_KEY"):
            config.setdefault("llm", {})["api_key"] = llm_key

        # LLM Base URL
        if llm_url := os.getenv("ADCAST_LLM_BASE_URL"):
            config.setdefault("llm", {})["base_url"] = llm_url

        # Checkpoint PostgreSQL 密码
        if pg_password := os.getenv("ADCAST_PG_PASSWORD"):
            config.setdefault("checkpoint", {}).setdefault("postgres", {})["password"] = pg_password

        # Checkpoint 后端切换
        if cp_backend := os.getenv("ADCAST_CHECKPOINT_BACKEND"):
            config.setdefault("checkpoint", {})["backend"] = cp_backend

        # 各平台凭证
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
        # 解析LLM配置
        llm_raw = raw.get("llm", {})
        llm_config = LLMConfig(
            provider=llm_raw.get("provider", "openai"),
            model=llm_raw.get("model", "gpt-4o"),
            api_key=llm_raw.get("api_key", ""),
            base_url=llm_raw.get("base_url"),
            temperature=llm_raw.get("temperature", 0.3),
            max_tokens=llm_raw.get("max_tokens", 4096),
        )

        # 解析Checkpoint配置
        cp_raw = raw.get("checkpoint", {})
        checkpoint_config = CheckpointConfig(
            backend=cp_raw.get("backend", "memory"),
            postgres=cp_raw.get("postgres", {
                "host": "localhost",
                "port": 5432,
                "database": "adcast",
                "user": "adcast",
                "password": "",
                "table_name": "checkpoints",
            }),
        )

        # 解析Loop配置
        loop_raw = raw.get("loop", {})
        loop_config = LoopConfig(
            interval_minutes=loop_raw.get("interval_minutes", 60),
            max_iterations=loop_raw.get("max_iterations", 10),
            auto_resume_after_pause=loop_raw.get("auto_resume_after_pause", False),
        )

        # 解析平台配置
        platforms = {}
        for name, pconf in raw.get("platforms", {}).items():
            platforms[name] = PlatformConfig(name=name, **pconf)

        security = SecurityConfig(**raw.get("security", {}))

        return AgentConfig(
            name=raw.get("name", "adcast-agent"),
            log_level=raw.get("log_level", "INFO"),
            llm=llm_config,
            checkpoint=checkpoint_config,
            loop=loop_config,
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

    def get_llm_config(self) -> Dict[str, Any]:
        """获取LLM配置为字典"""
        return {
            "provider": self._config.llm.provider,
            "model": self._config.llm.model,
            "api_key": self._config.llm.api_key,
            "base_url": self._config.llm.base_url,
            "temperature": self._config.llm.temperature,
            "max_tokens": self._config.llm.max_tokens,
        }

    def get_checkpoint_config(self) -> Dict[str, Any]:
        """获取Checkpoint配置为字典"""
        return {
            "backend": self._config.checkpoint.backend,
            "postgres": self._config.checkpoint.postgres,
        }

    def get_loop_config(self) -> Dict[str, Any]:
        """获取Loop配置为字典"""
        return {
            "interval_minutes": self._config.loop.interval_minutes,
            "max_iterations": self._config.loop.max_iterations,
            "auto_resume_after_pause": self._config.loop.auto_resume_after_pause,
        }


def get_config() -> AgentConfig:
    """获取全局配置快捷函数"""
    return ConfigManager().config
