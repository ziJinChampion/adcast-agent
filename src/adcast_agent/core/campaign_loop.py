"""
Campaign 闭环管理器 - Observe-Analyze-Act Loop 生命周期管理

负责：
1. 启动/恢复 LangGraph 执行
2. 管理Checkpoint持久化
3. 处理人工审批后的继续执行
4. 定时触发新一轮循环（数据收集后）
5. 监控Loop健康状态
"""

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional
from datetime import datetime, timedelta

from .agent_graph import (
    AgentState, build_agent_graph,
    node_observe, node_analyze, node_decide, node_execute, node_reflect,
)
from .checkpoint import CheckpointManager, BaseCheckpoint
from .long_term_memory import BaseLongTermMemory, get_long_term_memory
from .llm_client import LLMClient

logger = logging.getLogger("adcast.loop")


class CampaignLoop:
    """
    Campaign闭环管理器
    
    每个Campaign对应一个Loop实例，通过LangGraph状态图驱动。
    Checkpoint确保每次迭代的状态可恢复。
    """

    def __init__(
        self,
        campaign_name: str,
        checkpoint_manager: CheckpointManager,
        llm_client: Optional[LLMClient] = None,
        interval_minutes: int = 60,       # 每次循环间隔
        max_iterations: int = 10,
    ):
        self.campaign_name = campaign_name
        self.checkpoint = checkpoint_manager
        self.llm_client = llm_client
        self.interval_minutes = interval_minutes
        self.max_iterations = max_iterations

        self._graph = None
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def initialize(self):
        """初始化Loop - 编译LangGraph"""
        self._graph = build_agent_graph(self.checkpoint)
        if self._graph is None:
            logger.error("Failed to build agent graph - langgraph may not be installed")
            return False
        logger.info(f"CampaignLoop initialized for '{self.campaign_name}'")
        return True

    async def start(
        self,
        campaign_config: Dict[str, Any],
        platform_data: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """
        启动新Loop
        
        1. 构建初始状态
        2. 保存checkpoint
        3. 执行第一轮
        """
        thread_id = f"campaign_{self.campaign_name}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        # 构建初始状态
        initial_state = AgentState(
            thread_id=thread_id,
            campaign_name=campaign_config.get("name", self.campaign_name),
            campaign_objective=campaign_config.get("objective", "conversions"),
            campaign_budget=campaign_config.get("budget", 3000),
            campaign_daily_budget=campaign_config.get("daily_budget", 100),
            campaign_target_market=campaign_config.get("target_market", "global"),
            campaign_industry=campaign_config.get("industry"),
            campaign_audience=campaign_config.get("audience"),
            campaign_creative_type=campaign_config.get("creative_type", "video"),
            max_iterations=self.max_iterations,
            platform_data=platform_data or [],
            _llm_config=campaign_config.get("_llm_config", {}),
        )

        logger.info(f"[Loop] Starting campaign loop: {thread_id}")

        # 保存初始checkpoint
        self.checkpoint.put(thread_id, dict(initial_state))

        # 执行第一轮
        return await self._run_iteration(initial_state)

    async def resume(self, thread_id: str) -> Dict[str, Any]:
        """
        从Checkpoint恢复Loop
        
        用于：
        - 人工审批后继续
        - 进程重启后恢复
        - 定时触发下一轮
        """
        # 从checkpoint恢复状态
        saved_state = self.checkpoint.get(thread_id)
        if not saved_state:
            raise ValueError(f"No checkpoint found for thread: {thread_id}")

        state = AgentState(**saved_state)

        # 清除暂停状态
        state["pause_reason"] = None
        state["should_continue"] = True

        logger.info(f"[Loop] Resuming campaign loop: {thread_id} (iteration {state.get('iteration', 0)})")

        return await self._run_iteration(state)

    async def run_continuous(self, campaign_config: Dict[str, Any]):
        """
        持续运行Loop - 定时触发
        
        每隔 interval_minutes 分钟执行一轮：
        1. 拉取最新报表数据
        2. 运行一次完整循环
        3. 保存checkpoint
        4. 等待下一次触发
        """
        self._running = True

        # 首次启动
        result = await self.start(campaign_config)
        thread_id = result.get("thread_id", "")

        if not thread_id:
            logger.error("Failed to get thread_id from initial run")
            return

        logger.info(f"[Loop] Continuous mode started, interval={self.interval_minutes}min")

        while self._running:
            try:
                # 等待间隔
                await asyncio.sleep(self.interval_minutes * 60)

                if not self._running:
                    break

                # 恢复并执行下一轮
                logger.info(f"[Loop] Triggering iteration for {thread_id}")
                result = await self.resume(thread_id)

                # 检查是否应该停止
                if result.get("status") == "completed":
                    logger.info(f"[Loop] Campaign loop completed: {thread_id}")
                    break

            except asyncio.CancelledError:
                logger.info("[Loop] Continuous loop cancelled")
                break
            except Exception as e:
                logger.error(f"[Loop] Error in continuous loop: {e}")
                await asyncio.sleep(60)  # 出错后等待1分钟重试

    def stop(self):
        """停止Loop"""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
        logger.info(f"[Loop] Campaign loop stopped: {self.campaign_name}")

    async def _run_iteration(self, state: AgentState) -> Dict[str, Any]:
        """
        执行一次完整迭代
        
        手动执行各节点（兼容不安装langgraph的情况）
        """
        thread_id = state.get("thread_id", "")
        iteration = state.get("iteration", 0)

        logger.info(f"[Loop] Running iteration {iteration} for {thread_id}")

        try:
            # 如果安装了langgraph，使用编译后的图
            if self._graph is not None:
                # 通过LangGraph执行
                config = {"configurable": {"thread_id": thread_id}}

                # 使用invoke直接执行完整图
                try:
                    final_state = self._graph.invoke(dict(state), config=config)
                    result_state = AgentState(**final_state)
                except Exception as e:
                    logger.warning(f"LangGraph invoke failed, falling back to manual: {e}")
                    result_state = await self._run_manual(state)
            else:
                # 手动执行各节点（降级方案）
                result_state = await self._run_manual(state)

            # 保存checkpoint
            self.checkpoint.put(thread_id, dict(result_state))

            # 构建结果
            return {
                "thread_id": thread_id,
                "iteration": result_state.get("iteration", 0),
                "status": "paused" if result_state.get("pause_reason") else (
                    "completed" if not result_state.get("should_continue", True) else "running"
                ),
                "pause_reason": result_state.get("pause_reason"),
                "selected_platforms": result_state.get("selected_platforms", []),
                "budget_allocation": result_state.get("budget_allocation", {}),
                "decision": result_state.get("decision"),
                "learning_notes": result_state.get("learning_notes", []),
                "should_continue": result_state.get("should_continue", False),
            }

        except Exception as e:
            logger.error(f"[Loop] Iteration failed: {e}")
            return {
                "thread_id": thread_id,
                "iteration": iteration,
                "status": "error",
                "error": str(e),
            }

    async def _run_manual(self, state: AgentState) -> AgentState:
        """
        手动执行各节点（不依赖LangGraph的降级方案）
        
        按顺序执行: observe -> analyze -> decide -> execute -> reflect
        """
        logger.info("[Loop] Running manual node execution")

        # observe
        state = await node_observe(state)

        # analyze
        state = await node_analyze(state)

        # decide
        state = await node_decide(state)

        # 检查是否暂停
        if state.get("pause_reason"):
            return state

        # execute
        state = await node_execute(state)

        # reflect
        state = await node_reflect(state)

        return state

    async def update_report_data(
        self,
        thread_id: str,
        platform_reports: Dict[str, List[Dict]],
    ) -> bool:
        """
        更新报表数据到checkpoint
        
        定时任务调用此方法来推送最新报表数据，
        下次resume时会使用这些数据进行分析和决策。
        """
        saved_state = self.checkpoint.get(thread_id)
        if not saved_state:
            return False

        state = AgentState(**saved_state)
        state["platform_reports"] = platform_reports
        state["should_continue"] = True  # 有新数据，可以继续

        self.checkpoint.put(thread_id, dict(state))
        logger.info(f"[Loop] Report data updated for {thread_id}: {len(platform_reports)} platforms")
        return True

    async def get_status(self, thread_id: str) -> Dict[str, Any]:
        """获取Loop状态"""
        saved_state = self.checkpoint.get(thread_id)
        if not saved_state:
            return {"error": "Thread not found"}

        state = AgentState(**saved_state)
        return {
            "thread_id": thread_id,
            "campaign_name": state.get("campaign_name"),
            "iteration": state.get("iteration", 0),
            "max_iterations": state.get("max_iterations", 10),
            "status": "paused" if state.get("pause_reason") else (
                "completed" if not state.get("should_continue", True) else "running"
            ),
            "pause_reason": state.get("pause_reason"),
            "selected_platforms": state.get("selected_platforms", []),
            "budget_allocation": state.get("budget_allocation", {}),
            "learning_notes": state.get("learning_notes", []),
        }


class LoopScheduler:
    """
    Loop调度器 - 管理多个Campaign的定时循环
    
    类似于cron，但针对Campaign Loop优化：
    - 每个Campaign有独立的触发间隔
    - 支持暂停/恢复单个Campaign
    - 统一的错误处理和重试
    """

    def __init__(self, checkpoint_manager: CheckpointManager):
        self.checkpoint = checkpoint_manager
        self._loops: Dict[str, CampaignLoop] = {}      # campaign_name -> CampaignLoop
        self._tasks: Dict[str, asyncio.Task] = {}      # campaign_name -> Task
        self._running = False

    async def register_campaign(
        self,
        campaign_name: str,
        config: Dict[str, Any],
        llm_client: Optional[LLMClient] = None,
        interval_minutes: int = 60,
    ) -> CampaignLoop:
        """注册一个Campaign到调度器"""
        loop = CampaignLoop(
            campaign_name=campaign_name,
            checkpoint_manager=self.checkpoint,
            llm_client=llm_client,
            interval_minutes=interval_minutes,
        )
        await loop.initialize()

        self._loops[campaign_name] = loop
        logger.info(f"[Scheduler] Registered campaign: {campaign_name}")
        return loop

    async def start_campaign(self, campaign_name: str, config: Dict[str, Any]):
        """启动指定Campaign的循环"""
        loop = self._loops.get(campaign_name)
        if not loop:
            loop = await self.register_campaign(campaign_name, config)

        # 启动持续运行
        task = asyncio.create_task(
            loop.run_continuous(config),
            name=f"loop_{campaign_name}",
        )
        self._tasks[campaign_name] = task
        self._running = True

        logger.info(f"[Scheduler] Started campaign loop: {campaign_name}")

    async def pause_campaign(self, campaign_name: str):
        """暂停Campaign"""
        loop = self._loops.get(campaign_name)
        if loop:
            loop.stop()

        task = self._tasks.get(campaign_name)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        logger.info(f"[Scheduler] Paused campaign: {campaign_name}")

    async def resume_campaign(self, campaign_name: str):
        """恢复Campaign - 找到thread_id并继续"""
        loop = self._loops.get(campaign_name)
        if not loop:
            logger.warning(f"Campaign not found: {campaign_name}")
            return

        # 查找最新的thread_id
        threads = self.checkpoint.list_threads(limit=10)
        matching_threads = [
            t for t in threads
            if t.startswith(f"campaign_{campaign_name}_")
        ]

        if not matching_threads:
            logger.warning(f"No checkpoint found for campaign: {campaign_name}")
            return

        latest_thread = matching_threads[0]
        result = await loop.resume(latest_thread)
        logger.info(f"[Scheduler] Resumed campaign: {campaign_name} -> {result.get('status')}")
        return result

    async def stop_all(self):
        """停止所有Campaign"""
        for name, loop in self._loops.items():
            loop.stop()

        for name, task in self._tasks.items():
            if not task.done():
                task.cancel()

        self._running = False
        logger.info("[Scheduler] All campaigns stopped")

    def list_running(self) -> List[str]:
        """列出运行中的Campaign"""
        return [
            name for name, task in self._tasks.items()
            if not task.done()
        ]

    async def update_reports(self, campaign_name: str, platform_reports: Dict[str, List[Dict]]):
        """推送报表数据到指定Campaign"""
        loop = self._loops.get(campaign_name)
        if not loop:
            return False

        # 查找thread_id
        threads = self.checkpoint.list_threads(limit=10)
        for t in threads:
            if t.startswith(f"campaign_{campaign_name}_"):
                return await loop.update_report_data(t, platform_reports)

        return False
