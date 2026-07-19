"""
Loop 管理路由模块

提供 Campaign Loop 的列表查询、创建、状态控制和详情查看。
"""

import asyncio
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, status

from adcast_agent.api.deps import AgentDep
from adcast_agent.api.schemas import (
    LoopResponse, LoopCreateRequest, LoopControlRequest, LoopListResponse,
)

router = APIRouter()


def _safe_get(d: Dict, key: str, default=None):
    """安全获取字典嵌套字段。"""
    if not isinstance(d, dict):
        return default
    return d.get(key, default)


def _state_to_loop_response(thread_id: str, state: Dict) -> Optional[LoopResponse]:
    """将 AgentState 字典转换为 LoopResponse。"""
    if not state:
        return None

    campaign_name = _safe_get(state, "campaign_name", "未命名")
    iteration = _safe_get(state, "iteration", 0)
    max_iter = _safe_get(state, "max_iterations", 10)
    should_continue = _safe_get(state, "should_continue", False)
    pause_reason = _safe_get(state, "pause_reason")

    if pause_reason:
        loop_status = "paused"
    elif not should_continue:
        loop_status = "completed"
    else:
        loop_status = "running"

    budget_alloc = _safe_get(state, "budget_allocation", {})
    total_budget = sum(budget_alloc.values()) if budget_alloc else 0.0

    # 估算 spend
    execution = _safe_get(state, "execution_results", {})
    spend = 0.0
    if isinstance(execution, dict):
        for _, result in execution.items():
            if isinstance(result, dict):
                spend += result.get("budget", 0.0) * 0.3  # 估算

    # 估算 ROAS
    platform_scores = _safe_get(state, "platform_scores", [])
    roas = 0.0
    if platform_scores and isinstance(platform_scores, list):
        scores = [ps.get("score", 0) for ps in platform_scores if isinstance(ps, dict)]
        if scores:
            roas = round(sum(scores) / len(scores) / 25, 2)  # 归一化

    next_action = _safe_get(state, "next_action", "observe")
    selected_platforms = _safe_get(state, "selected_platforms", [])

    return LoopResponse(
        id=thread_id, name=campaign_name, status=loop_status,
        iteration=iteration, maxIterations=max_iter,
        platforms=selected_platforms, budget=round(total_budget, 2),
        spend=round(spend, 2), roas=roas,
        threadId=thread_id, nextAction=next_action,
    )


@router.get("/loops", response_model=LoopListResponse, summary="获取所有 Loop 列表")
async def list_loops(agent: AgentDep) -> LoopListResponse:
    """获取所有 Campaign Loop 列表。"""
    loops: List[LoopResponse] = []

    if agent is not None:
        try:
            cp = getattr(agent, "checkpoint_manager", None)
            if cp is not None:
                threads = cp.list_threads(limit=100)
                for tid in threads:
                    if tid.startswith("campaign_"):
                        state = cp.get(tid)
                        if state:
                            loop = _state_to_loop_response(tid, state)
                            if loop:
                                loops.append(loop)
        except Exception:
            pass

    return LoopListResponse(loops=loops)


@router.post("/loops", response_model=LoopResponse, summary="创建并启动新 Loop")
async def create_loop(request: LoopCreateRequest, agent: AgentDep) -> LoopResponse:
    """创建并启动新的 AI Loop。"""
    if agent is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Agent 未初始化")

    try:
        result = await agent.run_ai_loop(
            name=request.name,
            objective=request.objective,
            budget=request.budget,
            daily_budget=request.dailyBudget,
            target_market=request.targetMarket,
            industry=request.industry,
            creative_type=request.creativeType,
            interval_minutes=request.intervalMinutes,
            max_iterations=request.maxIterations,
        )

        thread_id = result.get("thread_id", "")
        return LoopResponse(
            id=thread_id, name=request.name,
            status=result.get("status", "running"),
            iteration=result.get("iteration", 1),
            maxIterations=request.maxIterations,
            platforms=result.get("selected_platforms", []),
            budget=request.budget, spend=0.0, roas=0.0,
            threadId=thread_id,
            nextAction=result.get("next_action", "observe"),
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/loops/{name}", response_model=LoopResponse, summary="获取 Loop 状态")
async def get_loop(name: str, agent: AgentDep) -> LoopResponse:
    """获取指定 Campaign Loop 的状态。"""
    if agent is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Agent 未初始化")

    try:
        status_result = await agent.get_loop_status(name)
        if "error" in status_result:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=status_result["error"])

        thread_id = status_result.get("thread_id", f"campaign_{name}")
        return LoopResponse(
            id=thread_id, name=name,
            status=status_result.get("status", "paused"),
            iteration=status_result.get("iteration", 0),
            maxIterations=10,
            platforms=status_result.get("selected_platforms", []),
            budget=sum(status_result.get("budget_allocation", {}).values()),
            spend=0.0, roas=0.0,
            threadId=thread_id,
            nextAction=status_result.get("status", "observe"),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/loops/{name}/control", summary="控制 Loop")
async def control_loop(name: str, request: LoopControlRequest, agent: AgentDep) -> dict:
    """控制指定 Loop（暂停/恢复/停止）。"""
    if agent is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Agent 未初始化")

    try:
        if request.action == "pause":
            await agent.pause_loop(name)
            return {"success": True, "action": "pause", "campaign": name}
        elif request.action == "resume":
            result = await agent.resume_loop(name)
            return {"success": True, "action": "resume", "campaign": name, "result": result}
        elif request.action == "stop":
            await agent.pause_loop(name)
            return {"success": True, "action": "stop", "campaign": name}
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"无效操作: {request.action}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
