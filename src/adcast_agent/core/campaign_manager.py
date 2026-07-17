"""
Campaign管理器 - 统一管理多平台Campaign生命周期

职责：
1. 协调决策引擎和预算分配器
2. 在多个平台上创建和管理Campaign
3. 收集跨平台报表
4. 监控和告警
"""

import asyncio
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import logging

from .decision_engine import DecisionEngine, CampaignRequest, PlatformScore, StrategyType
from .budget_allocator import BudgetAllocator, AllocationStrategy, BudgetAllocation
from ..platforms.base import BaseAdPlatform, PlatformCampaign, PlatformReport, CampaignStatus
from ..utils.security import SecurityManager, ActionType
from ..utils.logger import PlatformLogAdapter

logger = logging.getLogger("adcast.campaign")


@dataclass
class CampaignExecutionPlan:
    """Campaign执行计划"""
    request: CampaignRequest
    platform_scores: List[PlatformScore]
    budget_allocations: List[BudgetAllocation]
    created_campaigns: Dict[str, str] = field(default_factory=dict)  # platform -> campaign_id
    status: str = "planned"  # planned, executing, running, paused, completed
    created_at: datetime = field(default_factory=datetime.now)


class CampaignManager:
    """Campaign管理器"""

    def __init__(
        self,
        platforms: Dict[str, BaseAdPlatform],
        decision_engine: Optional[DecisionEngine] = None,
        budget_allocator: Optional[BudgetAllocator] = None,
        security_manager: Optional[SecurityManager] = None,
    ):
        self.platforms = platforms
        self.decision_engine = decision_engine or DecisionEngine(platforms)
        self.budget_allocator = budget_allocator or BudgetAllocator()
        self.security = security_manager
        self._plans: Dict[str, CampaignExecutionPlan] = {}
        self._platform_loggers: Dict[str, PlatformLogAdapter] = {}

    def _get_logger(self, platform: str) -> PlatformLogAdapter:
        """获取平台日志适配器"""
        if platform not in self._platform_loggers:
            self._platform_loggers[platform] = PlatformLogAdapter(logger, platform)
        return self._platform_loggers[platform]

    async def plan_campaign(
        self,
        request: CampaignRequest,
        strategy: StrategyType = StrategyType.ROAS_MAXIMIZE,
        allocation_strategy: AllocationStrategy = AllocationStrategy.ROAS_WEIGHTED,
    ) -> CampaignExecutionPlan:
        """
        制定Campaign执行计划
        
        流程：
        1. 决策引擎选择平台
        2. 预算分配器分配预算
        3. 生成执行计划
        """
        logger.info(f"Planning campaign: {request.name}")

        # 1. 选择平台
        platform_scores = await self.decision_engine.select_platforms(
            request, strategy=strategy
        )

        if not platform_scores:
            raise ValueError("No suitable platforms found for the campaign")

        # 2. 分配预算
        daily_budget = request.daily_budget or (request.budget_total / 30)
        allocations = self.budget_allocator.allocate(
            platform_scores, daily_budget, strategy=allocation_strategy
        )

        # 3. 生成计划
        plan = CampaignExecutionPlan(
            request=request,
            platform_scores=platform_scores,
            budget_allocations=allocations,
        )

        self._plans[request.name] = plan
        
        logger.info(
            f"Campaign plan created: {request.name} | "
            f"platforms={[s.platform for s in platform_scores]} | "
            f"daily_budget=${daily_budget:.0f}"
        )
        
        return plan

    async def execute_plan(self, plan_name: str) -> Dict[str, Any]:
        """
        执行Campaign计划
        
        在所有选定的平台上创建Campaign（默认PAUSED状态）。
        """
        plan = self._plans.get(plan_name)
        if not plan:
            raise ValueError(f"Plan not found: {plan_name}")

        plan.status = "executing"
        request = plan.request
        results = {}

        for score, allocation in zip(plan.platform_scores, plan.budget_allocations):
            platform_name = score.platform
            platform = self.platforms.get(platform_name)
            
            if not platform:
                continue

            plog = self._get_logger(platform_name)

            try:
                # 构建平台Campaign
                campaign = PlatformCampaign(
                    name=f"{request.name} - {platform_name.upper()}",
                    objective=request.objective,
                    budget_amount=allocation.daily_budget,
                    budget_type=BudgetType.DAILY,
                    status=CampaignStatus.PAUSED,  # 安全：默认暂停
                    start_time=request.start_date,
                    end_time=request.end_date,
                    audience=request.audience,
                )

                # 安全检查
                if self.security:
                    allowed = await self.security.check_operation(
                        platform=platform_name,
                        action=ActionType.CREATE_CAMPAIGN,
                        description=f"Create campaign '{campaign.name}' on {platform_name}",
                        details={
                            "campaign_name": campaign.name,
                            "daily_budget": allocation.daily_budget,
                            "objective": request.objective,
                        },
                        platform_budget_limit=allocation.daily_budget * 2,
                    )
                    if not allowed:
                        plog.warning("Campaign creation blocked by security", action="create_campaign")
                        results[platform_name] = {"status": "BLOCKED", "reason": "security"}
                        continue

                # 创建Campaign
                result = await platform.create_campaign(campaign)
                
                if "error" not in str(result).lower() and "error" not in result:
                    campaign_id = self._extract_campaign_id(result, platform_name)
                    plan.created_campaigns[platform_name] = campaign_id
                    results[platform_name] = {"status": "CREATED", "campaign_id": campaign_id}
                    plog.info(f"Campaign created: {campaign_id}", action="create_campaign", campaign_id=campaign_id)
                    
                    if self.security:
                        self.security.record_execution(
                            platform=platform_name,
                            action=ActionType.CREATE_CAMPAIGN,
                            status="SUCCESS",
                            campaign_id=campaign_id,
                        )
                else:
                    error = result.get("error", str(result))
                    results[platform_name] = {"status": "FAILED", "error": error}
                    plog.error(f"Campaign creation failed: {error}", action="create_campaign")

            except Exception as e:
                plog.error(f"Exception during campaign creation: {e}", action="create_campaign")
                results[platform_name] = {"status": "ERROR", "error": str(e)}

        plan.status = "running" if plan.created_campaigns else "failed"
        return results

    async def activate_campaigns(self, plan_name: str) -> Dict[str, bool]:
        """
        激活所有Campaign（从PAUSED改为ENABLED）
        
        需要额外确认，因为会开始花费。
        """
        plan = self._plans.get(plan_name)
        if not plan:
            raise ValueError(f"Plan not found: {plan_name}")

        results = {}
        
        for platform_name, campaign_id in plan.created_campaigns.items():
            platform = self.platforms.get(platform_name)
            if not platform:
                continue

            plog = self._get_logger(platform_name)

            try:
                # 安全检查
                if self.security:
                    allowed = await self.security.check_operation(
                        platform=platform_name,
                        action=ActionType.RESUME_CAMPAIGN,
                        description=f"Activate campaign {campaign_id} on {platform_name}",
                        details={"campaign_id": campaign_id},
                    )
                    if not allowed:
                        plog.warning("Activation blocked by security", action="activate")
                        results[platform_name] = False
                        continue

                success = await platform.update_campaign_status(
                    campaign_id, CampaignStatus.ENABLED
                )
                results[platform_name] = success
                
                if success:
                    plog.info(f"Campaign activated: {campaign_id}", action="activate", campaign_id=campaign_id)
                else:
                    plog.warning(f"Failed to activate campaign: {campaign_id}", action="activate")

            except Exception as e:
                plog.error(f"Exception during activation: {e}", action="activate")
                results[platform_name] = False

        if all(results.values()):
            plan.status = "active"
        
        return results

    async def pause_campaigns(self, plan_name: str) -> Dict[str, bool]:
        """暂停所有Campaign"""
        plan = self._plans.get(plan_name)
        if not plan:
            raise ValueError(f"Plan not found: {plan_name}")

        results = {}
        
        for platform_name, campaign_id in plan.created_campaigns.items():
            platform = self.platforms.get(platform_name)
            if not platform:
                continue

            try:
                success = await platform.update_campaign_status(
                    campaign_id, CampaignStatus.PAUSED
                )
                results[platform_name] = success
                
                if success:
                    self._get_logger(platform_name).info(
                        f"Campaign paused: {campaign_id}",
                        action="pause", campaign_id=campaign_id
                    )

            except Exception as e:
                logger.error(f"Error pausing campaign on {platform_name}: {e}")
                results[platform_name] = False

        plan.status = "paused"
        return results

    async def get_cross_platform_report(
        self,
        plan_name: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, List[PlatformReport]]:
        """获取跨平台报表"""
        plan = self._plans.get(plan_name)
        if not plan:
            raise ValueError(f"Plan not found: {plan_name}")

        results = {}
        tasks = []
        names = []

        for platform_name, campaign_id in plan.created_campaigns.items():
            platform = self.platforms.get(platform_name)
            if not platform:
                continue

            tasks.append(platform.get_report(
                campaign_ids=[campaign_id],
                start_date=start_date,
                end_date=end_date,
            ))
            names.append(platform_name)

        gathered = await asyncio.gather(*tasks, return_exceptions=True)
        
        for name, report in zip(names, gathered):
            if isinstance(report, list):
                results[name] = report
            else:
                results[name] = []
                logger.warning(f"Failed to get report for {name}: {report}")

        return results

    def get_plan(self, plan_name: str) -> Optional[CampaignExecutionPlan]:
        """获取执行计划"""
        return self._plans.get(plan_name)

    def list_plans(self) -> List[str]:
        """列出所有计划"""
        return list(self._plans.keys())

    def _extract_campaign_id(self, result: Dict, platform: str) -> str:
        """从创建结果中提取Campaign ID"""
        id_fields = [
            "campaign_id", "ad_id", "order_id", "project_id",
            "id", "campaignId", "adId", "orderId",
        ]
        
        # 直接查找
        for field in id_fields:
            if field in result:
                return str(result[field])
        
        # 嵌套查找
        for field in id_fields:
            if "data" in result and isinstance(result["data"], dict):
                if field in result["data"]:
                    return str(result["data"][field])
        
        return "unknown"
