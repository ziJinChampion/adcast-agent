"""
广告平台基类 - 定义所有平台的统一接口

所有平台（无论是通过MCP直连还是自研Adapter）都需实现此接口，
确保上层决策引擎可以无差别调用。
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class CampaignStatus(Enum):
    """Campaign状态"""
    ENABLED = "enabled"
    PAUSED = "paused"
    REMOVED = "removed"
    PENDING = "pending"


class BudgetType(Enum):
    """预算类型"""
    DAILY = "daily"
    LIFETIME = "lifetime"


@dataclass
class PlatformAudience:
    """受众定向"""
    age_min: Optional[int] = None
    age_max: Optional[int] = None
    genders: List[str] = field(default_factory=list)
    geo_locations: List[str] = field(default_factory=list)
    interests: List[str] = field(default_factory=list)
    behaviors: List[str] = field(default_factory=list)
    custom_audiences: List[str] = field(default_factory=list)
    lookalike_audiences: List[str] = field(default_factory=list)
    languages: List[str] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PlatformCreative:
    """广告创意"""
    name: str
    type: str  # image, video, carousel, text, etc.
    title: Optional[str] = None
    body: Optional[str] = None
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    call_to_action: Optional[str] = None
    link_url: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PlatformCampaign:
    """Campaign数据模型"""
    id: Optional[str] = None
    name: Optional[str] = None
    status: CampaignStatus = CampaignStatus.PAUSED
    objective: Optional[str] = None  # conversions, awareness, traffic, etc.
    budget_type: BudgetType = BudgetType.DAILY
    budget_amount: float = 0.0
    bid_strategy: Optional[str] = None  # lowest_cost, cost_cap, etc.
    bid_amount: Optional[float] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    audience: Optional[PlatformAudience] = None
    creatives: List[PlatformCreative] = field(default_factory=list)
    platform: Optional[str] = None  # 平台名称
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PlatformReport:
    """报表数据模型"""
    platform: str
    campaign_id: Optional[str] = None
    date: Optional[datetime] = None
    impressions: int = 0
    clicks: int = 0
    spend: float = 0.0
    conversions: int = 0
    revenue: float = 0.0
    ctr: float = 0.0
    cpc: float = 0.0
    cpm: float = 0.0
    roas: float = 0.0
    cpa: float = 0.0
    reach: int = 0
    frequency: float = 0.0
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PlatformForecast:
    """投放预测结果"""
    platform: str
    estimated_reach: int = 0
    estimated_impressions: int = 0
    estimated_cpm: float = 0.0
    estimated_cpc: float = 0.0
    estimated_ctr: float = 0.0
    estimated_conversions: int = 0
    estimated_cpa: float = 0.0
    estimated_roas: float = 0.0
    budget_suggestion: float = 0.0
    audience_size: int = 0
    competition_level: str = "medium"  # low, medium, high
    confidence: str = "medium"  # low, medium, high
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PlatformCapability:
    """平台能力描述"""
    platform: str
    supports_mcp: bool = False
    supports_api: bool = True
    supports_forecast: bool = False
    supports_auto_bidding: bool = False
    supports_audience: bool = True
    supports_creative_upload: bool = False
    supports_report: bool = True
    supported_objectives: List[str] = field(default_factory=list)
    supported_creative_types: List[str] = field(default_factory=list)
    min_budget: float = 0.0


class BaseAdPlatform(ABC):
    """
    广告平台抽象基类
    
    所有平台（MCP直连和自研Adapter）都必须实现此接口。
    提供统一的Campaign CRUD、报表查询、受众预估等能力。
    """

    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self.capability = self._init_capability()

    @abstractmethod
    def _init_capability(self) -> PlatformCapability:
        """初始化平台能力描述"""
        pass

    @abstractmethod
    async def create_campaign(self, campaign: PlatformCampaign) -> Dict[str, Any]:
        """
        创建Campaign
        
        所有新创建的Campaign必须默认状态为PAUSED，
        需要额外调用update_campaign_status才能启用。
        """
        pass

    @abstractmethod
    async def update_campaign(self, campaign_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """更新Campaign"""
        pass

    @abstractmethod
    async def delete_campaign(self, campaign_id: str) -> bool:
        """删除/归档Campaign"""
        pass

    @abstractmethod
    async def update_campaign_status(self, campaign_id: str, status: CampaignStatus) -> bool:
        """更新Campaign状态（暂停/启用）"""
        pass

    @abstractmethod
    async def list_campaigns(self, status: Optional[CampaignStatus] = None) -> List[PlatformCampaign]:
        """列出Campaign"""
        pass

    @abstractmethod
    async def get_campaign(self, campaign_id: str) -> Optional[PlatformCampaign]:
        """获取Campaign详情"""
        pass

    @abstractmethod
    async def get_report(
        self,
        campaign_ids: Optional[List[str]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        granularity: str = "daily",  # daily, hourly, weekly
    ) -> List[PlatformReport]:
        """获取报表数据"""
        pass

    async def get_forecast(self, campaign: PlatformCampaign) -> PlatformForecast:
        """
        获取投放预测
        
        并非所有平台都支持，默认返回空预测。
        """
        return PlatformForecast(platform=self.name)

    @abstractmethod
    async def health_check(self) -> bool:
        """健康检查"""
        pass

    def is_mcp(self) -> bool:
        """是否使用MCP协议"""
        return self.capability.supports_mcp

    def get_name(self) -> str:
        """获取平台名称"""
        return self.name

    def get_capability(self) -> PlatformCapability:
        """获取平台能力"""
        return self.capability

    def supports_objective(self, objective: str) -> bool:
        """检查是否支持指定投放目标"""
        return objective in self.capability.supported_objectives

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}', mcp={self.is_mcp()})"


class MCPAdPlatform(BaseAdPlatform):
    """
    MCP直连平台基类
    
    适用于Google Ads、Meta Ads、Amazon DSP、Adform、巨量引擎等
    提供MCP Server的平台。
    """

    def __init__(self, name: str, config: Dict[str, Any], mcp_client=None):
        super().__init__(name, config)
        self.mcp_client = mcp_client
        self._mcp_tool_prefix = config.get("mcp_tool_prefix", "")

    def _build_tool_name(self, action: str) -> str:
        """构建MCP工具名称"""
        if self._mcp_tool_prefix:
            return f"{self._mcp_tool_prefix}_{action}"
        return action

    async def _call_mcp(self, tool: str, **kwargs) -> Dict[str, Any]:
        """调用MCP工具"""
        if not self.mcp_client:
            return {"error": "MCP client not initialized"}
        
        from ..mcp.client import MCPResult
        result = await self.mcp_client.call(tool, **kwargs)
        
        if result.success:
            return result.data or {}
        return {"error": result.error}

    def is_mcp(self) -> bool:
        return True


class APIAdPlatform(BaseAdPlatform):
    """
    API适配平台基类
    
    适用于没有MCP Server、需自研Adapter的平台。
    子类需实现HTTP API调用逻辑。
    """

    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.api_base_url = config.get("api_base_url", "")
        self.credentials = config.get("credentials", {})
        self._session = None

    async def _ensure_session(self):
        """确保HTTP会话已创建"""
        if self._session is None:
            import aiohttp
            self._session = aiohttp.ClientSession(
                headers=self._build_headers(),
                timeout=aiohttp.ClientTimeout(total=30),
            )

    def _build_headers(self) -> Dict[str, str]:
        """构建API请求头 - 子类需覆盖"""
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _api_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        data: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        发送API请求
        
        Args:
            method: HTTP方法 (GET, POST, PUT, DELETE)
            endpoint: API端点路径
            params: URL查询参数
            data: 请求体数据
        """
        await self._ensure_session()
        
        url = f"{self.api_base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        
        try:
            async with self._session.request(
                method=method,
                url=url,
                params=params,
                json=data,
            ) as resp:
                if resp.status in (200, 201):
                    return await resp.json()
                else:
                    text = await resp.text()
                    return {"error": f"HTTP {resp.status}: {text}"}
        except Exception as e:
            return {"error": str(e)}

    async def close(self):
        """关闭HTTP会话"""
        if self._session:
            await self._session.close()
            self._session = None

    def is_mcp(self) -> bool:
        return False
