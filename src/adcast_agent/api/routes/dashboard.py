"""
仪表盘路由模块

提供 AdCast Agent 仪表盘所需的汇总数据。
"""

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List

from fastapi import APIRouter

from adcast_agent.api.deps import AgentDep
from adcast_agent.api.schemas import (
    DashboardResponse, KPIData, BudgetItem, ActivityItem,
    LoopResponse,
)

router = APIRouter()

# 预算饼图颜色
_BUDGET_COLORS = ["#06B6D4", "#8B5CF6", "#10B981", "#F59E0B", "#EF4444", "#EC4899", "#6366F1", "#14B8A6"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _minutes_ago(minutes: int) -> str:
    dt = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def _parse_state_to_loop(tid: str, state: Dict) -> LoopResponse:
    """将 AgentState 解析为 LoopResponse。"""
    campaign_name = state.get("campaign_name", "未命名")
    iteration = state.get("iteration", 0)
    max_iter = state.get("max_iterations", 10)
    pause_reason = state.get("pause_reason")
    should_continue = state.get("should_continue", False)

    if pause_reason:
        status = "paused"
    elif not should_continue:
        status = "completed"
    else:
        status = "running"

    budget_alloc = state.get("budget_allocation", {})
    total_budget = sum(budget_alloc.values()) if budget_alloc else 0.0

    execution = state.get("execution_results", {})
    spend = 0.0
    if isinstance(execution, dict):
        for _, r in execution.items():
            if isinstance(r, dict):
                spend += r.get("budget", 0.0) * 0.3

    platform_scores = state.get("platform_scores", [])
    roas = 0.0
    if isinstance(platform_scores, list):
        scores = [ps.get("score", 0) for ps in platform_scores if isinstance(ps, dict)]
        if scores:
            roas = round(sum(scores) / len(scores) / 25, 2)

    return LoopResponse(
        id=tid, name=campaign_name, status=status,
        iteration=iteration, maxIterations=max_iter,
        platforms=state.get("selected_platforms", []),
        budget=round(total_budget, 2), spend=round(spend, 2), roas=roas,
        threadId=tid, nextAction=state.get("next_action", "observe"),
    )


def _extract_activities(tid: str, state: Dict) -> List[ActivityItem]:
    """从 AgentState 提取活动记录。"""
    activities: List[ActivityItem] = []
    base = datetime.now(timezone.utc)

    execution = state.get("execution_results", {})
    if isinstance(execution, dict):
        for idx, (platform, result) in enumerate(execution.items()):
            if isinstance(result, dict):
                activities.append(ActivityItem(
                    id=f"{tid}_exec_{idx}", action="Campaign 执行",
                    platform=platform,
                    details=result.get("message", f"平台 {platform} 执行完成"),
                    timestamp=(base - timedelta(minutes=idx * 10)).strftime("%Y-%m-%dT%H:%M:%S"),
                    type="execute",
                ))

    learning_notes = state.get("learning_notes", [])
    if isinstance(learning_notes, list):
        for idx, note in enumerate(learning_notes):
            if isinstance(note, str):
                activities.append(ActivityItem(
                    id=f"{tid}_learn_{idx}", action="AI 学习笔记",
                    platform="all", details=note,
                    timestamp=(base - timedelta(minutes=idx * 15 + 5)).strftime("%Y-%m-%dT%H:%M:%S"),
                    type="analyze",
                ))

    return activities


def _generate_default_dashboard() -> DashboardResponse:
    """生成默认 Mock 仪表盘数据。"""
    return DashboardResponse(
        kpi=KPIData(totalCampaigns=5, activeLoops=2, totalSpend=26100.0, avgRoas=3.2),
        budgetAllocation=[
            BudgetItem(name="Google Ads", value=2000.0, fill="#06B6D4"),
            BudgetItem(name="Meta Ads", value=1800.0, fill="#8B5CF6"),
            BudgetItem(name="巨量引擎", value=1200.0, fill="#10B981"),
            BudgetItem(name="腾讯广告", value=900.0, fill="#F59E0B"),
            BudgetItem(name="快手", value=600.0, fill="#EF4444"),
        ],
        activeLoops=[
            LoopResponse(
                id="loop_001", name="Summer Sale 2024", status="running",
                iteration=4, maxIterations=10,
                platforms=["google_ads", "meta_ads", "oceanengine"],
                budget=5000.0, spend=2340.0, roas=3.2,
                threadId="campaign_summer_20240715", nextAction="REFLECT",
            ),
            LoopResponse(
                id="loop_002", name="Brand Awareness Q3", status="paused",
                iteration=2, maxIterations=10,
                platforms=["meta_ads", "tencent_ads"],
                budget=3000.0, spend=890.0, roas=1.8,
                threadId="campaign_brand_20240710", nextAction="ANALYZE",
            ),
        ],
        recentActivity=[
            ActivityItem(id="act1", action="Platform Selected", platform="google_ads",
                        details="AI selected Google Ads with score 92/100",
                        timestamp=_minutes_ago(5), type="decide"),
            ActivityItem(id="act2", action="Loop Started", platform="all",
                        details="Summer Sale 2024 loop started (max 10 iterations)",
                        timestamp=_minutes_ago(10), type="create"),
            ActivityItem(id="act3", action="Campaign Created", platform="meta_ads",
                        details="Created campaign on Meta Ads with $500 daily budget",
                        timestamp=_minutes_ago(15), type="execute"),
            ActivityItem(id="act4", action="Budget Allocated", platform="oceanengine",
                        details="Allocated $1800/day based on ROAS prediction",
                        timestamp=_minutes_ago(20), type="analyze"),
            ActivityItem(id="act5", action="Loop Paused", platform="all",
                        details="Brand Awareness Q3 paused - ROAS below threshold",
                        timestamp=_minutes_ago(30), type="pause"),
        ],
    )


@router.get("/dashboard", response_model=DashboardResponse, summary="获取仪表盘汇总数据")
async def get_dashboard(agent: AgentDep) -> DashboardResponse:
    """获取仪表盘汇总数据

    从 Campaign Manager 和 Checkpoint Manager 聚合数据。
    当无法获取实际数据时返回默认 Mock 数据。
    """
    has_real_data = False
    kpi = KPIData()
    loops: List[LoopResponse] = []
    activities: List[ActivityItem] = []
    budget_items: List[BudgetItem] = []
    total_spend = 0.0
    roas_values: List[float] = []

    if agent is not None:
        # 从 campaign_manager 获取 campaigns
        try:
            cm = getattr(agent, "campaign_manager", None)
            if cm is not None:
                plan_names = cm.list_plans()
                kpi.totalCampaigns = len(plan_names)
                has_real_data = True

                for pname in plan_names:
                    plan = cm.get_plan(pname)
                    if plan:
                        pscores = getattr(plan, "platform_scores", [])
                        for ps in pscores:
                            score = getattr(ps, "score", 0)
                            if score:
                                roas_values.append(score)
                        req = getattr(plan, "request", None)
                        if req:
                            total_spend += getattr(req, "budget_total", 0.0) * 0.3
        except Exception:
            pass

        # 从 checkpoint 获取 loops
        try:
            cp = getattr(agent, "checkpoint_manager", None)
            if cp is not None:
                threads = cp.list_threads(limit=50)
                if threads:
                    has_real_data = True

                for tid in threads:
                    if not tid.startswith("campaign_"):
                        continue
                    state = cp.get(tid)
                    if not state:
                        continue

                    loop = _parse_state_to_loop(tid, state)
                    if loop:
                        loops.append(loop)
                        if loop.status in ("running", "paused"):
                            total_spend += loop.spend
                            if loop.roas > 0:
                                roas_values.append(loop.roas)

                    acts = _extract_activities(tid, state)
                    activities.extend(acts)

                    # 取最新 running loop 的预算分配
                    if loop.status == "running" and not budget_items:
                        budget_alloc = state.get("budget_allocation", {})
                        for idx, (platform, amount) in enumerate(budget_alloc.items()):
                            color = _BUDGET_COLORS[idx % len(_BUDGET_COLORS)]
                            budget_items.append(BudgetItem(
                                name=platform, value=round(float(amount), 2), fill=color,
                            ))
        except Exception:
            pass

    if has_real_data:
        kpi.activeLoops = len([l for l in loops if l.status in ("running", "paused")])
        kpi.totalSpend = round(total_spend, 2)
        if roas_values:
            kpi.avgRoas = round(sum(roas_values) / len(roas_values), 2)

        final_loops = loops if loops else _generate_default_dashboard().activeLoops
        final_budget = budget_items if budget_items else _generate_default_dashboard().budgetAllocation

        if activities:
            activities.sort(key=lambda a: a.timestamp, reverse=True)
            activities = activities[:20]
        else:
            activities = _generate_default_dashboard().recentActivity

        return DashboardResponse(
            kpi=kpi, budgetAllocation=final_budget,
            activeLoops=final_loops, recentActivity=activities,
        )

    return _generate_default_dashboard()
