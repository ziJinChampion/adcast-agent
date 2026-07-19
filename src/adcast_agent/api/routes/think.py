"""
AI 思考过程路由模块

提供 AI 思考过程的查询和 SSE 实时流式推送。
"""

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

from adcast_agent.api.deps import AgentDep
from adcast_agent.api.schemas import (
    ThinkProcessResponse, ThinkNodeResponse,
    LLMDecisionResponse, LLMPlatformScore, SSEEvent,
)
from adcast_agent.api.sse_manager import sse_manager

router = APIRouter()

# 节点图标映射
_NODE_ICONS = {
    "observe": "Eye", "analyze": "Brain", "decide": "Lightbulb",
    "execute": "Play", "reflect": "RotateCcw",
}

# 节点顺序
_NODE_ORDER = ["observe", "analyze", "decide", "execute", "reflect"]


def _safe_get(d: Dict, key: str, default=None):
    """安全获取字典字段。"""
    if not isinstance(d, dict):
        return default
    return d.get(key, default)


def _parse_decision(state: Dict) -> Optional[LLMDecisionResponse]:
    """从 AgentState 解析 LLM 决策结果。"""
    decision = _safe_get(state, "decision")
    if not decision:
        return None

    reasoning = _safe_get(decision, "reasoning", "")
    overall_strategy = _safe_get(decision, "strategy", "")
    risk_factors = _safe_get(decision, "risk_factors", [])
    budget_allocation = _safe_get(decision, "budget_allocation", {})

    # 解析平台评分
    platform_scores_data = _safe_get(state, "platform_scores", [])
    llm_analysis = _safe_get(state, "llm_analysis", {})
    platforms_from_llm = _safe_get(llm_analysis, "platforms", [])

    selected_platforms: List[LLMPlatformScore] = []

    # 优先使用 llm_analysis.platforms
    if platforms_from_llm and isinstance(platforms_from_llm, list):
        for p in platforms_from_llm:
            if isinstance(p, dict):
                selected_platforms.append(LLMPlatformScore(
                    name=p.get("name", ""),
                    displayName=p.get("display_name", p.get("name", "")),
                    score=int(p.get("score", 0)),
                    confidence=p.get("confidence", "medium"),
                ))
    # 其次使用 platform_scores
    elif platform_scores_data and isinstance(platform_scores_data, list):
        for p in platform_scores_data:
            if isinstance(p, dict):
                selected_platforms.append(LLMPlatformScore(
                    name=p.get("name", ""),
                    displayName=p.get("display_name", p.get("name", "")),
                    score=int(p.get("score", 0)),
                    confidence=p.get("confidence", "medium"),
                ))

    return LLMDecisionResponse(
        reasoning=reasoning,
        selectedPlatforms=selected_platforms,
        budgetAllocation=budget_allocation,
        riskFactors=risk_factors if isinstance(risk_factors, list) else [],
        overallStrategy=overall_strategy,
    )


def _build_nodes(state: Dict) -> List[ThinkNodeResponse]:
    """从 AgentState 构建 5 个思考节点。"""
    nodes: List[ThinkNodeResponse] = []
    iteration = _safe_get(state, "iteration", 0)
    platform_data = _safe_get(state, "platform_data", [])
    llm_analysis = _safe_get(state, "llm_analysis", {})
    decision = _safe_get(state, "decision")
    execution_results = _safe_get(state, "execution_results", {})
    reflection = _safe_get(state, "reflection")
    learning_notes = _safe_get(state, "learning_notes", [])
    next_action = _safe_get(state, "next_action", "observe")
    pause_reason = _safe_get(state, "pause_reason")

    # 判断每个节点的状态
    has_platform_data = bool(platform_data) and isinstance(platform_data, list)
    has_llm_analysis = bool(llm_analysis) and isinstance(llm_analysis, dict) and llm_analysis.get("reasoning")
    has_decision = bool(decision) and isinstance(decision, dict)
    has_execution = bool(execution_results) and isinstance(execution_results, dict)
    has_reflection = bool(reflection) and isinstance(reflection, dict)

    # Observe 节点
    observe_reasoning = f"Iteration {iteration}: 收集了 {len(platform_data) if isinstance(platform_data, list) else 0} 个平台数据"
    if iteration <= 1 and not has_platform_data:
        observe_status = "active" if next_action == "observe" else "pending"
    else:
        observe_status = "completed"
    nodes.append(ThinkNodeResponse(
        id="observe", name="OBSERVE", status=observe_status,
        reasoning=observe_reasoning,
        timestamp=datetime.utcnow().isoformat(), icon=_NODE_ICONS["observe"],
    ))

    # Analyze 节点
    if has_llm_analysis:
        analyze_reasoning = llm_analysis.get("reasoning", "AI 分析完成")[:300]
        analyze_status = "completed"
    elif observe_status == "completed":
        analyze_reasoning = "正在使用 LLM 分析平台数据..."
        analyze_status = "active" if next_action == "analyze" else "pending"
    else:
        analyze_reasoning = "等待 OBSERVE 数据..."
        analyze_status = "pending"
    nodes.append(ThinkNodeResponse(
        id="analyze", name="ANALYZE", status=analyze_status,
        reasoning=analyze_reasoning,
        timestamp=datetime.utcnow().isoformat(), icon=_NODE_ICONS["analyze"],
    ))

    # Decide 节点
    if has_decision:
        selected = _safe_get(decision, "strategy", "")
        decide_reasoning = f"决策完成: {selected}"
        decide_status = "completed"
    elif analyze_status == "completed":
        decide_reasoning = "正在综合 LLM 分析和规则引擎做出决策..."
        decide_status = "active" if next_action == "decide" else "pending"
    else:
        decide_reasoning = "等待 ANALYZE 结果..."
        decide_status = "pending"
    nodes.append(ThinkNodeResponse(
        id="decide", name="DECIDE", status=decide_status,
        reasoning=decide_reasoning,
        timestamp=datetime.utcnow().isoformat(), icon=_NODE_ICONS["decide"],
    ))

    # Execute 节点
    if has_execution:
        exec_count = len(execution_results)
        execute_reasoning = f"已在 {exec_count} 个平台创建 Campaign"
        execute_status = "completed"
    elif decide_status == "completed":
        execute_reasoning = "正在各平台执行 Campaign 创建..."
        execute_status = "active" if next_action == "execute" else "pending"
    else:
        execute_reasoning = "等待 DECIDE 结果..."
        execute_status = "pending"
    nodes.append(ThinkNodeResponse(
        id="execute", name="EXECUTE", status=execute_status,
        reasoning=execute_reasoning,
        timestamp=datetime.utcnow().isoformat(), icon=_NODE_ICONS["execute"],
    ))

    # Reflect 节点
    if has_reflection or learning_notes:
        notes = learning_notes[0] if learning_notes else "反思完成"
        reflect_reasoning = f"学习笔记: {notes[:200]}"
        reflect_status = "completed"
    elif execute_status == "completed":
        reflect_reasoning = "正在评估执行效果并生成学习笔记..."
        reflect_status = "active" if next_action == "reflect" else "pending"
    else:
        reflect_reasoning = "等待 EXECUTE 完成..."
        reflect_status = "pending"
    nodes.append(ThinkNodeResponse(
        id="reflect", name="REFLECT", status=reflect_status,
        reasoning=reflect_reasoning,
        timestamp=datetime.utcnow().isoformat(), icon=_NODE_ICONS["reflect"],
    ))

    return nodes


@router.get("/think/{thread_id}", response_model=ThinkProcessResponse, summary="获取 AI 思考过程")
async def get_think_process(thread_id: str, agent: AgentDep) -> ThinkProcessResponse:
    """获取指定线程的 AI 思考过程（非流式）。"""
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent 未初始化")

    try:
        cp = getattr(agent, "checkpoint_manager", None)
        if cp is None:
            raise HTTPException(status_code=503, detail="Checkpoint 管理器未初始化")

        state = cp.get(thread_id)
        if not state:
            raise HTTPException(status_code=404, detail=f"Thread '{thread_id}' 不存在")

        nodes = _build_nodes(state)
        decision = _parse_decision(state)

        campaign_name = _safe_get(state, "campaign_name", "未命名")
        iteration = _safe_get(state, "iteration", 0)
        should_continue = _safe_get(state, "should_continue", False)
        pause_reason = _safe_get(state, "pause_reason")

        if pause_reason:
            proc_status = "paused"
        elif not should_continue:
            proc_status = "completed"
        else:
            proc_status = "running"

        return ThinkProcessResponse(
            threadId=thread_id, campaignName=campaign_name,
            iteration=iteration, nodes=nodes, decision=decision,
            status=proc_status, timestamp=datetime.utcnow().isoformat(),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/think/stream/{thread_id}", summary="SSE 实时推送 AI 思考过程")
async def stream_think_process(thread_id: str, agent: AgentDep, request: Request):
    """SSE 实时流式推送 AI 思考过程

    连接建立后，先发送当前 checkpoint 中的所有已完成节点事件，
    然后进入实时监听模式，等待新事件推送。
    """
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent 未初始化")

    cp = getattr(agent, "checkpoint_manager", None)
    if cp is None:
        raise HTTPException(status_code=503, detail="Checkpoint 管理器未初始化")

    # 获取 SSE queue
    queue = await sse_manager.connect(thread_id)

    # 启动心跳协程
    heartbeat_task = asyncio.create_task(
        sse_manager.heartbeat_loop(thread_id, interval=15.0)
    )

    async def event_generator():
        """SSE 事件生成器"""
        try:
            # 1. 发送当前 checkpoint 状态
            state = cp.get(thread_id)
            if state:
                nodes = _build_nodes(state)
                decision = _parse_decision(state)

                # 发送每个已完成节点的事件
                for node in nodes:
                    if node.status == "completed":
                        yield SSEEvent(
                            event="node_end",
                            data={
                                "node": node.id,
                                "name": node.name,
                                "reasoning": node.reasoning,
                                "timestamp": node.timestamp,
                            },
                        ).model_dump_json()

                # 发送决策事件
                if decision:
                    yield SSEEvent(
                        event="llm_decision",
                        data=decision.model_dump(),
                    ).model_dump_json()

            # 2. 进入实时监听循环
            while True:
                # 检查客户端是否断开
                if await request.is_disconnected():
                    break

                try:
                    # 等待新事件（带超时以便检查断开）
                    event = await asyncio.wait_for(queue.get(), timeout=1.0)
                    yield event.model_dump_json()

                    # 如果是 complete 事件，结束流
                    if event.event == "complete":
                        break

                except asyncio.TimeoutError:
                    continue

        except asyncio.CancelledError:
            pass
        except Exception as e:
            yield SSEEvent(
                event="error",
                data={"message": str(e)},
            ).model_dump_json()
        finally:
            # 清理
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass
            sse_manager.disconnect(thread_id, queue)

    return EventSourceResponse(event_generator())
