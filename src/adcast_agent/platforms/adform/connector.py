"""
Adform FLOW MCP Connector

通过MCP Server连接Adform FLOW，支持：
- Campaign全生命周期管理
- 受众和数据管理（DMP）
- 创意管理
- 跨渠道报表
- Flight中优化

Adform MCP特点：
- 2026年5月发布，800+ agentic capabilities
- 支持Claude, ChatGPT, Microsoft Copilot
- 全栈平台（DSP + Ad Server + DMP）
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
import logging

from ..base import (
    MCPAdPlatform, PlatformCampaign, PlatformReport, PlatformForecast,
    PlatformAudience, CampaignStatus, PlatformCapability,
)

logger = logging.getLogger("adcast.platform.adform")


class AdformConnector(MCPAdPlatform):
    """Adform FLOW MCP连接器"""

    def __init__(self, config: Dict[str, Any], mcp_client=None):
        super().__init__("adform", config, mcp_client)

    def _init_capability(self) -> PlatformCapability:
        return PlatformCapability(
            platform="adform",
            supports_mcp=True,
            supports_api=True,
            supports_forecast=True,
            supports_auto_bidding=True,
            supports_audience=True,
            supports_creative_upload=True,
            supports_report=True,
            supported_objectives=[
                "conversions", "awareness", "traffic", "video_views",
                "app_installs", "sales", "retargeting",
            ],
            supported_creative_types=[
                "display", "video", "audio", "native", "ctv",
            ],
            min_budget=1000.0,
        )

    async def create_campaign(self, campaign: PlatformCampaign) -> Dict[str, Any]:
        """创建Adform Campaign"""
        status = "INACTIVE" if campaign.status == CampaignStatus.PAUSED else "ACTIVE"

        params = {
            "name": campaign.name,
            "status": status,
            "budget": {
                "total": campaign.budget_amount,
                "period": "DAILY" if campaign.budget_type == BudgetType.DAILY else "TOTAL",
            },
        }

        # 目标
        goal_map = {
            "conversions": "CONVERSION",
            "awareness": "AWARENESS",
            "traffic": "CLICKS",
            "video_views": "VIDEO_VIEWS",
            "sales": "SALES",
            "app_installs": "APP_INSTALLS",
        }
        if campaign.objective:
            params["goal"] = goal_map.get(campaign.objective, "CONVERSION")

        # 出价
        if campaign.bid_strategy == "cpm":
            params["pricing_model"] = "CPM"
        elif campaign.bid_strategy == "cpc":
            params["pricing_model"] = "CPC"
        elif campaign.bid_strategy == "cpa":
            params["pricing_model"] = "CPA"

        if campaign.bid_amount:
            params["bid_price"] = campaign.bid_amount

        # 时间
        if campaign.start_time:
            params["start_date"] = campaign.start_time.isoformat()
        if campaign.end_time:
            params["end_date"] = campaign.end_time.isoformat()

        result = await self._call_mcp("create_campaign", **params)
        
        if "error" not in result:
            logger.info(f"Created Adform campaign: {result.get('campaign_id')}")
        else:
            logger.error(f"Failed to create Adform campaign: {result['error']}")
        
        return result

    async def update_campaign(self, campaign_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """更新Campaign"""
        params = {"campaign_id": campaign_id, **updates}
        return await self._call_mcp("update_campaign", **params)

    async def delete_campaign(self, campaign_id: str) -> bool:
        """删除Campaign"""
        result = await self._call_mcp("delete_campaign", campaign_id=campaign_id)
        return "error" not in result

    async def update_campaign_status(self, campaign_id: str, status: CampaignStatus) -> bool:
        """更新Campaign状态"""
        status_map = {
            CampaignStatus.ENABLED: "ACTIVE",
            CampaignStatus.PAUSED: "INACTIVE",
            CampaignStatus.REMOVED: "ARCHIVED",
        }
        result = await self._call_mcp("update_campaign_status",
            campaign_id=campaign_id,
            status=status_map.get(status, "INACTIVE"))
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
        """获取跨渠道报表"""
        params = {"granularity": granularity}
        if campaign_ids:
            params["campaign_ids"] = campaign_ids
        if start_date:
            params["start_date"] = start_date.strftime("%Y-%m-%d")
        if end_date:
            params["end_date"] = end_date.strftime("%Y-%m-%d")

        result = await self._call_mcp("get_report", **params)
        reports = []
        
        for item in result.get("rows", []):
            reports.append(PlatformReport(
                platform="adform",
                campaign_id=str(item.get("campaign_id", "")),
                date=datetime.strptime(item["date"], "%Y-%m-%d") if "date" in item else None,
                impressions=item.get("impressions", 0),
                clicks=item.get("clicks", 0),
                spend=item.get("media_cost", 0),
                conversions=item.get("conversions", 0),
                ctr=item.get("ctr", 0) * 100,
                cpc=item.get("ecpc", 0),
                cpm=item.get("ecpm", 0),
                reach=item.get("reach", 0),
                roas=item.get("roas", 0),
                extra=item,
            ))
        
        return reports

    async def get_forecast(self, campaign: PlatformCampaign) -> PlatformForecast:
        """获取投放预测"""
        params = {
            "budget": campaign.budget_amount,
            "goal": campaign.objective or "conversions",
        }
        if campaign.audience and campaign.audience.geo_locations:
            params["geos"] = campaign.audience.geo_locations

        result = await self._call_mcp("get_forecast", **params)
        
        if "error" in result:
            return PlatformForecast(platform="adform")

        return PlatformForecast(
            platform="adform",
            estimated_reach=result.get("reach", 0),
            estimated_impressions=result.get("impressions", 0),
            estimated_cpm=result.get("ecpm", 0),
            estimated_cpc=result.get("ecpc", 0),
            estimated_conversions=result.get("conversions", 0),
            estimated_cpa=result.get("cpa", 0),
            estimated_roas=result.get("roas", 0),
            budget_suggestion=result.get("suggested_budget", 0),
            audience_size=result.get("audience_size", 0),
            competition_level=result.get("competition", "medium"),
            confidence=result.get("confidence", "medium"),
        )

    async def optimize_campaign(self, campaign_id: str) -> Dict[str, Any]:
        """
        智能优化Campaign
        Adform特有功能：自动调整出价、频次等
        """
        return await self._call_mcp("optimize_campaign", campaign_id=campaign_id)

    async def get_audience_insights(self, audience_id: str) -> Dict[str, Any]:
        """获取受众洞察（DMP数据）"""
        return await self._call_mcp("get_audience_insights", audience_id=audience_id)

    async def health_check(self) -> bool:
        """健康检查"""
        result = await self._call_mcp("list_advertisers")
        return "error" not in result

    def _parse_campaign(self, data: Dict) -> PlatformCampaign:
        """解析Campaign数据"""
        status_map = {
            "ACTIVE": CampaignStatus.ENABLED,
            "INACTIVE": CampaignStatus.PAUSED,
            "ARCHIVED": CampaignStatus.REMOVED,
        }
        
        budget = 0
        if "budget" in data and isinstance(data["budget"], dict):
            budget = data["budget"].get("total", 0)

        return PlatformCampaign(
            id=str(data.get("campaign_id", data.get("id", ""))),
            name=data.get("name"),
            status=status_map.get(data.get("status", "INACTIVE"), CampaignStatus.PAUSED),
            objective=data.get("goal", ""),
            budget_amount=budget,
            platform="adform",
            extra=data,
        )

# Need to import BudgetType
from ..base import BudgetType
