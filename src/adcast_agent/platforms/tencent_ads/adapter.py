"""
腾讯广告 MCP Adapter (自研)

腾讯广告没有官方MCP Server，此模块将其Marketing API包装为MCP工具。

覆盖能力：
- 推广计划/广告组/广告/创意管理
- 数据洞察报表
- DMP人群管理
- 动态商品广告
- 智能出价

API文档: https://developers.e.qq.com/
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
import logging

from ..base import (
    APIAdPlatform, PlatformCampaign, PlatformReport, PlatformForecast,
    PlatformAudience, CampaignStatus, BudgetType, PlatformCapability,
)

logger = logging.getLogger("adcast.platform.tencent_ads")


class TencentAdsAdapter(APIAdPlatform):
    """腾讯广告 MCP Adapter"""

    API_BASE = "https://sandbox-api.e.qq.com/v3.0"  # 生产环境: https://api.e.qq.com/v3.0

    # 投放目标映射
    OBJECTIVE_MAP = {
        "conversions": "PROMOTED_OBJECT_TYPE_LINK",
        "awareness": "PROMOTED_OBJECT_TYPE_LINK",
        "traffic": "PROMOTED_OBJECT_TYPE_LINK",
        "app_installs": "PROMOTED_OBJECT_TYPE_APP_ANDROID",
        "sales": "PROMOTED_OBJECT_TYPE_ECOMMERCE",
        "leads": "PROMOTED_OBJECT_TYPE_LEAD_AD",
        "video_views": "PROMOTED_OBJECT_TYPE_LINK",
    }

    def __init__(self, config: Dict[str, Any]):
        super().__init__("tencent_ads", config)
        self.api_base_url = config.get("api_base_url", self.API_BASE)
        self.account_id = config.get("credentials", {}).get("account_id")
        self.access_token = config.get("credentials", {}).get("access_token")

    def _init_capability(self) -> PlatformCapability:
        return PlatformCapability(
            platform="tencent_ads",
            supports_mcp=False,  # 自研Adapter
            supports_api=True,
            supports_forecast=False,
            supports_auto_bidding=True,
            supports_audience=True,
            supports_creative_upload=True,
            supports_report=True,
            supported_objectives=[
                "conversions", "awareness", "traffic", "app_installs",
                "sales", "leads", "video_views",
            ],
            supported_creative_types=[
                "image", "video", "carousel", "collection",
            ],
            min_budget=50.0,  # 50元
        )

    def _build_headers(self) -> Dict[str, str]:
        """构建API请求头"""
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Access-Token": self.access_token or "",
        }

    async def create_campaign(self, campaign: PlatformCampaign) -> Dict[str, Any]:
        """创建推广计划"""
        data = {
            "account_id": int(self.account_id) if self.account_id else 0,
            "campaign_name": campaign.name,
            "campaign_type": "CAMPAIGN_TYPE_NORMAL",
            "promoted_object_type": self.OBJECTIVE_MAP.get(campaign.objective, "PROMOTED_OBJECT_TYPE_LINK"),
            "daily_budget": int(campaign.budget_amount * 100) if campaign.budget_amount > 0 else 0,
            "configured_status": "CAMPAIGN_STATUS_SUSPEND" if campaign.status == CampaignStatus.PAUSED else "CAMPAIGN_STATUS_NORMAL",
        }

        # 智能出价
        if campaign.bid_strategy == "ocpa":
            data["bid_mode"] = "BID_MODE_OCPA"

        result = await self._api_request("POST", "/campaigns/add", data=data)
        
        if "data" in result:
            logger.info(f"Created Tencent campaign: {result['data'].get('campaign_id')}")
        elif "message" in result:
            logger.error(f"Failed to create Tencent campaign: {result['message']}")
        
        return result

    async def update_campaign(self, campaign_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """更新推广计划"""
        data = {
            "account_id": int(self.account_id) if self.account_id else 0,
            "campaign_id": campaign_id,
            **updates,
        }
        return await self._api_request("POST", "/campaigns/update", data=data)

    async def delete_campaign(self, campaign_id: str) -> bool:
        """删除推广计划"""
        result = await self._api_request("POST", "/campaigns/delete", data={
            "account_id": int(self.account_id) if self.account_id else 0,
            "campaign_id": campaign_id,
        })
        return "data" in result

    async def update_campaign_status(self, campaign_id: str, status: CampaignStatus) -> bool:
        """更新推广计划状态"""
        status_map = {
            CampaignStatus.ENABLED: "CAMPAIGN_STATUS_NORMAL",
            CampaignStatus.PAUSED: "CAMPAIGN_STATUS_SUSPEND",
        }
        result = await self.update_campaign(campaign_id, {
            "configured_status": status_map.get(status, "CAMPAIGN_STATUS_SUSPEND"),
        })
        return "data" in result

    async def list_campaigns(self, status: Optional[CampaignStatus] = None) -> List[PlatformCampaign]:
        """列出推广计划"""
        params = {
            "account_id": int(self.account_id) if self.account_id else 0,
            "page": 1,
            "page_size": 100,
        }
        if status:
            t_status = {
                CampaignStatus.ENABLED: "CAMPAIGN_STATUS_NORMAL",
                CampaignStatus.PAUSED: "CAMPAIGN_STATUS_SUSPEND",
            }.get(status)
            if t_status:
                params["configured_status"] = t_status

        result = await self._api_request("GET", "/campaigns/get", params=params)
        campaigns = []
        
        for item in result.get("data", {}).get("list", []):
            campaigns.append(self._parse_campaign(item))
        
        return campaigns

    async def get_campaign(self, campaign_id: str) -> Optional[PlatformCampaign]:
        """获取推广计划详情"""
        params = {
            "account_id": int(self.account_id) if self.account_id else 0,
            "campaign_id": campaign_id,
        }
        result = await self._api_request("GET", "/campaigns/get", params=params)
        if "data" in result and result["data"].get("list"):
            return self._parse_campaign(result["data"]["list"][0])
        return None

    async def get_report(
        self,
        campaign_ids: Optional[List[str]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        granularity: str = "daily",
    ) -> List[PlatformReport]:
        """获取报表"""
        data = {
            "account_id": int(self.account_id) if self.account_id else 0,
            "level": "CAMPAIGN",
            "fields": [
                "campaign_id", "campaign_name", "date",
                "impression", "click", "cost", "conversion",
                "ctr", "cpc", "cpm",
            ],
            "page": 1,
            "page_size": 100,
        }
        if start_date:
            data["date_range"] = {
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d") if end_date else start_date.strftime("%Y-%m-%d"),
            }
        if campaign_ids:
            data["filtering"] = [{"field": "campaign_id", "operator": "IN", "values": campaign_ids}]

        result = await self._api_request("POST", "/daily_reports/get", data=data)
        reports = []
        
        for item in result.get("data", {}).get("list", []):
            reports.append(PlatformReport(
                platform="tencent_ads",
                campaign_id=str(item.get("campaign_id", "")),
                date=datetime.strptime(item["date"], "%Y-%m-%d") if "date" in item else None,
                impressions=item.get("impression", 0),
                clicks=item.get("click", 0),
                spend=item.get("cost", 0),
                conversions=item.get("conversion", 0),
                ctr=item.get("ctr", 0),
                cpc=item.get("cpc", 0),
                cpm=item.get("cpm", 0),
                extra=item,
            ))
        
        return reports

    async def create_ad_group(self, campaign_id: str, name: str,
                              bid_amount: float, audience: Optional[PlatformAudience] = None,
                              **kwargs) -> Dict[str, Any]:
        """创建广告组"""
        data = {
            "account_id": int(self.account_id) if self.account_id else 0,
            "campaign_id": campaign_id,
            "adgroup_name": name,
            "bid_amount": int(bid_amount * 100),
            "optimization_goal": "OPTIMIZATIONGOAL_CLICK",
        }
        if audience:
            data["targeting"] = self._build_audience_params(audience)
        
        return await self._api_request("POST", "/adgroups/add", data=data)

    async def health_check(self) -> bool:
        """健康检查"""
        result = await self._api_request("GET", "/advertiser/get", params={
            "account_id": int(self.account_id) if self.account_id else 0,
        })
        return "data" in result

    def _build_audience_params(self, audience: PlatformAudience) -> Dict[str, Any]:
        """构建受众参数"""
        targeting = {}

        if audience.age_min or audience.age_max:
            targeting["age"] = [
                list(range(audience.age_min or 18, (audience.age_max or 65) + 1, 5))
            ]

        if audience.genders:
            gender_map = {"male": ["MALE"], "female": ["FEMALE"]}
            targeting["gender"] = gender_map.get(audience.genders[0].lower(), ["MALE", "FEMALE"])

        if audience.geo_locations:
            targeting["geo_location"] = {
                "location_types": ["LIVE_IN"],
                "regions": audience.geo_locations,
            }

        if audience.interests:
            targeting["interest_targeting"] = {
                "interests": audience.interests,
            }

        return targeting

    def _parse_campaign(self, data: Dict) -> PlatformCampaign:
        """解析推广计划"""
        status_map = {
            "CAMPAIGN_STATUS_NORMAL": CampaignStatus.ENABLED,
            "CAMPAIGN_STATUS_SUSPEND": CampaignStatus.PAUSED,
        }

        return PlatformCampaign(
            id=str(data.get("campaign_id", "")),
            name=data.get("campaign_name"),
            status=status_map.get(data.get("configured_status", ""), CampaignStatus.PAUSED),
            objective=data.get("promoted_object_type", ""),
            budget_amount=(data.get("daily_budget", 0) / 100),
            platform="tencent_ads",
            extra=data,
        )
