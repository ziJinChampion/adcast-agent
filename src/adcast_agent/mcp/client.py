"""
MCP 客户端模块 - 支持 stdio 和 HTTP 两种传输方式

支持两种MCP Server连接方式：
1. stdio: 本地运行MCP Server进程（命令行方式）
2. HTTP: 远程MCP Server（Streamable HTTP方式）
"""

import asyncio
import json
import subprocess
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, AsyncGenerator
from dataclasses import dataclass, field
from contextlib import asynccontextmanager

logger = logging.getLogger("adcast.mcp")


@dataclass
class MCPTool:
    """MCP工具描述"""
    name: str
    description: str
    input_schema: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MCPResource:
    """MCP资源描述"""
    uri: str
    name: str
    mime_type: str = "application/json"


@dataclass
class MCPResult:
    """MCP调用结果"""
    success: bool
    data: Any = None
    error: Optional[str] = None


class MCPTransport(ABC):
    """MCP传输层抽象基类"""

    @abstractmethod
    async def connect(self):
        """建立连接"""
        pass

    @abstractmethod
    async def disconnect(self):
        """断开连接"""
        pass

    @abstractmethod
    async def send_request(self, method: str, params: Optional[Dict] = None) -> Dict:
        """发送JSON-RPC请求"""
        pass

    @abstractmethod
    async def list_tools(self) -> List[MCPTool]:
        """列出可用工具"""
        pass

    @abstractmethod
    async def call_tool(self, name: str, arguments: Optional[Dict] = None) -> MCPResult:
        """调用工具"""
        pass

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """是否已连接"""
        pass


class StdioTransport(MCPTransport):
    """
    stdio传输实现 - 通过子进程stdin/stdout与MCP Server通信
    
    适用于本地运行的MCP Server，如：
    - npx pipeboard-mcp-server
    - uvx some-mcp-server
    """

    def __init__(self, command: str, args: List[str] = None, env: Optional[Dict[str, str]] = None):
        self.command = command
        self.args = args or []
        self.env = env
        self._process: Optional[subprocess.Popen] = None
        self._is_connected = False
        self._request_id = 0

    async def connect(self):
        """启动MCP Server子进程"""
        try:
            self._process = subprocess.Popen(
                [self.command] + self.args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=self.env,
            )
            self._is_connected = True
            logger.info(f"stdio MCP Server started: {self.command}")

            # 初始化握手（JSON-RPC）
            await self._initialize()
        except Exception as e:
            logger.error(f"Failed to start stdio MCP Server: {e}")
            self._is_connected = False
            raise

    async def disconnect(self):
        """终止子进程"""
        if self._process:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
            self._process = None
        self._is_connected = False
        logger.info("stdio MCP Server stopped")

    async def _initialize(self):
        """JSON-RPC初始化"""
        init_request = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "adcast-agent", "version": "0.1.0"},
            },
        }
        await self._send_raw(json.dumps(init_request))
        response = await self._recv_raw()
        logger.debug(f"MCP init response: {response}")

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    async def _send_raw(self, data: str):
        """发送原始数据"""
        if self._process and self._process.stdin:
            self._process.stdin.write(data + "\n")
            self._process.stdin.flush()

    async def _recv_raw(self) -> str:
        """接收原始数据"""
        if self._process and self._process.stdout:
            return self._process.stdout.readline().strip()
        return ""

    async def send_request(self, method: str, params: Optional[Dict] = None) -> Dict:
        """发送JSON-RPC请求"""
        request = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": method,
            "params": params or {},
        }
        await self._send_raw(json.dumps(request))
        response = await self._recv_raw()
        return json.loads(response) if response else {}

    async def list_tools(self) -> List[MCPTool]:
        """列出可用工具"""
        response = await self.send_request("tools/list")
        tools = []
        for tool_data in response.get("result", {}).get("tools", []):
            tools.append(MCPTool(
                name=tool_data["name"],
                description=tool_data.get("description", ""),
                input_schema=tool_data.get("inputSchema", {}),
            ))
        return tools

    async def call_tool(self, name: str, arguments: Optional[Dict] = None) -> MCPResult:
        """调用工具"""
        try:
            response = await self.send_request(
                "tools/call",
                {"name": name, "arguments": arguments or {}},
            )
            result = response.get("result", {})
            return MCPResult(success=True, data=result)
        except Exception as e:
            return MCPResult(success=False, error=str(e))

    @property
    def is_connected(self) -> bool:
        return self._is_connected and self._process is not None


class HTTPTransport(MCPTransport):
    """
    HTTP传输实现 - 通过HTTP与远程MCP Server通信
    
    适用于：
    - 巨量引擎官方MCP（Streamable HTTP）
    - Pipeboard等托管MCP服务
    """

    def __init__(self, base_url: str, headers: Optional[Dict[str, str]] = None):
        self.base_url = base_url.rstrip("/")
        self.headers = headers or {}
        self._session = None
        self._is_connected = False

    async def connect(self):
        """建立HTTP连接"""
        try:
            import aiohttp
            self._session = aiohttp.ClientSession(
                headers=self.headers,
                timeout=aiohttp.ClientTimeout(total=30),
            )
            self._is_connected = True
            logger.info(f"HTTP MCP connected: {self.base_url}")
        except ImportError:
            logger.error("aiohttp is required for HTTP transport. Install: pip install aiohttp")
            raise

    async def disconnect(self):
        """关闭HTTP连接"""
        if self._session:
            await self._session.close()
            self._session = None
        self._is_connected = False
        logger.info("HTTP MCP disconnected")

    async def send_request(self, method: str, params: Optional[Dict] = None) -> Dict:
        """发送HTTP POST请求"""
        if not self._session:
            return {}
        
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
        }
        
        try:
            async with self._session.post(
                f"{self.base_url}/mcp",
                json=payload,
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    text = await resp.text()
                    logger.error(f"HTTP MCP error {resp.status}: {text}")
                    return {"error": f"HTTP {resp.status}: {text}"}
        except Exception as e:
            logger.error(f"HTTP MCP request failed: {e}")
            return {"error": str(e)}

    async def list_tools(self) -> List[MCPTool]:
        """列出可用工具"""
        response = await self.send_request("tools/list")
        tools = []
        for tool_data in response.get("result", {}).get("tools", []):
            tools.append(MCPTool(
                name=tool_data["name"],
                description=tool_data.get("description", ""),
                input_schema=tool_data.get("inputSchema", {}),
            ))
        return tools

    async def call_tool(self, name: str, arguments: Optional[Dict] = None) -> MCPResult:
        """调用工具"""
        try:
            response = await self.send_request(
                "tools/call",
                {"name": name, "arguments": arguments or {}},
            )
            if "error" in response:
                return MCPResult(success=False, error=response["error"])
            return MCPResult(success=True, data=response.get("result"))
        except Exception as e:
            return MCPResult(success=False, error=str(e))

    @property
    def is_connected(self) -> bool:
        return self._is_connected and self._session is not None


class MCPClient:
    """
    MCP客户端统一入口
    
    根据配置自动选择合适的传输方式，提供统一的工具调用接口。
    """

    def __init__(self, name: str, transport: MCPTransport):
        self.name = name
        self.transport = transport
        self._tools: List[MCPTool] = []
        self._tools_cache: Dict[str, MCPTool] = {}

    async def connect(self):
        """连接MCP Server"""
        await self.transport.connect()
        await self._refresh_tools()

    async def disconnect(self):
        """断开连接"""
        await self.transport.disconnect()

    async def _refresh_tools(self):
        """刷新工具列表"""
        self._tools = await self.transport.list_tools()
        self._tools_cache = {t.name: t for t in self._tools}
        logger.info(f"MCP {self.name}: loaded {len(self._tools)} tools")

    async def call(self, tool_name: str, **kwargs) -> MCPResult:
        """
        调用指定工具
        
        Args:
            tool_name: 工具名称
            **kwargs: 工具参数
            
        Returns:
            MCPResult: 调用结果
        """
        if tool_name not in self._tools_cache:
            await self._refresh_tools()
        
        if tool_name not in self._tools_cache:
            return MCPResult(success=False, error=f"Tool '{tool_name}' not found")

        tool = self._tools_cache[tool_name]
        logger.debug(f"Calling {self.name}/{tool_name}: {kwargs}")
        
        result = await self.transport.call_tool(tool_name, kwargs)
        
        if result.success:
            logger.debug(f"{self.name}/{tool_name} succeeded")
        else:
            logger.warning(f"{self.name}/{tool_name} failed: {result.error}")
        
        return result

    async def call_batch(self, calls: List[Dict[str, Any]]) -> List[MCPResult]:
        """
        批量调用工具
        
        Args:
            calls: 调用列表，每个元素为 {"tool": str, "args": dict}
            
        Returns:
            List[MCPResult]: 调用结果列表
        """
        tasks = []
        for call in calls:
            tasks.append(self.call(call["tool"], **call.get("args", {})))
        return await asyncio.gather(*tasks, return_exceptions=True)

    def list_tools(self) -> List[str]:
        """列出可用工具名称"""
        return [t.name for t in self._tools]

    def get_tool_info(self, tool_name: str) -> Optional[MCPTool]:
        """获取工具详细信息"""
        return self._tools_cache.get(tool_name)

    @property
    def is_connected(self) -> bool:
        return self.transport.is_connected

    @property
    def tool_count(self) -> int:
        return len(self._tools)


# 快捷函数

def stdio_client(name: str, command: str, args: List[str] = None, env: Optional[Dict] = None) -> MCPClient:
    """创建stdio MCP客户端"""
    transport = StdioTransport(command=command, args=args, env=env)
    return MCPClient(name=name, transport=transport)


def http_client(name: str, base_url: str, headers: Optional[Dict[str, str]] = None) -> MCPClient:
    """创建HTTP MCP客户端"""
    transport = HTTPTransport(base_url=base_url, headers=headers)
    return MCPClient(name=name, transport=transport)
