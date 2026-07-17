"""
Campaign 管理路由模块

提供 Campaign 的列表查询、创建、暂停/激活等操作。
"""

import uuid
from typing import Any, Dict, List, Optional, Set

from fastapi import APIRouter, HTTPException, status

from adcast_agent.api.deps import AgentDep
from adcast_agent.api.schemas import (
    CampaignResponse, CampaignCreateRequest, CampaignListResponse,
)

router = APIRouter()


def _safe_get(d: Dict, key: str, default=None):
    """安全获取字典字段。"""
    if not isinstance(d, dict):
        return default
    return d.get(key, default)


def _state_to_campaign_response(thread_id: str, state: Dict) -> Optional[CampaignResponse]:
    """将 AgentState 转换为 CampaignResponse。"""
    if not state:
        return None

    campaign_name = _safe_get(state, "campaign_name", "未命名")
    objective = _safe_get(state, "campaign_objective", "conversions")
    budget = _safe_get(state, "campaign_budget", 0.0)
    daily_budget = _safe_get(state, "campaign_daily_budget", 0.0)
    selected_platforms = _safe_get(state, "selected_platforms", [])
    should_continue = _safe_get(state, "should_continue", False)
    pause_reason = _safe_get(state, "pause_reason")
    iteration = _safe_get(state, "iteration", 0)

    if pause_reason:
        camp_status = "paused"
    elif not should_continue and iteration > 1:
        camp_status = "completed"
    elif iteration > 0:
        camp_status = "active"
    else:
        camp_status = "planned"

    budget_alloc = _safe_get(state, "budget_allocation", {})
    spend = sum(budget_alloc.values()) * 0.3 if budget_alloc else 0.0

    return CampaignResponse(
        id=thread_id, name=campaign_name, objective=objective,
        budget=budget, dailyBudget=daily_budget,
        platforms=selected_platforms, status=camp_status,
        startDate=_safe_get(state, "created_at", ""),
        spend=round(spend, 2), conversions=0, roas=0.0,
    )


def _plan_to_campaign_response(plan_name: str, plan: Any) -> Optional[CampaignResponse]:
    """将 CampaignExecutionPlan 转换为 CampaignResponse。"""
    if plan is None:
        return None

    try:
        request = getattr(plan, "request", None)
        if request is None:
            return None

        name = getattr(request, "name", plan_name)
        objective = getattr(request, "objective", "conversions")
        budget_total = getattr(request, "budget_total", 0.0)
        daily_budget = getattr(request, "daily_budget", 0.0)
        start_date = getattr(request, "start_date", None)

        platform_scores = getattr(plan, "platform_scores", [])
        platforms_list = []
        if platform_scores:
            for ps in platform_scores:
                if hasattr(ps, "platform"):
                    platforms_list.append(ps.platform)
                elif isinstance(ps, dict):
                    platforms_list.append(ps.get("platform", ""))

        plan_status = getattr(plan, "status", "planned")
        status_map = {
            "planned": "planned", "executing": "active", "running": "active",
            "active": "active", "paused": "paused", "completed": "completed",
            "failed": "paused",
        }

        start_date_str = ""
        if start_date:
            from datetime import datetime
            if isinstance(start_date, datetime):
                start_date_str = start_date.isoformat()

        return CampaignResponse(
            id=f"plan_{plan_name}", name=name, objective=objective,
            budget=budget_total, dailyBudget=daily_budget,
            platforms=platforms_list,
            status=status_map.get(plan_status, "planned"),
            startDate=start_date_str,
            spend=0.0, conversions=0, roas=0.0,
        )
    except Exception:
        return None


@router.get("/campaigns", response_model=CampaignListResponse, summary="获取所有 Campaign")
async def list_campaigns(agent: AgentDep) -> CampaignListResponse:
    """获取所有 Campaign 列表（合并 Plan 和 Checkpoint 数据源）。"""
    campaigns: List[CampaignResponse] = []
    seen_names: Set[str] = set()

    # 从 campaign_manager 获取 plans
    if agent is not None:
        try:
            cm = getattr(agent, "campaign_manager", None)
            if cm is not None:
                plan_names = cm.list_plans()
                for pname in plan_names:
                    plan = cm.get_plan(pname)
                    camp = _plan_to_campaign_response(pname, plan)
                    if camp and camp.name not in seen_names:
                        campaigns.append(camp)
                        seen_names.add(camp.name)
        except Exception:
            pass

        # 从 checkpoint 获取 campaigns
        try:
            cp = getattr(agent, "checkpoint_manager", None)
            if cp is not None:
                threads = cp.list_threads(limit=100)
                for tid in threads:
                    if tid.startswith("campaign_"):
                        state = cp.get(tid)
                        if state:
                            camp = _state_to_campaign_response(tid, state)
                            if camp and camp.name not in seen_names:
                                campaigns.append(camp)
                                seen_names.add(camp.name)
        except Exception:
            pass

    return CampaignListResponse(campaigns=campaigns)


@router.post("/campaigns", response_model=CampaignResponse, summary="创建 Campaign")
async def create_campaign(request: CampaignCreateRequest, agent: AgentDep) -> CampaignResponse:
    """创建新的 Campaign（One-shot 模式）。"""
    if agent is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Agent 未初始化")

    try:
        result = await agent.run_campaign(
            name=request.name,
            objective=request.objective,
            budget=request.budget,
            daily_budget=request.dailyBudget,
            target_market=request.targetMarket,
            industry=request.industry,
            creative_type=request.creativeType,
            auto_activate=False,
        )

        return CampaignResponse(
            id=f"campaign_{request.name}_{uuid.uuid4().hex[:8]}",
            name=request.name, objective=request.objective,
            budget=request.budget, dailyBudget=request.dailyBudget,
            platforms=request.platforms if request.platforms else result.get("platforms", []),
            status="planned", startDate=request.startDate or "",
            spend=0.0, conversions=0, roas=0.0,
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/campaigns/{name}", response_model=CampaignResponse, summary="获取 Campaign 详情")
async def get_campaign(name: str, agent: AgentDep) -> CampaignResponse:
    """获取指定 Campaign 详情。"""
    if agent is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Agent 未初始化")

    # 先从 plans 查找
    try:
        cm = getattr(agent, "campaign_manager", None)
        if cm is not None:
            plan = cm.get_plan(name)
            if plan:
                camp = _plan_to_campaign_response(name, plan)
                if camp:
                    return camp
    except Exception:
        pass

    # 再从 checkpoint 查找
    try:
        cp = getattr(agent, "checkpoint_manager", None)
        if cp is not None:
            threads = cp.list_threads(limit=100)
            for tid in threads:
                if tid.startswith(f"campaign_{name}_"):
                    state = cp.get(tid)
                    if state:
                        camp = _state_to_campaign_response(tid, state)
                        if camp:
                            return camp
    except Exception:
        pass

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Campaign '{name}' 不存在")


@router.post("/campaigns/{name}/pause", summary="暂停 Campaign")
async def pause_campaign(name: str, agent: AgentDep) -> dict:
    """暂停指定 Campaign。"""
    if agent is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Agent 未初始化")

    try:
        await agent.pause_campaigns(name)
        return {"success": True, "action": "pause", "campaign": name}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/campaigns/{name}/activate", summary="激活 Campaign")
async def activate_campaign(name: str, agent: AgentDep) -> dict:
    """激活指定 Campaign。"""
    if agent is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Agent 未初始化")

    try:
        await agent.activate_campaigns(name)
        return {"success": True, "action": "activate", "campaign": name}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
