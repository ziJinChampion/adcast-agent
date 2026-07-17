"""
AdCast Agent - 主入口

AI驱动的自动广告投放Agent，智能选择最优平台并自动投放。
"""

import asyncio
import os
import sys
import argparse
from typing import Optional
from datetime import datetime, timedelta

from .utils.config import ConfigManager, get_config
from .utils.logger import setup_logger
from .utils.security import SecurityManager
from .mcp.client import MCPClient, stdio_client, http_client
from .mcp.registry import MCPRegistry
from .platforms.base import PlatformAudience, CampaignStatus
from .platforms.google_ads.connector import GoogleAdsConnector
from .platforms.meta_ads.connector import MetaAdsConnector
from .platforms.amazon_dsp.connector import AmazonDSPConnector
from .platforms.adform.connector import AdformConnector
from .platforms.oceanengine.connector import OceanEngineConnector
from .platforms.tencent_ads.adapter import TencentAdsAdapter
from .platforms.kuaishou.adapter import KuaishouAdapter
from .platforms.baidu_ads.adapter import BaiduAdsAdapter
from .core.decision_engine import DecisionEngine, CampaignRequest, StrategyType
from .core.budget_allocator import BudgetAllocator, AllocationStrategy
from .core.campaign_manager import CampaignManager
from .platform_manager import PlatformManager


class AdCastAgent:
    """
    AdCast Agent 主类
    
    完整的工作流：
    1. 初始化配置和平台连接
    2. 接收投放需求
    3. 决策引擎选择最优平台
    4. 预算分配
    5. 安全检查和审批
    6. 创建Campaign（默认PAUSED）
    7. 人工确认后激活
    8. 持续监控和报表
    """

    def __init__(self):
        self.config = get_config()
        self.logger = setup_logger("adcast", self.config.log_level)
        self.security = SecurityManager()
        self.registry = MCPRegistry()
        self.platforms = {}
        self.decision_engine = None
        self.campaign_manager = None
        self.platform_manager = None

    async def initialize(self):
        """初始化Agent - 连接所有配置的平台"""
        self.logger.info("=" * 50)
        self.logger.info("AdCast Agent 初始化中...")
        self.logger.info("=" * 50)

        # 初始化平台管理器
        self.platform_manager = PlatformManager(self.registry, self.config)
        await self.platform_manager.initialize_all()
        
        self.platforms = self.platform_manager.get_platforms()
        
        if not self.platforms:
            self.logger.warning("没有成功连接任何平台！请检查配置。")
            return

        # 初始化决策引擎和Campaign管理器
        self.decision_engine = DecisionEngine(self.platforms)
        self.campaign_manager = CampaignManager(
            platforms=self.platforms,
            decision_engine=self.decision_engine,
            security_manager=self.security,
        )

        self.logger.info(f"Agent初始化完成！已连接 {len(self.platforms)} 个平台:")
        for name, platform in self.platforms.items():
            mcp_status = "MCP" if platform.is_mcp() else "API"
            self.logger.info(f"  - {name} ({mcp_status})")

    async def run_campaign(
        self,
        name: str,
        objective: str,
        budget: float,
        daily_budget: float = 0,
        target_market: str = "global",
        audience: Optional[PlatformAudience] = None,
        industry: Optional[str] = None,
        creative_type: str = "video",
        strategy: str = "roas_maximize",
        allocation: str = "roas_weighted",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        auto_activate: bool = False,
    ) -> dict:
        """
        运行一个完整的Campaign流程
        
        Returns:
            dict: 执行结果
        """
        # 构建Campaign请求
        request = CampaignRequest(
            name=name,
            objective=objective,
            budget_total=budget,
            daily_budget=daily_budget or budget / 30,
            target_market=target_market,
            audience=audience,
            industry=industry,
            creative_type=creative_type,
            start_date=start_date,
            end_date=end_date,
        )

        strategy_enum = StrategyType(strategy)
        allocation_enum = AllocationStrategy(allocation)

        self.logger.info(f"开始Campaign流程: {name}")
        self.logger.info(f"  目标: {objective}")
        self.logger.info(f"  总预算: ${budget:.0f}")
        self.logger.info(f"  日预算: ${request.daily_budget:.0f}")
        self.logger.info(f"  策略: {strategy}")
        self.logger.info(f"  市场: {target_market}")

        # Step 1: 制定计划
        self.logger.info("\n[Step 1/4] 平台选择与预算分配...")
        plan = await self.campaign_manager.plan_campaign(
            request, strategy=strategy_enum, allocation_strategy=allocation_enum
        )

        self.logger.info("\n推荐平台:")
        for score in plan.platform_scores:
            self.logger.info(f"  {score.recommendation}")

        self.logger.info("\n预算分配:")
        for alloc in plan.budget_allocations:
            self.logger.info(f"  {alloc.platform}: ${alloc.daily_budget:.0f}/天 ({alloc.reasoning})")

        # Step 2: 创建Campaign（默认PAUSED）
        self.logger.info("\n[Step 2/4] 创建Campaign（默认暂停状态）...")
        create_results = await self.campaign_manager.execute_plan(name)

        for platform, result in create_results.items():
            status = result.get("status", "UNKNOWN")
            if status == "CREATED":
                self.logger.info(f"  [{platform}] 创建成功: {result.get('campaign_id')}")
            else:
                self.logger.warning(f"  [{platform}] 创建失败: {result.get('error', status)}")

        # Step 3: 激活（如果需要）
        if auto_activate:
            self.logger.info("\n[Step 3/4] 激活Campaign...")
            activate_results = await self.campaign_manager.activate_campaigns(name)
            for platform, success in activate_results.items():
                status = "已激活" if success else "激活失败"
                self.logger.info(f"  [{platform}] {status}")
        else:
            self.logger.info("\n[Step 3/4] Campaign已创建（暂停状态），请确认后手动激活")
            self.logger.info("提示: 调用 activate_campaigns() 激活所有Campaign")

        # Step 4: 返回结果
        self.logger.info("\n[Step 4/4] Campaign流程完成!")
        
        return {
            "plan_name": name,
            "platforms": [s.platform for s in plan.platform_scores],
            "scores": [
                {
                    "platform": s.platform,
                    "score": s.overall_score,
                    "recommendation": s.recommendation,
                }
                for s in plan.platform_scores
            ],
            "allocations": [
                {
                    "platform": a.platform,
                    "daily_budget": a.daily_budget,
                    "reasoning": a.reasoning,
                }
                for a in plan.budget_allocations
            ],
            "created_campaigns": plan.created_campaigns,
            "create_results": create_results,
            "status": plan.status,
        }

    async def activate_campaigns(self, plan_name: str):
        """激活指定计划的所有Campaign"""
        results = await self.campaign_manager.activate_campaigns(plan_name)
        for platform, success in results.items():
            status = "已激活" if success else "激活失败"
            self.logger.info(f"[{platform}] {status}")
        return results

    async def pause_campaigns(self, plan_name: str):
        """暂停指定计划的所有Campaign"""
        results = await self.campaign_manager.pause_campaigns(plan_name)
        for platform, success in results.items():
            status = "已暂停" if success else "暂停失败"
            self.logger.info(f"[{platform}] {status}")
        return results

    async def get_report(self, plan_name: str):
        """获取跨平台报表"""
        reports = await self.campaign_manager.get_cross_platform_report(plan_name)
        
        summary = {}
        for platform, report_list in reports.items():
            total_spend = sum(r.spend for r in report_list)
            total_impressions = sum(r.impressions for r in report_list)
            total_clicks = sum(r.clicks for r in report_list)
            total_conversions = sum(r.conversions for r in report_list)
            
            summary[platform] = {
                "spend": total_spend,
                "impressions": total_impressions,
                "clicks": total_clicks,
                "conversions": total_conversions,
                "ctr": (total_clicks / total_impressions * 100) if total_impressions > 0 else 0,
                "cpc": (total_spend / total_clicks) if total_clicks > 0 else 0,
            }
        
        return summary

    async def shutdown(self):
        """关闭Agent - 断开所有连接"""
        self.logger.info("正在关闭Agent...")
        
        # 暂停所有运行中的Campaign
        for plan_name in self.campaign_manager.list_plans():
            plan = self.campaign_manager.get_plan(plan_name)
            if plan and plan.status == "active":
                self.logger.info(f"暂停Campaign: {plan_name}")
                await self.campaign_manager.pause_campaigns(plan_name)
        
        # 断开MCP连接
        await self.registry.disconnect_all()
        
        # 关闭API Adapter会话
        for platform in self.platforms.values():
            if hasattr(platform, 'close'):
                await platform.close()
        
        self.logger.info("Agent已关闭")


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(description="AdCast Agent - AI自动广告投放")
    parser.add_argument("--campaign", "-n", help="Campaign名称")
    parser.add_argument("--objective", "-o", default="conversions",
                       choices=["conversions", "awareness", "traffic", "sales", 
                               "leads", "app_installs", "video_views"],
                       help="投放目标")
    parser.add_argument("--budget", "-b", type=float, default=3000, help="总预算（USD）")
    parser.add_argument("--daily-budget", "-d", type=float, default=0, help="日预算（USD）")
    parser.add_argument("--market", "-m", default="global",
                       choices=["global", "domestic", "overseas"],
                       help="目标市场")
    parser.add_argument("--strategy", "-s", default="roas_maximize",
                       choices=["roas_maximize", "reach_maximize", "conversion_maximize",
                               "balanced", "cost_minimize"],
                       help="投放策略")
    parser.add_argument("--auto-activate", action="store_true",
                       help="自动激活Campaign（默认需要手动确认）")
    parser.add_argument("--config", "-c", help="配置文件路径")
    
    args = parser.parse_args()

    async def run():
        agent = AdCastAgent()
        
        try:
            await agent.initialize()
            
            if args.campaign:
                result = await agent.run_campaign(
                    name=args.campaign,
                    objective=args.objective,
                    budget=args.budget,
                    daily_budget=args.daily_budget,
                    target_market=args.market,
                    strategy=args.strategy,
                    auto_activate=args.auto_activate,
                )
                print("\n" + "=" * 50)
                print("Campaign执行结果:")
                print("=" * 50)
                import json
                print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
            else:
                print("\nAdCast Agent 已就绪！")
                print(f"已连接平台: {list(agent.platforms.keys())}")
                print("\n使用示例:")
                print(f"  python -m adcast_agent --campaign '夏季促销' --objective sales --budget 5000")
                
        except KeyboardInterrupt:
            print("\n正在关闭...")
        finally:
            await agent.shutdown()

    asyncio.run(run())


if __name__ == "__main__":
    main()
