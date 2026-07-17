"""
快手磁力引擎 MCP Adapter (自研)

快手没有官方MCP Server，此模块将其Marketing API包装为MCP工具。

覆盖能力：
- 广告计划/广告组/广告创意管理
- 搜索广告投放
- 数据报表（多维/多粒度）
- DMP人群管理
- 后链路线索管理
- 素材管理

API文档: https://developers.e.kuaishou.com/
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
import logging

from ..base import (
    APIAdPlatform, PlatformCampaign, PlatformReport, PlatformForecast,
    PlatformAudience, CampaignStatus, BudgetType, PlatformCapability,
)

logger = logging.getLogger("adcast.platform.kuaishou")


class KuaishouAdapter(APIAdPlatform):
    """快手磁力引擎 MCP Adapter"""

    API_BASE = "https://ad.e.kuaishou.com/rest/openapi/v1"

    # 推广目标映射
    OBJECTIVE_MAP = {
        "conversions": "2",   # 行为数
        "awareness": "5",    # 封面曝光数
        "traffic": "1",      # 封面点击数
        "app_installs": "9", # 安装完成数
        "sales": "31",       # 订单支付
        "leads": "23",       # 表单提交
        "livestream": "33",  # 直播间观看
        "follows": "12",     # 涨粉数
    }

    def __init__(self, config: Dict[str, Any]):
        super().__init__("kuaishou", config)
        self.api_base_url = config.get("api_base_url", self.API_BASE)
        self.advertiser_id = config.get("credentials", {}).get("advertiser_id")
        self.access_token = config.get("credentials", {}).get("access_token")
        self.refresh_token = config.get("credentials", {}).get("refresh_token")
        self.app_id = config.get("credentials", {}).get("app_id")

    def _init_capability(self) -> PlatformCapability:
        return PlatformCapability(
            platform="kuaishou",
            supports_mcp=False,  # 自研Adapter
            supports_api=True,
            supports_forecast=False,
            supports_auto_bidding=True,
            supports_audience=True,
            supports_creative_upload=True,
            supports_report=True,
            supported_objectives=[
                "conversions", "awareness", "traffic", "app_installs",
                "sales", "leads", "livestream", "follows",
            ],
            supported_creative_types=[
                "video", "image", "carousel",
            ],
            min_budget=100.0,  # 100元
        )

    def _build_headers(self) -> Dict[str, str]:
        """构建API请求头"""
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Access-Token": self.access_token or "",
            "Advertiser-Id": str(self.advertiser_id) if self.advertiser_id else "",
        }

    async def create_campaign(self, campaign: PlatformCampaign) -> Dict[str, Any]:
        """创建广告计划"""
        # 快手API结构：计划(campaign) -> 单元(unit) -> 创意(creative)
        data = {
            "advertiser_id": int(self.advertiser_id) if self.advertiser_id else 0,
            "campaign_name": campaign.name,
            "photo_type": "1",  # 竖版视频
            "bid_type": "oCPC",  # 智能出价
            "status": 2 if campaign.status == CampaignStatus.PAUSED else 1,  # 1=投放, 2=暂停
        }

        # 推广目标
        objective = self.OBJECTIVE_MAP.get(campaign.objective, "2")
        data["charge_type"] = objective

        # 预算
        if campaign.budget_amount > 0:
            data["day_budget"] = int(campaign.budget_amount * 100000)  # 快手单位：元*100000

        # 出价
        if campaign.bid_amount:
            data["bid"] = int(campaign.bid_amount * 100000)

        # 时间
        if campaign.start_time:
            data["begin_time"] = int(campaign.start_time.timestamp())
        if campaign.end_time:
            data["end_time"] = int(campaign.end_time.timestamp())

        result = await self._api_request("POST", "/campaign/create", data=data)
        
        if result.get("code") == 0:
            logger.info(f"Created Kuaishou campaign: {result.get('data', {}).get('campaign_id')}")
        else:
            logger.error(f"Failed to create Kuaishou campaign: {result.get('message')}")
        
        return result

    async def update_campaign(self, campaign_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """更新广告计划"""
        data = {
            "advertiser_id": int(self.advertiser_id) if self.advertiser_id else 0,
            "campaign_id": campaign_id,
            **updates,
        }
        return await self._api_request("POST", "/campaign/update", data=data)

    async def delete_campaign(self, campaign_id: str) -> bool:
        """删除广告计划"""
        result = await self._api_request("POST", "/campaign/delete", data={
            "advertiser_id": int(self.advertiser_id) if self.advertiser_id else 0,
            "campaign_id": campaign_id,
        })
        return result.get("code") == 0

    async def update_campaign_status(self, campaign_id: str, status: CampaignStatus) -> bool:
        """更新广告计划状态"""
        status_code = 1 if status == CampaignStatus.ENABLED else 2
        result = await self.update_campaign(campaign_id, {"status": status_code})
        return result.get("code") == 0

    async def list_campaigns(self, status: Optional[CampaignStatus] = None) -> List[PlatformCampaign]:
        """列出广告计划"""
        params = {
            "advertiser_id": int(self.advertiser_id) if self.advertiser_id else 0,
            "page": 1,
            "page_size": 100,
        }
        if status:
            params["status"] = 1 if status == CampaignStatus.ENABLED else 2

        result = await self._api_request("GET", "/campaign/list", params=params)
        campaigns = []
        
        for item in result.get("data", {}).get("list", []):
            campaigns.append(self._parse_campaign(item))
        
        return campaigns

    async def get_campaign(self, campaign_id: str) -> Optional[PlatformCampaign]:
        """获取广告计划详情"""
        params = {
            "advertiser_id": int(self.advertiser_id) if self.advertiser_id else 0,
            "campaign_id": campaign_id,
        }
        result = await self._api_request("GET", "/campaign/detail", params=params)
        if result.get("code") == 0 and result.get("data"):
            return self._parse_campaign(result["data"])
        return None

    async def get_report(
        self,
        campaign_ids: Optional[List[str]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        granularity: str = "daily",
    ) -> List[PlatformReport]:
        """获取数据报表"""
        data = {
            "advertiser_id": int(self.advertiser_id) if self.advertiser_id else 0,
            "report_dims": "campaign",
            "fields": [
                "campaign_id", "campaign_name", "stat_date",
                "impression", "click", "charge", "conversion",
                "ctr", "acp", "ecpm",
            ],
        }
        if start_date:
            data["start_date"] = int(start_date.timestamp())
        if end_date:
            data["end_date"] = int(end_date.timestamp())
        if campaign_ids:
            data["campaign_id_list"] = campaign_ids

        result = await self._api_request("POST", "/report/integrated", data=data)
        reports = []
        
        for item in result.get("data", {}).get("rows", []):
            reports.append(PlatformReport(
                platform="kuaishou",
                campaign_id=str(item.get("campaign_id", "")),
                date=datetime.strptime(item["stat_date"], "%Y-%m-%d") if "stat_date" in item else None,
                impressions=item.get("impression", 0),
                clicks=item.get("click", 0),
                spend=item.get("charge", 0),
                conversions=item.get("conversion", 0),
                ctr=item.get("ctr", 0),
                cpc=item.get("acp", 0),
                cpm=item.get("ecpm", 0),
                extra=item,
            ))
        
        return reports

    async def upload_creative(self, file_path: str, file_name: str) -> Dict[str, Any]:
        """上传素材"""
        return await self._api_request("POST", "/file/upload", data={
            "advertiser_id": int(self.advertiser_id) if self.advertiser_id else 0,
            "file_path": file_path,
            "file_name": file_name,
        })

    async def health_check(self) -> bool:
        """健康检查"""
        result = await self._api_request("GET", "/advertiser/info", params={
            "advertiser_id": int(self.advertiser_id) if self.advertiser_id else 0,
        })
        return result.get("code") == 0

    def _parse_campaign(self, data: Dict) -> PlatformCampaign:
        """解析广告计划"""
        status_map = {
            1: CampaignStatus.ENABLED,
            2: CampaignStatus.PAUSED,
            3: CampaignStatus.REMOVED,
        }

        return PlatformCampaign(
            id=str(data.get("campaign_id", "")),
            name=data.get("campaign_name"),
            status=status_map.get(data.get("status"), CampaignStatus.PAUSED),
            objective=str(data.get("charge_type", "")),
            budget_amount=(data.get("day_budget", 0) / 100000),
            platform="kuaishou",
            extra=data,
        )
