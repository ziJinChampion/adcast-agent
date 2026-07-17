"""
Google Ads MCP Connector

通过MCP Server连接Google Ads，支持：
- Campaign创建/更新/暂停/查询
- Ad Group管理
- 关键词管理
- 预算和出价调整
- 报表查询（GAQL）
- 受众管理

推荐MCP Server：
- 官方: github.com/googleads/google-ads-mcp (只读)
- 社区: github.com/FGRibreau/mcp-google-ads (读写)
- Pipeboard: google-ads.mcp.pipeboard.co
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
import logging

from ..base import (
    MCPAdPlatform, PlatformCampaign, PlatformReport, PlatformForecast,
    PlatformAudience, PlatformCreative, CampaignStatus, BudgetType,
    PlatformCapability,
)

logger = logging.getLogger("adcast.platform.google_ads")


class GoogleAdsConnector(MCPAdPlatform):
    """Google Ads MCP连接器"""

    # Campaign目标映射
    OBJECTIVE_MAP = {
        "conversions": " conversions",
        "awareness": "brand_awareness_and_reach",
        "traffic": "website_traffic",
        "app_installs": "app_promotion",
        "sales": "sales",
        "leads": "leads",
        "video_views": "video_views",
    }

    # 出价策略映射
    BID_STRATEGY_MAP = {
        "maximize_conversions": "maximizeConversions",
        "maximize_clicks": "maximizeClicks",
        "target_cpa": "targetCpa",
        "target_roas": "targetRoas",
        "manual_cpc": "manualCpc",
        "maximize_conversion_value": "maximizeConversionValue",
    }

    def __init__(self, config: Dict[str, Any], mcp_client=None):
        super().__init__("google_ads", config, mcp_client)

    def _init_capability(self) -> PlatformCapability:
        return PlatformCapability(
            platform="google_ads",
            supports_mcp=True,
            supports_api=True,
            supports_forecast=True,
            supports_auto_bidding=True,
            supports_audience=True,
            supports_creative_upload=True,
            supports_report=True,
            supported_objectives=[
                "conversions", "awareness", "traffic", "app_installs",
                "sales", "leads", "video_views",
            ],
            supported_creative_types=[
                "responsive_search_ad", "responsive_display_ad",
                "app_ad", "video_ad", "performance_max",
                "call_only_ad", "shopping_ad",
            ],
            min_budget=1.0,  # $1 USD
        )

    async def create_campaign(self, campaign: PlatformCampaign) -> Dict[str, Any]:
        """创建Google Ads Campaign"""
        # 默认PAUSED
        status = "PAUSED" if campaign.status == CampaignStatus.PAUSED else "ENABLED"
        
        params = {
            "name": campaign.name,
            "status": status,
            "advertising_channel_type": self._get_channel_type(campaign.objective),
            "budget": {
                "amount_micros": int(campaign.budget_amount * 1000000),
                "delivery_method": "STANDARD",
            },
        }

        # 出价策略
        if campaign.bid_strategy:
            bid_strategy = self.BID_STRATEGY_MAP.get(campaign.bid_strategy)
            if bid_strategy:
                params["bidding_strategy_type"] = bid_strategy

        # 目标CPA/ROAS
        if campaign.bid_amount and campaign.bid_strategy in ("target_cpa", "target_roas"):
            params["target_cpa_micros"] = int(campaign.bid_amount * 1000000)

        # 时间设置
        if campaign.start_time:
            params["start_date"] = campaign.start_time.strftime("%Y-%m-%d")
        if campaign.end_time:
            params["end_date"] = campaign.end_time.strftime("%Y-%m-%d")

        result = await self._call_mcp("create_campaign", **params)
        
        if "error" not in result:
            logger.info(f"Created Google Ads campaign: {result.get('campaign_id')}")
        else:
            logger.error(f"Failed to create Google Ads campaign: {result['error']}")
        
        return result

    async def update_campaign(self, campaign_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """更新Campaign"""
        params = {"campaign_id": campaign_id, **updates}
        return await self._call_mcp("update_campaign", **params)

    async def delete_campaign(self, campaign_id: str) -> bool:
        """归档Campaign（Google Ads不支持真正删除）"""
        result = await self._call_mcp("update_campaign_status",
            campaign_id=campaign_id, status="REMOVED")
        return "error" not in result

    async def update_campaign_status(self, campaign_id: str, status: CampaignStatus) -> bool:
        """更新Campaign状态"""
        status_map = {
            CampaignStatus.ENABLED: "ENABLED",
            CampaignStatus.PAUSED: "PAUSED",
            CampaignStatus.REMOVED: "REMOVED",
        }
        result = await self._call_mcp("update_campaign_status",
            campaign_id=campaign_id,
            status=status_map.get(status, "PAUSED"))
        return "error" not in result

    async def list_campaigns(self, status: Optional[CampaignStatus] = None) -> List[PlatformCampaign]:
        """列出Campaign"""
        params = {}
        if status:
            params["status"] = status.value.upper()
        
        result = await self._call_mcp("list_campaigns", **params)
        campaigns = []
        
        for item in result.get("campaigns", []):
            campaigns.append(self._parse_campaign(item))
        
        return campaigns

    async def get_campaign(self, campaign_id: str) -> Optional[PlatformCampaign]:
        """获取Campaign详情"""
        result = await self._call_mcp("get_campaign", campaign_id=campaign_id)
        if "error" in result:
            return None
        return self._parse_campaign(result)

    async def get_report(
        self,
        campaign_ids: Optional[List[str]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        granularity: str = "daily",
    ) -> List[PlatformReport]:
        """获取GAQL报表"""
        params = {}
        if campaign_ids:
            params["campaign_ids"] = campaign_ids
        if start_date:
            params["start_date"] = start_date.strftime("%Y-%m-%d")
        if end_date:
            params["end_date"] = end_date.strftime("%Y-%m-%d")
        params["granularity"] = granularity

        result = await self._call_mcp("get_campaign_report", **params)
        reports = []
        
        for item in result.get("rows", []):
            reports.append(PlatformReport(
                platform="google_ads",
                campaign_id=str(item.get("campaign_id", "")),
                date=datetime.strptime(item["date"], "%Y-%m-%d") if "date" in item else None,
                impressions=item.get("impressions", 0),
                clicks=item.get("clicks", 0),
                spend=item.get("cost_micros", 0) / 1000000,
                conversions=item.get("conversions", 0),
                ctr=item.get("ctr", 0) * 100,
                cpc=item.get("average_cpc", 0) / 1000000,
                cpm=item.get("average_cpm", 0) / 1000000,
                reach=item.get("reach", 0),
                roas=item.get("conversions_value_per_cost", 0),
                extra=item,
            ))
        
        return reports

    async def get_forecast(self, campaign: PlatformCampaign) -> PlatformForecast:
        """获取投放预测（Keyword Planner）"""
        params = {
            "objective": campaign.objective,
            "budget": campaign.budget_amount,
        }
        if campaign.audience:
            params["geo_locations"] = campaign.audience.geo_locations

        result = await self._call_mcp("get_forecast", **params)
        
        if "error" in result:
            return PlatformForecast(platform="google_ads")

        return PlatformForecast(
            platform="google_ads",
            estimated_reach=result.get("reach", 0),
            estimated_impressions=result.get("impressions", 0),
            estimated_cpm=result.get("cpm", 0),
            estimated_cpc=result.get("cpc", 0),
            estimated_ctr=result.get("ctr", 0) * 100,
            estimated_conversions=result.get("conversions", 0),
            estimated_cpa=result.get("cpa", 0),
            estimated_roas=result.get("roas", 0),
            audience_size=result.get("audience_size", 0),
            confidence=result.get("confidence", "medium"),
        )

    async def create_ad_group(self, campaign_id: str, name: str,
                             bid_amount: float, **kwargs) -> Dict[str, Any]:
        """创建Ad Group"""
        return await self._call_mcp("create_ad_group",
            campaign_id=campaign_id,
            name=name,
            cpc_bid_micros=int(bid_amount * 1000000),
            **kwargs)

    async def add_keywords(self, ad_group_id: str, keywords: List[Dict[str, str]]) -> Dict[str, Any]:
        """添加关键词"""
        return await self._call_mcp("add_keywords",
            ad_group_id=ad_group_id,
            keywords=keywords)

    async def health_check(self) -> bool:
        """健康检查"""
        result = await self._call_mcp("list_accessible_accounts")
        return "error" not in result

    def _parse_campaign(self, data: Dict) -> PlatformCampaign:
        """解析Campaign数据"""
        status_map = {
            "ENABLED": CampaignStatus.ENABLED,
            "PAUSED": CampaignStatus.PAUSED,
            "REMOVED": CampaignStatus.REMOVED,
        }
        
        return PlatformCampaign(
            id=str(data.get("campaign_id", data.get("id", ""))),
            name=data.get("name"),
            status=status_map.get(data.get("status", "PAUSED"), CampaignStatus.PAUSED),
            objective=data.get("advertising_channel_type", ""),
            budget_amount=(data.get("budget_amount_micros", 0) / 1000000),
            platform="google_ads",
            extra=data,
        )

    def _get_channel_type(self, objective: Optional[str]) -> str:
        """获取广告渠道类型"""
        channel_map = {
            "conversions": "SEARCH",
            "awareness": "DISPLAY",
            "traffic": "SEARCH",
            "app_installs": "MULTI_CHANNEL",
            "sales": "SHOPPING",
            "leads": "SEARCH",
            "video_views": "VIDEO",
        }
        return channel_map.get(objective, "SEARCH")
