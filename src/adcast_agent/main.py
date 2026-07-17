"""
AdCast Agent - 主入口 (AI Loop 版本)

LangGraph AI Loop 驱动的工作流：
1. OBSERVE  - 收集平台数据 + 历史表现
2. ANALYZE  - LLM智能分析各平台适合度
3. DECIDE   - AI决策选平台 + 预算分配
4. EXECUTE  - 创建Campaign（默认PAUSED）
5. REFLECT  - 监控表现 + 学习优化

[Loop] <- 定时循环回到 OBSERVE

Checkpoint持久化确保进程重启后可恢复。
"""

import asyncio
import os
import sys
import argparse
import json
from typing import Optional, Dict, Any
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
from .core.campaign_loop import CampaignLoop, LoopScheduler
from .core.checkpoint import CheckpointManager, MemoryCheckpoint, PostgresCheckpoint
from .core.llm_client import LLMClient, get_llm_client
from .core.agent_graph import AgentState
from .core.long_term_memory import get_long_term_memory
from .platform_manager import PlatformManager

logger = setup_logger("adcast")


class AdCastAgent:
    """
    AdCast Agent 主类 (AI Loop 版本)

    两种工作模式：
    1. One-shot 模式: 单次Campaign投放（原来的方式）
    2. AI Loop 模式: LangGraph驱动的持续优化Loop
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

        # AI Loop 组件
        self.checkpoint_manager = None
        self.llm_client = None
        self.loop_scheduler = None

    async def initialize(self):
        """初始化Agent - 连接所有平台 + 初始化AI Loop组件"""
        self.logger.info("=" * 60)
        self.logger.info("AdCast Agent 初始化中... [AI Loop Mode]")
        self.logger.info("=" * 60)

        # 1. 初始化Checkpoint
        cp_config = self.config.get_checkpoint_config()
        self.checkpoint_manager = CheckpointManager(cp_config)
        self.logger.info(f"Checkpoint backend: {cp_config.get('backend', 'memory')}")

        # 2. 初始化LLM Client
        llm_config = self.config.get_llm_config()
        if llm_config.get("api_key"):
            self.llm_client = LLMClient(llm_config)
            self.logger.info(f"LLM: {llm_config.get('provider', 'openai')}/{llm_config.get('model', 'gpt-4o')}")
        else:
            self.logger.warning("LLM API Key未配置，AI决策将使用降级规则引擎")

        # 3. 初始化平台
        self.platform_manager = PlatformManager(self.registry, self.config)
        await self.platform_manager.initialize_all()
        self.platforms = self.platform_manager.get_platforms()

        if not self.platforms:
            self.logger.warning("没有成功连接任何平台！AI决策将使用默认平台数据。")

        # 4. 初始化传统组件
        self.decision_engine = DecisionEngine(self.platforms)
        self.campaign_manager = CampaignManager(
            platforms=self.platforms,
            decision_engine=self.decision_engine,
            security_manager=self.security,
        )

        # 5. 初始化Loop调度器
        self.loop_scheduler = LoopScheduler(self.checkpoint_manager)

        self.logger.info(f"Agent初始化完成！已连接 {len(self.platforms)} 个平台")
        for name in self.platforms.keys():
            self.logger.info(f"  - {name}")

    # ==================== AI Loop 模式 ====================

    async def run_ai_loop(
        self,
        name: str,
        objective: str,
        budget: float,
        daily_budget: float = 0,
        target_market: str = "global",
        audience: Optional[PlatformAudience] = None,
        industry: Optional[str] = None,
        creative_type: str = "video",
        interval_minutes: int = 60,
        max_iterations: int = 10,
        continuous: bool = False,
    ) -> Dict[str, Any]:
        """
        运行AI Loop模式

        使用LangGraph Observe-Analyze-Act闭环：
        1. LLM智能分析选择最优平台
        2. 自动预算分配
        3. 定时循环优化

        Args:
            name: Campaign名称
            objective: 投放目标
            budget: 总预算
            daily_budget: 日预算
            target_market: 目标市场 (global/domestic/overseas)
            audience: 受众定向
            industry: 行业
            creative_type: 创意类型
            interval_minutes: 循环间隔（分钟）
            max_iterations: 最大迭代次数
            continuous: 是否持续运行（后台定时循环）
        """
        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"[AI Loop] 启动: {name}")
        self.logger.info(f"{'='*60}")

        # 构建Campaign配置
        campaign_config = {
            "name": name,
            "objective": objective,
            "budget": budget,
            "daily_budget": daily_budget or budget / 30,
            "target_market": target_market,
            "industry": industry,
            "creative_type": creative_type,
            "audience": audience.__dict__ if audience else None,
            "_llm_config": self.config.get_llm_config() if self.llm_client else {},
        }

        # 收集平台数据
        platform_data = self._collect_platform_data(target_market)

        # 创建Loop
        loop = CampaignLoop(
            campaign_name=name,
            checkpoint_manager=self.checkpoint_manager,
            llm_client=self.llm_client,
            interval_minutes=interval_minutes,
            max_iterations=max_iterations,
        )
        await loop.initialize()

        if continuous:
            # 持续运行模式（后台）
            await self.loop_scheduler.start_campaign(name, campaign_config)
            self.logger.info(f"[AI Loop] 持续运行模式已启动，间隔={interval_minutes}分钟")
            return {
                "status": "running_continuously",
                "campaign_name": name,
                "interval_minutes": interval_minutes,
                "note": "使用 pause_campaign() 暂停, resume_campaign() 恢复",
            }
        else:
            # 单次执行一轮
            result = await loop.start(campaign_config, platform_data)
            self.logger.info(f"[AI Loop] 第一轮执行完成: {result.get('status')}")

            # 打印AI决策结果
            self._print_decision(result)

            return result

    async def resume_loop(self, campaign_name: str) -> Dict[str, Any]:
        """恢复已暂停的AI Loop"""
        self.logger.info(f"[AI Loop] 恢复Campaign: {campaign_name}")

        # 通过LoopScheduler恢复
        result = await self.loop_scheduler.resume_campaign(campaign_name)
        if result:
            self._print_decision(result)
        return result or {"error": "Campaign not found"}

    async def pause_loop(self, campaign_name: str):
        """暂停AI Loop"""
        self.logger.info(f"[AI Loop] 暂停Campaign: {campaign_name}")
        await self.loop_scheduler.pause_campaign(campaign_name)

    async def update_loop_reports(
        self,
        campaign_name: str,
        platform_reports: Dict[str, list],
    ) -> bool:
        """
        推送报表数据到AI Loop

        外部定时任务调用此方法推送最新数据，
        Loop下次迭代时会使用这些数据进行分析和优化。
        """
        return await self.loop_scheduler.update_reports(campaign_name, platform_reports)

    async def get_loop_status(self, campaign_name: str) -> Dict[str, Any]:
        """获取AI Loop状态"""
        # 查找最新的thread_id
        threads = self.checkpoint_manager.list_threads(limit=20)
        for thread_id in threads:
            if thread_id.startswith(f"campaign_{campaign_name}_"):
                # 从checkpoint读取状态
                state = self.checkpoint_manager.get(thread_id)
                if state:
                    return {
                        "thread_id": thread_id,
                        "campaign_name": campaign_name,
                        "iteration": state.get("iteration", 0),
                        "status": "paused" if state.get("pause_reason") else (
                            "completed" if not state.get("should_continue", True) else "running"
                        ),
                        "pause_reason": state.get("pause_reason"),
                        "selected_platforms": state.get("selected_platforms", []),
                        "budget_allocation": state.get("budget_allocation", {}),
                        "learning_notes": state.get("learning_notes", []),
                    }
        return {"error": "No checkpoint found for this campaign"}

    async def list_active_loops(self) -> list:
        """列出所有活跃的Loop"""
        return self.loop_scheduler.list_running()

    # ==================== One-shot 模式（传统方式）====================

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
        """传统One-shot Campaign投放模式"""
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

        plan = await self.campaign_manager.plan_campaign(
            request, strategy=strategy_enum, allocation_strategy=allocation_enum
        )

        self.logger.info("推荐平台:")
        for score in plan.platform_scores:
            self.logger.info(f"  {score.recommendation}")

        create_results = await self.campaign_manager.execute_plan(name)

        if auto_activate:
            await self.campaign_manager.activate_campaigns(name)

        return {
            "plan_name": name,
            "platforms": [s.platform for s in plan.platform_scores],
            "created_campaigns": plan.created_campaigns,
            "status": plan.status,
        }

    async def activate_campaigns(self, plan_name: str):
        """激活Campaign"""
        return await self.campaign_manager.activate_campaigns(plan_name)

    async def pause_campaigns(self, plan_name: str):
        """暂停Campaign"""
        return await self.campaign_manager.pause_campaigns(plan_name)

    async def get_report(self, plan_name: str):
        """获取报表"""
        return await self.campaign_manager.get_cross_platform_report(plan_name)

    # ==================== 生命周期 ====================

    async def shutdown(self):
        """关闭Agent"""
        self.logger.info("正在关闭Agent...")

        if self.loop_scheduler:
            await self.loop_scheduler.stop_all()

        if hasattr(self, 'registry'):
            await self.registry.disconnect_all()

        for platform in self.platforms.values():
            if hasattr(platform, 'close'):
                await platform.close()

        self.logger.info("Agent已关闭")

    # ==================== 内部方法 ====================

    def _collect_platform_data(self, target_market: str) -> list:
        """收集已连接平台的实时数据"""
        platform_data = []

        for name, platform in self.platforms.items():
            cap = platform.get_capability()
            platform_data.append({
                "name": name,
                "supports_mcp": cap.supports_mcp,
                "supports_forecast": cap.supports_forecast,
                "supported_objectives": cap.supported_objectives,
                "min_budget": cap.min_budget,
                "connected": True,
            })

        # 如果无连接平台，提供默认数据
        if not platform_data:
            platform_data = self._get_default_platform_data(target_market)

        return platform_data

    def _get_default_platform_data(self, target_market: str) -> list:
        """默认平台数据"""
        all_platforms = [
            {"name": "google_ads", "display_name": "Google Ads", "strengths": ["search", "shopping"], "avg_cpm": 8.5, "avg_cpc": 2.5, "best_for": ["conversions", "sales", "traffic"], "min_budget": 1},
            {"name": "meta_ads", "display_name": "Meta Ads", "strengths": ["social", "visual"], "avg_cpm": 12, "avg_cpc": 1.5, "best_for": ["awareness", "sales"], "min_budget": 1},
            {"name": "oceanengine", "display_name": "巨量引擎", "strengths": ["short_video", "livestream"], "avg_cpm": 15, "avg_cpc": 3, "best_for": ["awareness", "sales", "app_installs"], "min_budget": 300},
            {"name": "tencent_ads", "display_name": "腾讯广告", "strengths": ["social", "mini_program"], "avg_cpm": 18, "avg_cpc": 2.8, "best_for": ["conversions", "gaming"], "min_budget": 50},
            {"name": "kuaishou", "display_name": "快手", "strengths": ["short_video", "lower_tier"], "avg_cpm": 10, "avg_cpc": 2, "best_for": ["awareness", "sales"], "min_budget": 100},
            {"name": "baidu_ads", "display_name": "百度营销", "strengths": ["search", "B2B"], "avg_cpm": 5, "avg_cpc": 4, "best_for": ["leads", "B2B"], "min_budget": 50},
        ]

        overseas = ["google_ads", "meta_ads"]
        domestic = ["oceanengine", "tencent_ads", "kuaishou", "baidu_ads"]

        if target_market == "domestic":
            return [p for p in all_platforms if p["name"] in domestic]
        elif target_market == "overseas":
            return [p for p in all_platforms if p["name"] in overseas]
        return all_platforms

    def _print_decision(self, result: Dict[str, Any]):
        """打印AI决策结果"""
        self.logger.info(f"\n{'='*60}")
        self.logger.info("[AI Loop] 决策结果:")
        self.logger.info(f"{'='*60}")

        if "decision" in result and result["decision"]:
            decision = result["decision"]
            self.logger.info(f"策略: {decision.get('strategy', 'N/A')}")
            self.logger.info(f"选中平台: {result.get('selected_platforms', [])}")
            self.logger.info(f"预算分配: {result.get('budget_allocation', {})}")
            if decision.get("risk_factors"):
                self.logger.info(f"风险提示: {decision['risk_factors']}")

        if result.get("pause_reason"):
            self.logger.info(f"[暂停] {result['pause_reason']}")
            self.logger.info("使用 resume_loop() 继续执行")

        self.logger.info(f"状态: {result.get('status', 'unknown')}")
        self.logger.info(f"迭代: {result.get('iteration', 0)}")


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(description="AdCast Agent - AI自动广告投放 (LangGraph Loop)")

    # 子命令
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # run 命令 - AI Loop模式
    run_parser = subparsers.add_parser("run", help="启动AI Loop投放")
    run_parser.add_argument("--name", "-n", required=True, help="Campaign名称")
    run_parser.add_argument("--objective", "-o", default="conversions",
                           choices=["conversions", "awareness", "traffic", "sales",
                                   "leads", "app_installs", "video_views"],
                           help="投放目标")
    run_parser.add_argument("--budget", "-b", type=float, default=3000, help="总预算")
    run_parser.add_argument("--daily-budget", "-d", type=float, default=0, help="日预算")
    run_parser.add_argument("--market", "-m", default="global",
                           choices=["global", "domestic", "overseas"],
                           help="目标市场")
    run_parser.add_argument("--industry", default=None, help="行业")
    run_parser.add_argument("--interval", type=int, default=60, help="循环间隔（分钟）")
    run_parser.add_argument("--max-iter", type=int, default=10, help="最大迭代次数")
    run_parser.add_argument("--continuous", action="store_true", help="持续运行模式")
    run_parser.add_argument("--strategy", "-s", default="roas_maximize",
                           choices=["roas_maximize", "reach_maximize", "conversion_maximize",
                                   "balanced", "cost_minimize"],
                           help="投放策略（One-shot模式）")

    # status 命令
    status_parser = subparsers.add_parser("status", help="查看Loop状态")
    status_parser.add_argument("--name", "-n", required=True, help="Campaign名称")

    # resume 命令
    resume_parser = subparsers.add_parser("resume", help="恢复Loop")
    resume_parser.add_argument("--name", "-n", required=True, help="Campaign名称")

    # pause 命令
    pause_parser = subparsers.add_parser("pause", help="暂停Loop")
    pause_parser.add_argument("--name", "-n", required=True, help="Campaign名称")

    # oneshot 命令 - 传统模式
    oneshot_parser = subparsers.add_parser("oneshot", help="传统One-shot投放")
    oneshot_parser.add_argument("--name", "-n", required=True, help="Campaign名称")
    oneshot_parser.add_argument("--objective", "-o", default="conversions",
                               choices=["conversions", "awareness", "traffic", "sales",
                                       "leads", "app_installs", "video_views"],
                               help="投放目标")
    oneshot_parser.add_argument("--budget", "-b", type=float, default=3000, help="总预算")
    oneshot_parser.add_argument("--daily-budget", "-d", type=float, default=0, help="日预算")
    oneshot_parser.add_argument("--market", "-m", default="global",
                               choices=["global", "domestic", "overseas"],
                               help="目标市场")
    oneshot_parser.add_argument("--auto-activate", action="store_true",
                               help="自动激活")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    async def run():
        agent = AdCastAgent()

        try:
            await agent.initialize()

            if args.command == "run":
                # AI Loop模式
                result = await agent.run_ai_loop(
                    name=args.name,
                    objective=args.objective,
                    budget=args.budget,
                    daily_budget=args.daily_budget,
                    target_market=args.market,
                    industry=args.industry,
                    interval_minutes=args.interval,
                    max_iterations=args.max_iter,
                    continuous=args.continuous,
                )
                print("\n" + "=" * 60)
                print(json.dumps(result, indent=2, ensure_ascii=False, default=str))

            elif args.command == "status":
                result = await agent.get_loop_status(args.name)
                print(json.dumps(result, indent=2, ensure_ascii=False, default=str))

            elif args.command == "resume":
                result = await agent.resume_loop(args.name)
                print(json.dumps(result, indent=2, ensure_ascii=False, default=str))

            elif args.command == "pause":
                await agent.pause_loop(args.name)
                print(f"Campaign '{args.name}' paused")

            elif args.command == "oneshot":
                # 传统One-shot模式
                result = await agent.run_campaign(
                    name=args.name,
                    objective=args.objective,
                    budget=args.budget,
                    daily_budget=args.daily_budget,
                    target_market=args.market,
                    auto_activate=args.auto_activate,
                )
                print(json.dumps(result, indent=2, ensure_ascii=False, default=str))

        except KeyboardInterrupt:
            print("\n正在关闭...")
        finally:
            await agent.shutdown()

    asyncio.run(run())


if __name__ == "__main__":
    main()
