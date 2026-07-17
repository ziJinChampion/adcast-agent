"""
百度营销 MCP Adapter (自研)

百度没有官方MCP Server，此模块将其搜索推广API包装为MCP工具。
由于百度API能力相对有限（文档较分散，沙箱有限），实现为基础版本。

覆盖能力：
- 搜索推广计划/单元/关键词/创意管理
- 信息流推广
- 数据报表
- oCPC转化追踪

API文档: http://dev2.baidu.com/
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
import logging

from ..base import (
    APIAdPlatform, PlatformCampaign, PlatformReport, PlatformForecast,
    PlatformAudience, CampaignStatus, BudgetType, PlatformCapability,
)

logger = logging.getLogger("adcast.platform.baidu_ads")


class BaiduAdsAdapter(APIAdPlatform):
    """百度营销 MCP Adapter"""

    API_BASE = "https://api.baidu.com/json/sms/service"

    def __init__(self, config: Dict[str, Any]):
        super().__init__("baidu_ads", config)
        self.api_base_url = config.get("api_base_url", self.API_BASE)
        self.username = config.get("credentials", {}).get("username")
        self.password = config.get("credentials", {}).get("password")
        self.token = config.get("credentials", {}).get("token")

    def _init_capability(self) -> PlatformCapability:
        return PlatformCapability(
            platform="baidu_ads",
            supports_mcp=False,
            supports_api=True,
            supports_forecast=False,
            supports_auto_bidding=True,
            supports_audience=False,  # DMP能力较弱
            supports_creative_upload=False,
            supports_report=True,
            supported_objectives=[
                "conversions", "traffic", "sales", "leads",
            ],
            supported_creative_types=[
                "text", "image",
            ],
            min_budget=50.0,  # 50元
        )

    def _build_headers(self) -> Dict[str, str]:
        """构建API请求头"""
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _build_request_body(self, service: str, method: str, params: Dict = None) -> Dict:
        """构建百度API请求体（JSON-RPC风格）"""
        return {
            "header": {
                "username": self.username,
                "password": self.password,
                "token": self.token,
                "target": "",  # 账户名
            },
            "body": {
                "service": service,
                "method": method,
                "params": params or {},
            },
        }

    async def create_campaign(self, campaign: PlatformCampaign) -> Dict[str, Any]:
        """创建推广计划"""
        body = self._build_request_body("CampaignService", "addCampaign", {
            "campaignTypes": [{
                "campaignName": campaign.name,
                "budget": campaign.budget_amount,
                "status": 1 if campaign.status == CampaignStatus.PAUSED else 0,  # 0=启用, 1=暂停
            }]
        })

        result = await self._api_request("POST", "/CampaignService", data=body)
        
        if result.get("header", {}).get("status") == 0:
            logger.info(f"Created Baidu campaign successfully")
        else:
            logger.error(f"Failed to create Baidu campaign: {result.get('header', {}).get('desc')}")
        
        return result

    async def update_campaign(self, campaign_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """更新推广计划"""
        body = self._build_request_body("CampaignService", "updateCampaign", {
            "campaignTypes": [{
                "campaignId": campaign_id,
                **updates,
            }]
        })
        return await self._api_request("POST", "/CampaignService", data=body)

    async def delete_campaign(self, campaign_id: str) -> bool:
        """删除推广计划"""
        body = self._build_request_body("CampaignService", "deleteCampaign", {
            "campaignIds": [campaign_id],
        })
        result = await self._api_request("POST", "/CampaignService", data=body)
        return result.get("header", {}).get("status") == 0

    async def update_campaign_status(self, campaign_id: str, status: CampaignStatus) -> bool:
        """更新推广计划状态"""
        baidu_status = 1 if status == CampaignStatus.PAUSED else 0
        result = await self.update_campaign(campaign_id, {"status": baidu_status})
        return result.get("header", {}).get("status") == 0

    async def list_campaigns(self, status: Optional[CampaignStatus] = None) -> List[PlatformCampaign]:
        """列出推广计划"""
        body = self._build_request_body("CampaignService", "getAllCampaign")
        
        result = await self._api_request("POST", "/CampaignService", data=body)
        campaigns = []
        
        for item in result.get("body", {}).get("data", []):
            campaigns.append(self._parse_campaign(item))
        
        return campaigns

    async def get_campaign(self, campaign_id: str) -> Optional[PlatformCampaign]:
        """获取推广计划详情"""
        body = self._build_request_body("CampaignService", "getCampaignByCampaignId", {
            "campaignIds": [campaign_id],
        })
        result = await self._api_request("POST", "/CampaignService", data=body)
        if result.get("header", {}).get("status") == 0:
            data = result.get("body", {}).get("data", [])
            if data:
                return self._parse_campaign(data[0])
        return None

    async def get_report(
        self,
        campaign_ids: Optional[List[str]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        granularity: str = "daily",
    ) -> List[PlatformReport]:
        """获取报表"""
        body = self._build_request_body("ReportService", "getRealTimeData", {
            "realTimeRequestTypes": {
                "performanceData": [
                    "impression", "click", "cost", "conversion",
                    "ctr", "cpc", "cpm",
                ],
                "startDate": start_date.strftime("%Y-%m-%d") if start_date else None,
                "endDate": end_date.strftime("%Y-%m-%d") if end_date else None,
                "levelOfDetails": 3,  # 计划级别
            }
        })

        if campaign_ids:
            body["body"]["params"]["realTimeRequestTypes"]["campaignIds"] = campaign_ids

        result = await self._api_request("POST", "/ReportService", data=body)
        reports = []
        
        for item in result.get("body", {}).get("data", []):
            date_str = item.get("date", "")
            parsed_date = None
            try:
                parsed_date = datetime.strptime(date_str, "%Y-%m-%d")
            except (ValueError, TypeError):
                pass

            reports.append(PlatformReport(
                platform="baidu_ads",
                campaign_id=str(item.get("campaignId", "")),
                date=parsed_date,
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

    async def add_keywords(self, adgroup_id: str, keywords: List[Dict[str, str]]) -> Dict[str, Any]:
        """添加关键词"""
        body = self._build_request_body("KeywordService", "addKeyword", {
            "keywordTypes": [
                {
                    "adgroupId": adgroup_id,
                    "keyword": kw.get("keyword"),
                    "matchType": kw.get("match_type", "1"),  # 1=广泛, 2=短语, 3=精确
                    "price": kw.get("price", 0),
                }
                for kw in keywords
            ]
        })
        return await self._api_request("POST", "/KeywordService", data=body)

    async def health_check(self) -> bool:
        """健康检查"""
        body = self._build_request_body("AccountService", "getAccountInfo")
        result = await self._api_request("POST", "/AccountService", data=body)
        return result.get("header", {}).get("status") == 0

    def _parse_campaign(self, data: Dict) -> PlatformCampaign:
        """解析推广计划"""
        status_map = {
            0: CampaignStatus.ENABLED,
            1: CampaignStatus.PAUSED,
        }

        return PlatformCampaign(
            id=str(data.get("campaignId", "")),
            name=data.get("campaignName"),
            status=status_map.get(data.get("status"), CampaignStatus.PAUSED),
            objective="search",
            budget_amount=data.get("budget", 0),
            platform="baidu_ads",
            extra=data,
        )
