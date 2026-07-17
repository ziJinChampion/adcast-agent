"""
Amazon DSP MCP Connector

通过MCP Server连接Amazon DSP，支持：
- Campaign/Order管理
- Inventory管理
- Deal管理
- Forecasting预测
- 报表查询

推荐MCP Server：
- 官方: Amazon DSP MCP (2026年2月发布)
- KuudoAI: github.com/KuudoAI/amazon-ads-mcp
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
import logging

from ..base import (
    MCPAdPlatform, PlatformCampaign, PlatformReport, PlatformForecast,
    PlatformAudience, CampaignStatus, PlatformCapability,
)

logger = logging.getLogger("adcast.platform.amazon_dsp")


class AmazonDSPConnector(MCPAdPlatform):
    """Amazon DSP MCP连接器"""

    def __init__(self, config: Dict[str, Any], mcp_client=None):
        super().__init__("amazon_dsp", config, mcp_client)

    def _init_capability(self) -> PlatformCapability:
        return PlatformCapability(
            platform="amazon_dsp",
            supports_mcp=True,
            supports_api=True,
            supports_forecast=True,
            supports_auto_bidding=True,
            supports_audience=True,
            supports_creative_upload=False,
            supports_report=True,
            supported_objectives=[
                "conversions", "awareness", "sales", "retargeting",
            ],
            supported_creative_types=[
                "display", "video", "audio",
            ],
            min_budget=50000.0,  # $50K/month typically
        )

    async def create_campaign(self, campaign: PlatformCampaign) -> Dict[str, Any]:
        """创建DSP Order"""
        status = "PAUSED" if campaign.status == CampaignStatus.PAUSED else "ACTIVE"

        params = {
            "name": campaign.name,
            "status": status,
            "budget": {
                "amount": campaign.budget_amount,
                "delivery_profile": "DAILY",
            },
        }

        # 电商目标
        if campaign.objective == "sales":
            params["goal"] = "SELL_THROUGH"
        elif campaign.objective == "awareness":
            params["goal"] = "AWARENESS"
        elif campaign.objective == "conversions":
            params["goal"] = "CONVERSION"

        if campaign.start_time:
            params["start_date"] = campaign.start_time.strftime("%Y-%m-%d")
        if campaign.end_time:
            params["end_date"] = campaign.end_time.strftime("%Y-%m-%d")

        result = await self._call_mcp("create_order", **params)
        
        if "error" not in result:
            logger.info(f"Created Amazon DSP order: {result.get('order_id')}")
        else:
            logger.error(f"Failed to create Amazon DSP order: {result['error']}")
        
        return result

    async def update_campaign(self, order_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """更新Order"""
        params = {"order_id": order_id, **updates}
        return await self._call_mcp("update_order", **params)

    async def delete_campaign(self, order_id: str) -> bool:
        """归档Order"""
        result = await self._call_mcp("update_order_status",
            order_id=order_id, status="ARCHIVED")
        return "error" not in result

    async def update_campaign_status(self, order_id: str, status: CampaignStatus) -> bool:
        """更新Order状态"""
        status_map = {
            CampaignStatus.ENABLED: "ACTIVE",
            CampaignStatus.PAUSED: "PAUSED",
            CampaignStatus.REMOVED: "ARCHIVED",
        }
        result = await self._call_mcp("update_order_status",
            order_id=order_id,
            status=status_map.get(status, "PAUSED"))
        return "error" not in result

    async def list_campaigns(self, status: Optional[CampaignStatus] = None) -> List[PlatformCampaign]:
        """列出Orders"""
        params = {}
        if status:
            params["status"] = status.value.upper()
        
        result = await self._call_mcp("list_orders", **params)
        campaigns = []
        
        for item in result.get("orders", []):
            campaigns.append(self._parse_order(item))
        
        return campaigns

    async def get_campaign(self, order_id: str) -> Optional[PlatformCampaign]:
        """获取Order详情"""
        result = await self._call_mcp("get_order", order_id=order_id)
        if "error" in result:
            return None
        return self._parse_order(result)

    async def get_report(
        self,
        campaign_ids: Optional[List[str]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        granularity: str = "daily",
    ) -> List[PlatformReport]:
        """获取报表"""
        params = {"granularity": granularity}
        if campaign_ids:
            params["order_ids"] = campaign_ids
        if start_date:
            params["start_date"] = start_date.strftime("%Y-%m-%d")
        if end_date:
            params["end_date"] = end_date.strftime("%Y-%m-%d")

        result = await self._call_mcp("get_report", **params)
        reports = []
        
        for item in result.get("rows", []):
            reports.append(PlatformReport(
                platform="amazon_dsp",
                campaign_id=str(item.get("order_id", "")),
                date=datetime.strptime(item["date"], "%Y-%m-%d") if "date" in item else None,
                impressions=item.get("impressions", 0),
                clicks=item.get("clicks", 0),
                spend=item.get("total_cost", 0),
                conversions=item.get("dpv_detail_page_views", 0),
                ctr=item.get("ctr", 0) * 100,
                cpc=item.get("e_cpc", 0),
                cpm=item.get("e_cpm", 0),
                reach=item.get("reach", 0),
                extra=item,
            ))
        
        return reports

    async def get_forecast(self, campaign: PlatformCampaign) -> PlatformForecast:
        """获取投放预测（Forecasting API）"""
        params = {
            "budget": campaign.budget_amount,
            "start_date": campaign.start_time.strftime("%Y-%m-%d") if campaign.start_time else None,
            "end_date": campaign.end_time.strftime("%Y-%m-%d") if campaign.end_time else None,
        }
        
        result = await self._call_mcp("get_forecast", **params)
        
        if "error" in result:
            return PlatformForecast(platform="amazon_dsp")

        return PlatformForecast(
            platform="amazon_dsp",
            estimated_reach=result.get("reach", 0),
            estimated_impressions=result.get("impressions", 0),
            estimated_cpm=result.get("cpm", 0),
            estimated_cpc=result.get("cpc", 0),
            estimated_conversions=result.get("conversions", 0),
            estimated_cpa=result.get("cpa", 0),
            estimated_roas=result.get("roas", 0),
            budget_suggestion=result.get("suggested_budget", 0),
            audience_size=result.get("audience_size", 0),
            confidence=result.get("confidence", "medium"),
        )

    async def list_inventory(self) -> List[Dict[str, Any]]:
        """列出可用Inventory"""
        result = await self._call_mcp("list_inventory")
        return result.get("inventory_groups", [])

    async def health_check(self) -> bool:
        """健康检查"""
        result = await self._call_mcp("list_profiles")
        return "error" not in result

    def _parse_order(self, data: Dict) -> PlatformCampaign:
        """解析Order数据"""
        status_map = {
            "ACTIVE": CampaignStatus.ENABLED,
            "PAUSED": CampaignStatus.PAUSED,
            "ARCHIVED": CampaignStatus.REMOVED,
            "ENDED": CampaignStatus.REMOVED,
        }
        
        return PlatformCampaign(
            id=str(data.get("order_id", data.get("id", ""))),
            name=data.get("name"),
            status=status_map.get(data.get("status", "PAUSED"), CampaignStatus.PAUSED),
            objective=data.get("goal", ""),
            budget_amount=data.get("budget", {}).get("amount", 0),
            platform="amazon_dsp",
            extra=data,
        )
