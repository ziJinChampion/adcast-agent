"""
LangGraph AI Agent 决策图 - Observe-Analyze-Act 闭环

核心架构：
    +---------+     +---------+     +---------+     +---------+     +----------+
    | OBSERVE | --> | ANALYZE | --> | DECIDE  | --> | EXECUTE | --> | REFLECT  |
    |  收集   |     |  分析   |     |  决策   |     |  执行   |     |  反思    |
    +---------+     +---------+     +---------+     +---------+     +----------+
                                                         |                 |
                                                         |                 v
                                                         |          +----------+
                                                         +------->  |  CONTINUE?|
                                                                    | (条件分支) |
                                                                    +----------+
                                                                    是 |    | 否
                                                                       |    v
                                                                       v   END
                                                                 OBSERVE

状态持久化：通过 CheckpointManager 在每个节点后自动保存
长期记忆：通过 VectorLongTermMemory 在 observe/analyze/decide/reflect 节点 RAG 增强
"""

import json
import logging
from typing import Any, Dict, List, Optional, Literal
from datetime import datetime
from enum import Enum

try:
    from langgraph.graph import StateGraph, END
    from langgraph.constants import START
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    # 占位符，用于类型检查
    StateGraph = object
    END = "__end__"
    START = "__start__"

from .llm_client import LLMClient, get_llm_client
from .checkpoint import CheckpointManager
from .long_term_memory import get_long_term_memory

logger = logging.getLogger("adcast.agent_graph")


# ============ 状态定义 ============

class AgentState(dict):
    """
    Agent状态 - TypedDict风格的字典
    
    所有字段都是可选的，便于增量更新。
    LangGraph在每个节点间传递此状态对象。
    """

    # 元数据
    thread_id: str
    created_at: str
    iteration: int           # 当前循环迭代次数
    max_iterations: int      # 最大迭代次数（防止无限循环）

    # Campaign上下文
    campaign_name: str
    campaign_objective: str
    campaign_budget: float
    campaign_daily_budget: float
    campaign_target_market: str
    campaign_audience: Optional[Dict]
    campaign_industry: Optional[str]
    campaign_creative_type: str
    campaign_start_date: Optional[str]
    campaign_end_date: Optional[str]

    # 平台数据（OBSERVE阶段填充）
    platform_data: List[Dict[str, Any]]      # 各平台能力/预测数据
    platform_reports: Dict[str, List]        # 各平台报表数据
    historical_data: Dict[str, Any]          # 历史表现数据（含RAG上下文）

    # LLM分析结果（ANALYZE阶段填充）
    llm_analysis: Optional[Dict[str, Any]]   # LLM分析结果
    platform_scores: List[Dict[str, Any]]    # 平台评分

    # 决策结果（DECIDE阶段填充）
    decision: Optional[Dict[str, Any]]       # 最终决策
    selected_platforms: List[str]            # 选中的平台
    budget_allocation: Dict[str, float]      # 预算分配

    # 执行结果（EXECUTE阶段填充）
    execution_results: Dict[str, Any]        # 执行结果
    created_campaigns: Dict[str, str]        # platform -> campaign_id

    # 反思结果（REFLECT阶段填充）
    reflection: Optional[Dict[str, Any]]     # 反思结果
    learning_notes: List[str]                # 学习笔记

    # 控制流
    next_action: Literal["observe", "analyze", "decide", "execute", "reflect", "end"]
    should_continue: bool                    # 是否继续循环
    pause_reason: Optional[str]              # 暂停原因（人工审批等）

    def __init__(self, **kwargs):
        super().__init__()
        defaults = {
            "thread_id": f"campaign_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "created_at": datetime.utcnow().isoformat(),
            "iteration": 0,
            "max_iterations": 10,
            "platform_data": [],
            "platform_reports": {},
            "historical_data": {},
            "selected_platforms": [],
            "budget_allocation": {},
            "execution_results": {},
            "created_campaigns": {},
            "learning_notes": [],
            "should_continue": True,
            "next_action": "observe",
        }
        defaults.update(kwargs)
        self.update(defaults)


# ============ 节点函数 ============

async def node_observe(state: AgentState) -> AgentState:
    """
    OBSERVE 节点 - 收集所有相关数据（已集成向量长期记忆RAG）
    
    1. 收集各平台能力数据
    2. 通过向量记忆语义搜索相似Campaign历史
    3. 通过RAG查询获取格式化的历史投放经验
    4. 整合所有数据到 historical_data
    """
    logger.info(f"[OBSERVE] Iteration {state['iteration']} - Collecting data...")

    new_state = AgentState(**state)
    new_state["iteration"] = state.get("iteration", 0) + 1

    # 构建Campaign请求摘要（用于向量搜索）
    campaign_request = {
        "name": state.get("campaign_name", ""),
        "objective": state.get("campaign_objective", ""),
        "budget": state.get("campaign_budget", 0),
        "daily_budget": state.get("campaign_daily_budget", 0),
        "target_market": state.get("campaign_target_market", "global"),
        "industry": state.get("campaign_industry", ""),
        "creative_type": state.get("campaign_creative_type", "video"),
        "audience": state.get("campaign_audience"),
    }

    # === 向量记忆查询（深度集成）===
    memory = get_long_term_memory()
    similar_campaigns = []
    rag_context = ""

    # 1. 语义搜索相似 Campaign 历史
    try:
        if hasattr(memory, "find_similar_campaigns"):
            similar_campaigns = await memory.find_similar_campaigns(campaign_request, limit=3)
            logger.info(f"[OBSERVE] Found {len(similar_campaigns)} similar campaigns from memory")
    except Exception as e:
        logger.warning(f"[OBSERVE] find_similar_campaigns failed: {e}")

    # 2. RAG 查询历史投放经验
    try:
        if hasattr(memory, "rag_query"):
            objective = state.get("campaign_objective", "")
            industry = state.get("campaign_industry", "")
            rag_query_text = f"{objective} campaign experience {industry}".strip()
            rag_context = await memory.rag_query(
                query=rag_query_text,
                context_type="campaign_experience",
                limit=5,
            )
            if rag_context:
                logger.info(f"[OBSERVE] RAG context: {len(rag_context)} chars")
    except Exception as e:
        logger.warning(f"[OBSERVE] RAG query failed: {e}")

    # 3. 获取默认平台数据（如果没有实际平台数据）
    platform_data = new_state.get("platform_data", [])
    if not platform_data:
        platform_data = _get_default_platform_data(state.get("campaign_target_market", "global"))
    new_state["platform_data"] = platform_data

    # 4. 整合所有数据到 historical_data
    new_state["historical_data"] = {
        "past_experiences": similar_campaigns,
        "rag_context": rag_context,
        "campaign_request": campaign_request,
        "industry": campaign_request.get("industry", ""),
        "objective": campaign_request.get("objective", ""),
    }

    logger.info(f"[OBSERVE] {len(platform_data)} platforms, "
                f"{len(similar_campaigns)} similar campaigns, "
                f"RAG {len(rag_context)} chars")

    new_state["next_action"] = "analyze"
    return new_state


async def node_analyze(state: AgentState) -> AgentState:
    """
    ANALYZE 节点 - LLM分析数据（已集成RAG历史经验增强）
    
    1. 从 historical_data 提取 RAG 上下文和相似 Campaign
    2. 将历史经验拼接到 campaign_request 的 _memory_context 字段
    3. 调用 LLM 进行平台选择分析（增强版prompt）
    """
    logger.info(f"[ANALYZE] Analyzing with LLM (RAG-enhanced)...")

    new_state = AgentState(**state)

    # 获取LLM客户端
    llm_config = state.get("_llm_config", {})
    llm = get_llm_client(llm_config)

    # 构建分析请求
    campaign_request = {
        "name": state.get("campaign_name", ""),
        "objective": state.get("campaign_objective", ""),
        "budget": state.get("campaign_budget", 0),
        "daily_budget": state.get("campaign_daily_budget", 0),
        "target_market": state.get("campaign_target_market", "global"),
        "industry": state.get("campaign_industry", ""),
        "creative_type": state.get("campaign_creative_type", "video"),
        "audience": state.get("campaign_audience"),
    }

    platform_data = state.get("platform_data", [])
    if not platform_data:
        platform_data = _get_default_platform_data(state.get("campaign_target_market", "global"))

    # === 构建增强的 LLM prompt（RAG 上下文注入）===
    historical_data = state.get("historical_data", {})
    rag_context = historical_data.get("rag_context", "")
    similar_campaigns = historical_data.get("past_experiences", [])

    memory_context_parts = []
    
    if rag_context:
        memory_context_parts.append(f"=== 历史投放经验（来自长期记忆）===\n{rag_context}")
    
    if similar_campaigns:
        camp_lines = ["\n=== 相似 Campaign 历史 ==="]
        for i, camp in enumerate(similar_campaigns[:3], 1):
            data = camp.get("data", {})
            camp_lines.append(
                f"\n[{i}] 平台: {data.get('platform', 'N/A')}, "
                f"目标: {data.get('objective', 'N/A')}, "
                f"行业: {data.get('industry', 'N/A')}\n"
                f"    ROAS: {data.get('roas', 'N/A')}, "
                f"CPA: {data.get('cpa', 'N/A')}, "
                f"花费: {data.get('spend', 'N/A')}\n"
                f"    备注: {str(data.get('notes', ''))[:200]}"
            )
        memory_context_parts.append("\n".join(camp_lines))

    # 将 memory_context 注入到 campaign_request 的 _memory_context 字段
    # llm.decide_platform 方法会读取这个字段并拼接到 prompt
    campaign_request["_memory_context"] = "\n\n".join(memory_context_parts)

    try:
        # 调用LLM进行决策分析（prompt 中已包含历史经验）
        llm_result = await llm.decide_platform(campaign_request, platform_data)

        new_state["llm_analysis"] = llm_result

        # 提取平台评分
        platforms = llm_result.get("platforms", [])
        new_state["platform_scores"] = platforms

        # 提取选中平台
        selected = [p["name"] for p in platforms if p.get("score", 0) > 50]
        new_state["selected_platforms"] = selected

        reasoning = llm_result.get("reasoning", "")
        logger.info(f"[ANALYZE] LLM reasoning: {reasoning[:200]}...")
        logger.info(f"[ANALYZE] Selected platforms: {selected}")

    except Exception as e:
        logger.error(f"[ANALYZE] LLM analysis failed: {e}")
        new_state["llm_analysis"] = {"error": str(e), "reasoning": "Fallback to rule-based"}
        # 降级到规则基础的选择
        new_state["selected_platforms"] = _fallback_platform_selection(state)

    new_state["next_action"] = "decide"
    return new_state


async def node_decide(state: AgentState) -> AgentState:
    """
    DECIDE 节点 - 做出最终决策（已集成历史预算查询）
    
    1. 综合LLM分析和规则引擎的结果
    2. 查询历史预算分配作为参考
    3. 确定预算分配
    4. 检查是否需要人工审批
    """
    logger.info(f"[DECIDE] Making final decision...")

    new_state = AgentState(**state)

    selected_platforms = new_state.get("selected_platforms", [])
    llm_analysis = new_state.get("llm_analysis", {})
    total_budget = new_state.get("campaign_daily_budget", 100)

    # === 查询历史预算分配作为参考 ===
    memory = get_long_term_memory()
    historical_budgets: Dict[str, float] = {}
    
    try:
        if hasattr(memory, "search") and selected_platforms:
            objective = state.get("campaign_objective", "")
            for platform in selected_platforms:
                budget_results = await memory.search(
                    query=f"{platform} budget allocation {objective}",
                    tags=["campaign_experience"],
                    limit=2,
                )
                if budget_results:
                    allocations = [
                        r.get("data", {}).get("budget_allocation", {}).get(platform, 0)
                        for r in budget_results
                        if r.get("data", {}).get("budget_allocation", {}).get(platform)
                    ]
                    if allocations:
                        avg_budget = sum(allocations) / len(allocations)
                        if avg_budget > 0:
                            historical_budgets[platform] = avg_budget
    except Exception as e:
        logger.warning(f"[DECIDE] Historical budget search failed: {e}")

    # 预算分配：优先使用LLM推荐，其次参考历史数据，最后均分
    budget_allocation = {}
    platforms_data = llm_analysis.get("platforms", [])

    if platforms_data:
        # 使用LLM推荐的分配比例
        for p in platforms_data:
            name = p.get("name", "")
            pct = p.get("budget_allocation_pct", 0)
            if name and pct > 0:
                budget_allocation[name] = total_budget * (pct / 100)

    # 如果LLM没有分配，参考历史数据
    if not budget_allocation and historical_budgets:
        total_hist = sum(historical_budgets.values())
        if total_hist > 0:
            for platform in selected_platforms:
                hist = historical_budgets.get(platform, 0)
                budget_allocation[platform] = total_budget * (hist / total_hist)

    # Fallback: 均分
    if not budget_allocation and selected_platforms:
        per_platform = total_budget / len(selected_platforms)
        for p in selected_platforms:
            budget_allocation[p] = per_platform

    new_state["budget_allocation"] = budget_allocation
    new_state["decision"] = {
        "platforms": selected_platforms,
        "budget_allocation": budget_allocation,
        "strategy": llm_analysis.get("overall_strategy", ""),
        "risk_factors": llm_analysis.get("risk_factors", []),
        "reasoning": llm_analysis.get("reasoning", ""),
        "timestamp": datetime.utcnow().isoformat(),
    }

    # 检查是否需要人工审批（高风险操作）
    risk_factors = llm_analysis.get("risk_factors", [])
    total_spend_risk = new_state.get("campaign_budget", 0) > 10000

    if risk_factors or total_spend_risk:
        new_state["pause_reason"] = f"High risk detected: {risk_factors}. Awaiting approval."
        new_state["should_continue"] = False
        logger.info(f"[DECIDE] Paused for approval: {new_state['pause_reason']}")
    else:
        new_state["should_continue"] = True

    logger.info(f"[DECIDE] Decision: platforms={selected_platforms}, "
                f"budget={budget_allocation}")

    new_state["next_action"] = "execute"
    return new_state


async def node_execute(state: AgentState) -> AgentState:
    """
    EXECUTE 节点 - 执行决策动作
    
    1. 在各平台创建Campaign
    2. 设置预算和参数
    3. 收集执行结果
    """
    logger.info(f"[EXECUTE] Executing decisions...")

    new_state = AgentState(**state)

    # 注：实际执行需要接入platform_manager
    # 这里记录执行计划，实际创建由外部调用完成
    execution_results = {}
    created_campaigns = {}

    for platform, budget in state.get("budget_allocation", {}).items():
        execution_results[platform] = {
            "status": "PLANNED",
            "budget": budget,
            "platform": platform,
            "campaign_name": f"{state.get('campaign_name', '')} - {platform}",
        }
        created_campaigns[platform] = "pending"  # 待外部执行后更新

    new_state["execution_results"] = execution_results
    new_state["created_campaigns"] = created_campaigns

    logger.info(f"[EXECUTE] Planned campaigns for {len(execution_results)} platforms")

    new_state["next_action"] = "reflect"
    return new_state


async def node_reflect(state: AgentState) -> AgentState:
    """
    REFLECT 节点 - 反思和学习（已集成向量embedding保存）
    
    1. 评估执行结果
    2. 提取学习要点
    3. 使用向量embedding保存Campaign经验到长期记忆
    4. 决定是否继续循环
    """
    logger.info(f"[REFLECT] Reflecting on results...")

    new_state = AgentState(**state)

    # 收集学习笔记
    learning_notes = []
    iteration = new_state.get("iteration", 0)
    max_iterations = new_state.get("max_iterations", 10)

    # 基于当前迭代生成学习笔记
    if iteration == 1:
        learning_notes.append(f"Initial campaign setup for {state.get('campaign_name', '')}")
        learning_notes.append(f"Selected platforms: {state.get('selected_platforms', [])}")

    # 如果有报表数据，分析表现
    platform_reports = state.get("platform_reports", {})
    if platform_reports:
        try:
            llm = get_llm_client(state.get("_llm_config", {}))
            performance_analysis = await llm.analyze_performance(
                {
                    "name": state.get("campaign_name", ""),
                    "objective": state.get("campaign_objective", ""),
                    "budget": state.get("campaign_budget", 0),
                },
                platform_reports,
            )

            actions = performance_analysis.get("actions", [])
            for action in actions:
                learning_notes.append(
                    f"{action.get('platform')}: {action.get('action')} - {action.get('reason', '')}"
                )

            new_state["reflection"] = performance_analysis

        except Exception as e:
            logger.warning(f"[REFLECT] Performance analysis failed: {e}")

    # === 使用向量embedding保存Campaign经验（深度集成）===
    memory = get_long_term_memory()
    
    try:
        if hasattr(memory, "save_campaign_experience"):
            # 为每个选中的平台保存经验
            for platform in state.get("selected_platforms", []):
                exec_result = state.get("execution_results", {}).get(platform, {})
                platform_scores = state.get("platform_scores", [])
                platform_score = next(
                    (p for p in platform_scores if p.get("name") == platform), {}
                )

                await memory.save_campaign_experience({
                    "campaign_name": state.get("campaign_name", ""),
                    "campaign_id": state.get("thread_id", ""),
                    "platform": platform,
                    "objective": state.get("campaign_objective", ""),
                    "industry": state.get("campaign_industry", ""),
                    "target_market": state.get("campaign_target_market", ""),
                    "budget": state.get("budget_allocation", {}).get(platform, 0),
                    "roas": platform_score.get("score", 0) / 25 if platform_score.get("score") else 0,
                    "score": platform_score.get("score", 0),
                    "confidence": platform_score.get("confidence", "medium"),
                    "iteration": iteration,
                    "notes": f"Platform {platform} selected in iteration {iteration}. "
                             f"Learning: {'; '.join(learning_notes[-3:])}",
                })
                logger.info(f"[REFLECT] Campaign experience saved for {platform}")

        # 同时保存一个聚合的迭代记录
        if hasattr(memory, "save"):
            await memory.save(
                key=f"campaign_iter:{state.get('thread_id', '')}:{iteration}",
                data={
                    "campaign_name": state.get("campaign_name", ""),
                    "iteration": iteration,
                    "platforms": state.get("selected_platforms", []),
                    "budget_allocation": state.get("budget_allocation", {}),
                    "learning_notes": learning_notes,
                    "decision": state.get("decision", {}),
                },
                tags=["campaign_iteration", state.get("campaign_objective", ""),
                      state.get("campaign_industry", "")],
            )
    except Exception as e:
        logger.warning(f"[REFLECT] Failed to save vector memory: {e}")

    new_state["learning_notes"] = learning_notes

    # 决定是否继续循环
    if iteration >= max_iterations:
        new_state["should_continue"] = False
        logger.info(f"[REFLECT] Max iterations ({max_iterations}) reached, ending loop")
    elif not platform_reports:
        # 首次执行后没有报表数据，等待数据积累
        new_state["should_continue"] = False
        new_state["pause_reason"] = "Waiting for performance data. Resume after data collection."
        logger.info(f"[REFLECT] No report data yet, pausing for data collection")
    else:
        new_state["should_continue"] = True
        logger.info(f"[REFLECT] Will continue to next iteration")

    new_state["next_action"] = "observe"
    return new_state


# ============ 条件边 ============

def should_continue(state: AgentState) -> str:
    """
    条件边：决定是否继续循环
    
    Returns:
        "observe" - 继续下一轮
        END - 结束循环
    """
    if not state.get("should_continue", True):
        return END

    iteration = state.get("iteration", 0)
    max_iter = state.get("max_iterations", 10)

    if iteration >= max_iter:
        logger.info(f"[LOOP] Max iterations reached ({iteration}/{max_iter}), ending")
        return END

    return "observe"


def check_pause(state: AgentState) -> str:
    """
    条件边：检查是否需要暂停等待审批
    
    Returns:
        "execute" - 继续执行
        END - 暂停（等待外部触发）
    """
    if state.get("pause_reason"):
        logger.info(f"[LOOP] Paused: {state['pause_reason']}")
        return END
    return "execute"


# ============ 图构建 ============

def build_agent_graph(checkpoint_manager: Optional[CheckpointManager] = None) -> Optional[Any]:
    """
    构建 LangGraph Agent 图
    
    Returns:
        Compiled graph ready for invocation
    """
    if not LANGGRAPH_AVAILABLE:
        logger.error("langgraph is not installed. Install: pip install langgraph")
        return None

    # 创建状态图
    workflow = StateGraph(AgentState)

    # 添加节点
    workflow.add_node("observe", node_observe)
    workflow.add_node("analyze", node_analyze)
    workflow.add_node("decide", node_decide)
    workflow.add_node("execute", node_execute)
    workflow.add_node("reflect", node_reflect)

    # 添加边
    workflow.add_edge(START, "observe")
    workflow.add_edge("observe", "analyze")
    workflow.add_edge("analyze", "decide")

    # decide -> execute（条件：是否需要暂停审批）
    workflow.add_conditional_edges(
        "decide",
        check_pause,
        {
            "execute": "execute",
            END: END,
        },
    )

    workflow.add_edge("execute", "reflect")

    # reflect -> observe（循环）或 END（结束）
    workflow.add_conditional_edges(
        "reflect",
        should_continue,
        {
            "observe": "observe",
            END: END,
        },
    )

    # 编译图
    compiled = workflow.compile()

    logger.info("Agent graph compiled with nodes: observe -> analyze -> decide -> execute -> reflect [loop]")
    return compiled


# ============ 辅助函数 ============

def _get_default_platform_data(target_market: str) -> List[Dict[str, Any]]:
    """获取默认平台数据（当未连接实际平台时使用）"""
    all_platforms = [
        {
            "name": "google_ads",
            "display_name": "Google Ads",
            "strengths": ["search", "shopping", "youtube"],
            "avg_cpm": 8.5,
            "avg_cpc": 2.5,
            "best_for": ["conversions", "sales", "traffic", "leads"],
            "min_budget": 1,
        },
        {
            "name": "meta_ads",
            "display_name": "Meta Ads (Facebook/Instagram)",
            "strengths": ["social", "visual", "ecommerce"],
            "avg_cpm": 12,
            "avg_cpc": 1.5,
            "best_for": ["awareness", "sales", "conversions", "engagement"],
            "min_budget": 1,
        },
        {
            "name": "oceanengine",
            "display_name": "巨量引擎 (抖音/头条)",
            "strengths": ["short_video", "livestream", "ecommerce"],
            "avg_cpm": 15,
            "avg_cpc": 3,
            "best_for": ["awareness", "sales", "app_installs", "livestream"],
            "min_budget": 300,
        },
        {
            "name": "tencent_ads",
            "display_name": "腾讯广告 (微信/视频号)",
            "strengths": ["social", "mini_program", "gaming"],
            "avg_cpm": 18,
            "avg_cpc": 2.8,
            "best_for": ["conversions", "app_installs", "gaming"],
            "min_budget": 50,
        },
        {
            "name": "amazon_dsp",
            "display_name": "Amazon DSP",
            "strengths": ["ecommerce", "retail", "purchase_intent"],
            "avg_cpm": 6,
            "avg_cpc": 1.2,
            "best_for": ["sales", "conversions", "retargeting"],
            "min_budget": 50000,
        },
        {
            "name": "kuaishou",
            "display_name": "快手磁力引擎",
            "strengths": ["short_video", "lower_tier_cities", "livestream"],
            "avg_cpm": 10,
            "avg_cpc": 2,
            "best_for": ["awareness", "sales", "app_installs"],
            "min_budget": 100,
        },
        {
            "name": "baidu_ads",
            "display_name": "百度营销",
            "strengths": ["search", "B2B"],
            "avg_cpm": 5,
            "avg_cpc": 4,
            "best_for": ["leads", "traffic", "B2B"],
            "min_budget": 50,
        },
        {
            "name": "adform",
            "display_name": "Adform FLOW",
            "strengths": ["display", "programmatic"],
            "avg_cpm": 7.5,
            "avg_cpc": 1.8,
            "best_for": ["awareness", "conversions", "traffic"],
            "min_budget": 1000,
        },
    ]

    # 根据目标市场过滤
    overseas = ["google_ads", "meta_ads", "amazon_dsp", "adform"]
    domestic = ["oceanengine", "tencent_ads", "kuaishou", "baidu_ads"]

    if target_market == "domestic":
        return [p for p in all_platforms if p["name"] in domestic]
    elif target_market == "overseas":
        return [p for p in all_platforms if p["name"] in overseas]
    return all_platforms


def _fallback_platform_selection(state: AgentState) -> List[str]:
    """LLM失败时的降级平台选择"""
    target_market = state.get("campaign_target_market", "global")
    objective = state.get("campaign_objective", "conversions")

    # 简单规则
    defaults = {
        "domestic": ["oceanengine", "tencent_ads"],
        "overseas": ["google_ads", "meta_ads"],
    }

    if objective in ("awareness", "brand"):
        if target_market == "domestic":
            return ["oceanengine", "tencent_ads"]
        return ["meta_ads", "google_ads"]

    return defaults.get(target_market, ["google_ads", "meta_ads", "oceanengine"])
