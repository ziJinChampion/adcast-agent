"""
Meta Ads MCP Connector (Facebook & Instagram)

通过MCP Server连接Meta Ads，支持：
- Campaign创建/更新/暂停/查询
- Ad Set管理（受众定向）
- Ad管理（创意）
- 受众创建和管理
- 报表查询
- A+SC (Advantage+ Shopping Campaign)

推荐MCP Server：
- 官方: mcp.facebook.com/ads (Beta, 29 tools)
- Pipeboard: meta-ads.mcp.pipeboard.co (42 tools)
- mikusnuz: github.com/mikusnuz/meta-ads-mcp (135 tools)
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
import logging

from ..base import (
    MCPAdPlatform, PlatformCampaign, PlatformReport, PlatformForecast,
    PlatformAudience, PlatformCreative, CampaignStatus, BudgetType,
    PlatformCapability,
)

logger = logging.getLogger("adcast.platform.meta_ads")


class MetaAdsConnector(MCPAdPlatform):
    """Meta Ads MCP连接器"""

    # 投放目标映射
    OBJECTIVE_MAP = {
        "conversions": "OUTCOME_SALES",
        "awareness": "OUTCOME_AWARENESS",
        "traffic": "OUTCOME_TRAFFIC",
        "app_installs": "OUTCOME_APP_PROMOTION",
        "sales": "OUTCOME_SALES",
        "leads": "OUTCOME_LEADS",
        "engagement": "OUTCOME_ENGAGEMENT",
        "video_views": "OUTCOME_AWARENESS",
    }

    def __init__(self, config: Dict[str, Any], mcp_client=None):
        super().__init__("meta_ads", config, mcp_client)

    def _init_capability(self) -> PlatformCapability:
        return PlatformCapability(
            platform="meta_ads",
            supports_mcp=True,
            supports_api=True,
            supports_forecast=True,
            supports_auto_bidding=True,
            supports_audience=True,
            supports_creative_upload=True,
            supports_report=True,
            supported_objectives=[
                "conversions", "awareness", "traffic", "app_installs",
                "sales", "leads", "engagement", "video_views",
            ],
            supported_creative_types=[
                "image", "video", "carousel", "collection",
                "reels", "stories", "advantage_plus",
            ],
            min_budget=1.0,  # $1 USD
        )

    async def create_campaign(self, campaign: PlatformCampaign) -> Dict[str, Any]:
        """创建Meta Campaign"""
        status = "PAUSED" if campaign.status == CampaignStatus.PAUSED else "ACTIVE"
        objective = self.OBJECTIVE_MAP.get(campaign.objective, "OUTCOME_SALES")

        params = {
            "name": campaign.name,
            "status": status,
            "objective": objective,
            "special_ad_categories": [],
            "buying_type": "AUCTION",
        }

        # 预算
        if campaign.budget_amount > 0:
            params["daily_budget"] = int(campaign.budget_amount * 100)  # 美分

        # Advantage+ Shopping Campaign (电商推荐)
        if campaign.objective in ("sales", "conversions"):
            params["advantage_plus_creative"] = True

        # 时间
        if campaign.start_time:
            params["start_time"] = campaign.start_time.isoformat()
        if campaign.end_time:
            params["end_time"] = campaign.end_time.isoformat()

        result = await self._call_mcp("create_campaign", **params)
        
        if "error" not in result:
            campaign_id = result.get("campaign_id") or result.get("id")
            logger.info(f"Created Meta campaign: {campaign_id}")
            
            # 如果有受众，创建Ad Set
            if campaign.audience and campaign_id:
                await self._create_ad_set(campaign_id, campaign)
        else:
            logger.error(f"Failed to create Meta campaign: {result['error']}")
        
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
            CampaignStatus.PAUSED: "PAUSED",
            CampaignStatus.REMOVED: "DELETED",
        }
        result = await self._call_mcp("update_campaign_status",
            campaign_id=campaign_id,
            status=status_map.get(status, "PAUSED"))
        return "error" not in result

    async def list_campaigns(self, status: Optional[CampaignStatus] = None) -> List[PlatformCampaign]:
        """列出Campaign"""
        params = {}
        if status:
            params["status"] = [status.value.upper()]
        
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
        """获取报表"""
        params = {"granularity": granularity}
        if campaign_ids:
            params["campaign_ids"] = campaign_ids
        if start_date:
            params["start_date"] = start_date.strftime("%Y-%m-%d")
        if end_date:
            params["end_date"] = end_date.strftime("%Y-%m-%d")

        result = await self._call_mcp("get_insights", **params)
        reports = []
        
        for item in result.get("data", []):
            reports.append(PlatformReport(
                platform="meta_ads",
                campaign_id=str(item.get("campaign_id", "")),
                date=datetime.strptime(item["date_start"], "%Y-%m-%d") if "date_start" in item else None,
                impressions=item.get("impressions", 0),
                clicks=item.get("clicks", 0),
                spend=float(item.get("spend", 0)),
                conversions=item.get("conversions", 0),
                ctr=float(item.get("ctr", 0)),
                cpc=float(item.get("cpc", 0)),
                cpm=float(item.get("cpm", 0)),
                roas=float(item.get("purchase_roas", [{"value": 0}])[0].get("value", 0)) if isinstance(item.get("purchase_roas"), list) else 0,
                reach=item.get("reach", 0),
                frequency=float(item.get("frequency", 0)),
                extra=item,
            ))
        
        return reports

    async def get_forecast(self, campaign: PlatformCampaign) -> PlatformForecast:
        """获取受众规模预估"""
        if not campaign.audience:
            return PlatformForecast(platform="meta_ads")

        audience_params = self._build_audience_params(campaign.audience)
        result = await self._call_mcp("estimate_audience_size", **audience_params)
        
        if "error" in result:
            return PlatformForecast(platform="meta_ads")

        return PlatformForecast(
            platform="meta_ads",
            audience_size=result.get("audience_size", 0),
            estimated_cpm=result.get("cpm", 0),
            estimated_cpc=result.get("cpc", 0),
            confidence=result.get("confidence", "medium"),
        )

    async def create_audience(self, name: str, audience: PlatformAudience) -> Dict[str, Any]:
        """创建自定义受众"""
        params = {
            "name": name,
            **self._build_audience_params(audience),
        }
        return await self._call_mcp("create_custom_audience", **params)

    async def health_check(self) -> bool:
        """健康检查"""
        result = await self._call_mcp("list_ad_accounts")
        return "error" not in result

    async def _create_ad_set(self, campaign_id: str, campaign: PlatformCampaign):
        """创建Ad Set（受众定向）"""
        if not campaign.audience:
            return

        params = {
            "campaign_id": campaign_id,
            "name": f"{campaign.name} - Ad Set",
            "daily_budget": int(campaign.budget_amount * 100),
            "targeting": self._build_audience_params(campaign.audience),
            "status": "PAUSED",
        }

        if campaign.bid_strategy == "lowest_cost":
            params["bid_strategy"] = "LOWEST_COST_WITHOUT_CAP"
        elif campaign.bid_strategy == "cost_cap":
            params["bid_strategy"] = "COST_CAP"
            if campaign.bid_amount:
                params["bid_amount"] = int(campaign.bid_amount * 100)

        result = await self._call_mcp("create_ad_set", **params)
        
        if "error" not in result:
            logger.info(f"Created Meta ad set: {result.get('ad_set_id')}")
        else:
            logger.error(f"Failed to create Meta ad set: {result['error']}")

    def _build_audience_params(self, audience: PlatformAudience) -> Dict[str, Any]:
        """构建受众参数字典"""
        targeting = {}

        if audience.geo_locations:
            targeting["geo_locations"] = {
                "countries": audience.geo_locations,
            }

        if audience.age_min or audience.age_max:
            targeting["age_min"] = audience.age_min or 18
            targeting["age_max"] = audience.age_max or 65

        if audience.genders:
            gender_map = {"male": 1, "female": 2}
            targeting["genders"] = [gender_map.get(g.lower(), 0) for g in audience.genders]

        if audience.interests:
            targeting["interests"] = [{"name": i} for i in audience.interests]

        if audience.languages:
            targeting["locales"] = audience.languages

        if audience.custom_audiences:
            targeting["custom_audiences"] = [{"id": aid} for aid in audience.custom_audiences]

        return targeting

    def _parse_campaign(self, data: Dict) -> PlatformCampaign:
        """解析Campaign数据"""
        status_map = {
            "ACTIVE": CampaignStatus.ENABLED,
            "PAUSED": CampaignStatus.PAUSED,
            "DELETED": CampaignStatus.REMOVED,
            "ARCHIVED": CampaignStatus.REMOVED,
        }
        
        budget = 0
        if "daily_budget" in data:
            budget = float(data["daily_budget"]) / 100
        elif "lifetime_budget" in data:
            budget = float(data["lifetime_budget"]) / 100

        return PlatformCampaign(
            id=str(data.get("campaign_id", data.get("id", ""))),
            name=data.get("name"),
            status=status_map.get(data.get("status", "PAUSED"), CampaignStatus.PAUSED),
            objective=data.get("objective", ""),
            budget_amount=budget,
            platform="meta_ads",
            extra=data,
        )
