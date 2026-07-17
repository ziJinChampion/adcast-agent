"""
MCP Server 注册表 - 管理多个平台的MCP连接
"""

import asyncio
from typing import Dict, List, Optional
import logging

from .client import MCPClient, MCPResult

logger = logging.getLogger("adcast.mcp")


class MCPRegistry:
    """
    MCP注册表 - 统一管理所有广告平台的MCP连接
    
    负责：
    1. 注册和管理各平台的MCP客户端
    2. 提供统一的多平台调用接口
    3. 健康检查和连接恢复
    """

    def __init__(self):
        self._clients: Dict[str, MCPClient] = {}
        self._connected: Dict[str, bool] = {}

    def register(self, platform: str, client: MCPClient) -> "MCPRegistry":
        """
        注册一个平台的MCP客户端
        
        Args:
            platform: 平台名称 (如 'google_ads', 'meta_ads', 'oceanengine')
            client: MCPClient实例
        """
        self._clients[platform] = client
        self._connected[platform] = False
        logger.info(f"Registered MCP client for {platform}")
        return self

    async def connect_all(self):
        """连接所有已注册的MCP Server"""
        tasks = []
        for platform, client in self._clients.items():
            tasks.append(self._connect_one(platform, client))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        success = sum(1 for r in results if not isinstance(r, Exception))
        total = len(self._clients)
        logger.info(f"MCP connections: {success}/{total} successful")

    async def _connect_one(self, platform: str, client: MCPClient):
        """连接单个MCP Server"""
        try:
            await client.connect()
            self._connected[platform] = True
            logger.info(f"Connected to {platform} MCP ({client.tool_count} tools)")
        except Exception as e:
            self._connected[platform] = False
            logger.error(f"Failed to connect {platform} MCP: {e}")

    async def disconnect_all(self):
        """断开所有连接"""
        for platform, client in self._clients.items():
            try:
                await client.disconnect()
                self._connected[platform] = False
            except Exception as e:
                logger.warning(f"Error disconnecting {platform}: {e}")

    async def call(self, platform: str, tool: str, **kwargs) -> MCPResult:
        """
        调用指定平台的MCP工具
        
        Args:
            platform: 平台名称
            tool: 工具名称
            **kwargs: 工具参数
        """
        if platform not in self._clients:
            return MCPResult(success=False, error=f"Platform '{platform}' not registered")
        
        if not self._connected.get(platform):
            return MCPResult(success=False, error=f"Platform '{platform}' not connected")
        
        client = self._clients[platform]
        return await client.call(tool, **kwargs)

    async def call_all(self, tool: str, **kwargs) -> Dict[str, MCPResult]:
        """
        在所有已连接平台上调用同一工具
        
        适用于获取跨平台报表等场景
        """
        tasks = {}
        for platform, connected in self._connected.items():
            if connected:
                tasks[platform] = self.call(platform, tool, **kwargs)
        
        results = {}
        for platform, task in tasks.items():
            try:
                results[platform] = await task
            except Exception as e:
                results[platform] = MCPResult(success=False, error=str(e))
        
        return results

    def get_connected_platforms(self) -> List[str]:
        """获取所有已连接的平台列表"""
        return [p for p, c in self._connected.items() if c]

    def get_platform_tools(self, platform: str) -> List[str]:
        """获取指定平台的可用工具列表"""
        if platform in self._clients:
            return self._clients[platform].list_tools()
        return []

    def is_connected(self, platform: str) -> bool:
        """检查平台是否已连接"""
        return self._connected.get(platform, False)

    def __contains__(self, platform: str) -> bool:
        return platform in self._clients

    def __len__(self) -> int:
        return len(self._clients)
