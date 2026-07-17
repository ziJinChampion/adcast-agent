"""
巨量引擎 (OceanEngine) MCP Connector

国内唯一官方支持MCP协议的广告平台。
通过官方MCP Server连接，支持：
- 广告项目/计划/创意管理
- DMP人群管理
- 数据报表
- 素材管理
- 智能工具（诊断、预估）
- 千川电商/本地推/DOU+

官方MCP文档: https://open.oceanengine.com/labels/7/docs/1832875799891140
工具列表: https://open.oceanengine.com/labels/7/docs/1847297391943370
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
import logging

from ..base import (
    MCPAdPlatform, PlatformCampaign, PlatformReport, PlatformForecast,
    PlatformAudience, CampaignStatus, BudgetType, PlatformCapability,
)

logger = logging.getLogger("adcast.platform.oceanengine")


class OceanEngineConnector(MCPAdPlatform):
    """巨量引擎官方MCP连接器"""

    # 投放目标映射
    OBJECTIVE_MAP = {
        "conversions": "CONVERT",
        "awareness": "SHOW",
        "traffic": "TRAFFIC",
        "app_installs": "APP_ACTIVATE",
        "sales": "SHOPPING",
        "leads": "LEAD_COLLECT",
        "livestream": "LIVE_PROMOTION",
        "local": "LOCAL_STORE",
    }

    # 预算类型
    BUDGET_MODE_MAP = {
        BudgetType.DAILY: "BUDGET_MODE_DAY",
        BudgetType.LIFETIME: "BUDGET_MODE_TOTAL",
    }

    def __init__(self, config: Dict[str, Any], mcp_client=None):
        super().__init__("oceanengine", config, mcp_client)
        self.advertiser_id = config.get("credentials", {}).get("advertiser_id")

    def _init_capability(self) -> PlatformCapability:
        return PlatformCapability(
            platform="oceanengine",
            supports_mcp=True,
            supports_api=True,
            supports_forecast=True,
            supports_auto_bidding=True,
            supports_audience=True,
            supports_creative_upload=True,
            supports_report=True,
            supported_objectives=[
                "conversions", "awareness", "traffic", "app_installs",
                "sales", "leads", "livestream", "local",
            ],
            supported_creative_types=[
                "video", "image", "carousel", "live", "mini_program",
            ],
            min_budget=300.0,  # 300元
        )

    async def create_campaign(self, campaign: PlatformCampaign) -> Dict[str, Any]:
        """创建巨量引擎广告项目/计划"""
        landing_type = self._get_landing_type(campaign.objective)
        
        params = {
            "advertiser_id": int(self.advertiser_id) if self.advertiser_id else 0,
            "name": campaign.name,
            "landing_type": landing_type,
        }

        # 预算
        if campaign.budget_amount > 0:
            params["budget"] = campaign.budget_amount
            params["budget_mode"] = self.BUDGET_MODE_MAP.get(campaign.budget_type, "BUDGET_MODE_DAY")

        # 出价
        if campaign.bid_strategy == "ocpm":
            params["pricing"] = "PRICING_OCPM"
        elif campaign.bid_strategy == "cpm":
            params["pricing"] = "PRICING_CPM"
        elif campaign.bid_strategy == "cpc":
            params["pricing"] = "PRICING_CPC"

        if campaign.bid_amount:
            params["bid"] = campaign.bid_amount

        # 时间
        if campaign.start_time:
            params["start_time"] = int(campaign.start_time.timestamp())
        if campaign.end_time:
            params["end_time"] = int(campaign.end_time.timestamp())

        # 状态 - 默认PAUSED
        params["status"] = "CAMPAIGN_STATUS_DISABLE" if campaign.status == CampaignStatus.PAUSED else "CAMPAIGN_STATUS_ENABLE"

        # 受众
        if campaign.audience:
            params["audience"] = self._build_audience_params(campaign.audience)

        result = await self._call_mcp("create_project", **params)
        
        if "error" not in result:
            logger.info(f"Created OceanEngine project: {result.get('project_id')}")
        else:
            logger.error(f"Failed to create OceanEngine project: {result['error']}")
        
        return result

    async def update_campaign(self, campaign_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """更新广告项目"""
        params = {
            "advertiser_id": int(self.advertiser_id) if self.advertiser_id else 0,
            "project_id": campaign_id,
            **updates,
        }
        return await self._call_mcp("update_project", **params)

    async def delete_campaign(self, campaign_id: str) -> bool:
        """删除广告项目"""
        result = await self._call_mcp("update_project_status",
            advertiser_id=int(self.advertiser_id) if self.advertiser_id else 0,
            project_id=campaign_id,
            status="CAMPAIGN_STATUS_DELETE")
        return "error" not in result

    async def update_campaign_status(self, campaign_id: str, status: CampaignStatus) -> bool:
        """更新广告项目状态"""
        status_map = {
            CampaignStatus.ENABLED: "CAMPAIGN_STATUS_ENABLE",
            CampaignStatus.PAUSED: "CAMPAIGN_STATUS_DISABLE",
            CampaignStatus.REMOVED: "CAMPAIGN_STATUS_DELETE",
        }
        result = await self._call_mcp("update_project_status",
            advertiser_id=int(self.advertiser_id) if self.advertiser_id else 0,
            project_id=campaign_id,
            status=status_map.get(status, "CAMPAIGN_STATUS_DISABLE"))
        return "error" not in result

    async def list_campaigns(self, status: Optional[CampaignStatus] = None) -> List[PlatformCampaign]:
        """列出广告项目"""
        params = {
            "advertiser_id": int(self.advertiser_id) if self.advertiser_id else 0,
        }
        if status:
            oe_status = {
                CampaignStatus.ENABLED: "CAMPAIGN_STATUS_ENABLE",
                CampaignStatus.PAUSED: "CAMPAIGN_STATUS_DISABLE",
            }.get(status)
            if oe_status:
                params["status"] = oe_status

        result = await self._call_mcp("list_projects", **params)
        campaigns = []
        
        for item in result.get("list", []):
            campaigns.append(self._parse_campaign(item))
        
        return campaigns

    async def get_campaign(self, campaign_id: str) -> Optional[PlatformCampaign]:
        """获取广告项目详情"""
        result = await self._call_mcp("get_project",
            advertiser_id=int(self.advertiser_id) if self.advertiser_id else 0,
            project_id=campaign_id)
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
        """获取数据报表"""
        params = {
            "advertiser_id": int(self.advertiser_id) if self.advertiser_id else 0,
            "metrics": [
                "show", "click", "cost", "convert", "ctr", "cpc", "cpm",
                "reach", "frequency", "active_pay_roi",
            ],
        }
        if campaign_ids:
            params["campaign_ids"] = campaign_ids
        if start_date:
            params["start_date"] = start_date.strftime("%Y-%m-%d")
        if end_date:
            params["end_date"] = end_date.strftime("%Y-%m-%d")
        params["time_granularity"] = granularity.upper()

        result = await self._call_mcp("get_report", **params)
        reports = []
        
        for item in result.get("rows", []):
            reports.append(PlatformReport(
                platform="oceanengine",
                campaign_id=str(item.get("campaign_id", "")),
                date=datetime.strptime(item["stat_time_day"], "%Y-%m-%d") if "stat_time_day" in item else None,
                impressions=item.get("show", 0),
                clicks=item.get("click", 0),
                spend=item.get("cost", 0),
                conversions=item.get("convert", 0),
                ctr=item.get("ctr", 0),
                cpc=item.get("cpc", 0),
                cpm=item.get("cpm", 0),
                reach=item.get("reach", 0),
                frequency=item.get("frequency", 0),
                roas=item.get("active_pay_roi", 0),
                extra=item,
            ))
        
        return reports

    async def get_forecast(self, campaign: PlatformCampaign) -> PlatformForecast:
        """获取受众预估"""
        params = {
            "advertiser_id": int(self.advertiser_id) if self.advertiser_id else 0,
        }
        if campaign.audience:
            params["audience"] = self._build_audience_params(campaign.audience)

        result = await self._call_mcp("estimate_audience", **params)
        
        if "error" in result:
            return PlatformForecast(platform="oceanengine")

        return PlatformForecast(
            platform="oceanengine",
            estimated_reach=result.get("reach", 0),
            estimated_impressions=result.get("impressions", 0),
            estimated_cpm=result.get("cpm", 0),
            estimated_cpc=result.get("cpc", 0),
            audience_size=result.get("audience_size", 0),
            confidence=result.get("confidence", "medium"),
        )

    async def create_audience(self, name: str, audience: PlatformAudience) -> Dict[str, Any]:
        """创建人群包"""
        params = {
            "advertiser_id": int(self.advertiser_id) if self.advertiser_id else 0,
            "name": name,
            **self._build_audience_params(audience),
        }
        return await self._call_mcp("create_audience", **params)

    async def upload_creative(self, file_path: str, file_name: str, 
                              creative_type: str = "video") -> Dict[str, Any]:
        """上传素材"""
        return await self._call_mcp("upload_creative",
            advertiser_id=int(self.advertiser_id) if self.advertiser_id else 0,
            file_path=file_path,
            file_name=file_name,
            type=creative_type)

    async def health_check(self) -> bool:
        """健康检查"""
        result = await self._call_mcp("get_advertiser_info",
            advertiser_id=int(self.advertiser_id) if self.advertiser_id else 0)
        return "error" not in result

    def _build_audience_params(self, audience: PlatformAudience) -> Dict[str, Any]:
        """构建受众参数"""
        params = {}

        if audience.age_min or audience.age_max:
            params["age"] = [
                audience.age_min or 18,
                audience.age_max or 65,
            ]

        if audience.genders:
            gender_map = {"male": "GENDER_MALE", "female": "GENDER_FEMALE"}
            params["gender"] = [gender_map.get(g.lower(), "GENDER_UNLIMITED") for g in audience.genders]

        if audience.geo_locations:
            params["district"] = audience.geo_locations

        if audience.interests:
            params["interest_action"] = {
                "interest_categories": audience.interests,
            }

        if audience.custom_audiences:
            params["audience"] = {
                "audience_ids": audience.custom_audiences,
            }

        return params

    def _parse_campaign(self, data: Dict) -> PlatformCampaign:
        """解析广告项目数据"""
        status_map = {
            "CAMPAIGN_STATUS_ENABLE": CampaignStatus.ENABLED,
            "ENABLE": CampaignStatus.ENABLED,
            "CAMPAIGN_STATUS_DISABLE": CampaignStatus.PAUSED,
            "DISABLE": CampaignStatus.PAUSED,
            "CAMPAIGN_STATUS_DELETE": CampaignStatus.REMOVED,
            "DELETE": CampaignStatus.REMOVED,
        }

        return PlatformCampaign(
            id=str(data.get("project_id", data.get("campaign_id", data.get("id", "")))),
            name=data.get("name"),
            status=status_map.get(data.get("status", ""), CampaignStatus.PAUSED),
            objective=data.get("landing_type", ""),
            budget_amount=data.get("budget", 0),
            platform="oceanengine",
            extra=data,
        )

    def _get_landing_type(self, objective: Optional[str]) -> str:
        """获取落地页类型"""
        landing_map = {
            "conversions": "LINK",
            "awareness": "SHOP",
            "traffic": "LINK",
            "app_installs": "APP",
            "sales": "SHOP",
            "leads": "LINK",
            "livestream": "LINK",
            "local": "LOCAL_STORE",
        }
        return landing_map.get(objective, "LINK")
