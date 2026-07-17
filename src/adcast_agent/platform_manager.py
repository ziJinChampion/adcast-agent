"""
平台管理器 - 负责初始化和连接所有广告平台

职责：
1. 根据配置创建平台连接器/适配器
2. 建立MCP连接
3. 管理平台生命周期
"""

from typing import Dict, Optional
import logging

from .utils.config import AgentConfig, PlatformConfig
from .mcp.registry import MCPRegistry
from .platforms.base import BaseAdPlatform
from .platforms.google_ads.connector import GoogleAdsConnector
from .platforms.meta_ads.connector import MetaAdsConnector
from .platforms.amazon_dsp.connector import AmazonDSPConnector
from .platforms.adform.connector import AdformConnector
from .platforms.oceanengine.connector import OceanEngineConnector
from .platforms.tencent_ads.adapter import TencentAdsAdapter
from .platforms.kuaishou.adapter import KuaishouAdapter
from .platforms.baidu_ads.adapter import BaiduAdsAdapter

logger = logging.getLogger("adcast.platform_manager")


class PlatformManager:
    """平台管理器"""

    # 平台工厂映射
    PLATFORM_FACTORIES = {
        "google_ads": GoogleAdsConnector,
        "meta_ads": MetaAdsConnector,
        "amazon_dsp": AmazonDSPConnector,
        "adform": AdformConnector,
        "oceanengine": OceanEngineConnector,
        "tencent_ads": TencentAdsAdapter,
        "kuaishou": KuaishouAdapter,
        "baidu_ads": BaiduAdsAdapter,
    }

    def __init__(self, registry: MCPRegistry, config: AgentConfig):
        self.registry = registry
        self.config = config
        self._platforms: Dict[str, BaseAdPlatform] = {}

    async def initialize_all(self):
        """初始化所有配置的平台"""
        for name, pconf in self.config.platforms.items():
            if not pconf.enabled:
                continue

            try:
                await self._init_platform(name, pconf)
            except Exception as e:
                logger.error(f"Failed to initialize platform '{name}': {e}")

    async def _init_platform(self, name: str, pconf: PlatformConfig):
        """初始化单个平台"""
        factory = self.PLATFORM_FACTORIES.get(name)
        if not factory:
            logger.warning(f"Unknown platform: {name}")
            return

        logger.info(f"Initializing platform: {name}")

        # 转换配置为字典
        config_dict = {
            "enabled": pconf.enabled,
            "mcp_server": pconf.mcp_server,
            "api_base_url": pconf.api_base_url,
            "auth_type": pconf.auth_type,
            "credentials": pconf.credentials,
            "budget_limit_daily": pconf.budget_limit_daily,
            "require_approval": pconf.require_approval,
            "readonly": pconf.readonly,
            **pconf.extra,
        }

        # 检查是否需要MCP连接
        mcp_client = None
        if pconf.mcp_server:
            mcp_client = await self._connect_mcp(name, pconf)
            if not mcp_client:
                logger.warning(f"Failed to connect MCP for {name}, skipping")
                return

        # 创建平台实例
        if name in ("tencent_ads", "kuaishou", "baidu_ads"):
            # API Adapter平台不需要MCP client
            platform = factory(config=config_dict)
        else:
            # MCP平台需要MCP client
            platform = factory(config=config_dict, mcp_client=mcp_client)

        # 健康检查
        try:
            healthy = await platform.health_check()
            if not healthy:
                logger.warning(f"Platform {name} health check failed")
                return
        except Exception as e:
            logger.warning(f"Platform {name} health check error: {e}")
            # 继续，某些平台健康检查可能需要额外权限

        self._platforms[name] = platform
        logger.info(f"Platform '{name}' initialized successfully (MCP={platform.is_mcp()})")

    async def _connect_mcp(self, name: str, pconf: PlatformConfig) -> Optional[object]:
        """
        连接MCP Server
        
        支持两种方式：
        1. HTTP MCP（如巨量引擎、Pipeboard）
        2. Stdio MCP（如Google Ads官方MCP）
        """
        from .mcp.client import MCPClient, stdio_client, http_client

        try:
            if pconf.mcp_server.startswith("http"):
                # HTTP MCP
                headers = {}
                if pconf.credentials.get("access_token"):
                    headers["Authorization"] = f"Bearer {pconf.credentials['access_token']}"
                
                client = http_client(name, pconf.mcp_server, headers=headers)
                await client.connect()
                
                if client.is_connected:
                    self.registry.register(name, client)
                    logger.info(f"Connected to {name} MCP via HTTP ({client.tool_count} tools)")
                    return client
            else:
                # Stdio MCP - mcp_server是命令
                cmd = pconf.mcp_server
                args = pconf.extra.get("mcp_args", [])
                env = pconf.credentials if pconf.credentials else None
                
                client = stdio_client(name, cmd, args=args, env=env)
                await client.connect()
                
                if client.is_connected:
                    self.registry.register(name, client)
                    logger.info(f"Connected to {name} MCP via stdio ({client.tool_count} tools)")
                    return client

        except Exception as e:
            logger.error(f"MCP connection failed for {name}: {e}")

        return None

    def get_platforms(self) -> Dict[str, BaseAdPlatform]:
        """获取所有已初始化的平台"""
        return self._platforms

    def get_platform(self, name: str) -> Optional[BaseAdPlatform]:
        """获取指定平台"""
        return self._platforms.get(name)

    def list_platforms(self) -> list:
        """列出所有平台名称"""
        return list(self._platforms.keys())
