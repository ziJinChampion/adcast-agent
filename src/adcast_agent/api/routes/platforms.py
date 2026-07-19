"""
平台管理路由模块

提供广告平台的列表查询、详情查看和健康检查功能。
"""

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, status

from adcast_agent.api.deps import AgentDep
from adcast_agent.api.schemas import PlatformResponse, PlatformListResponse

router = APIRouter()

# MCP 平台列表：海外4个 + 巨量引擎
_MCP_PLATFORMS = {"google_ads", "meta_ads", "oceanengine", "amazon_dsp", "adform"}

# 默认平台静态数据
DEFAULT_PLATFORMS: List[Dict[str, Any]] = [
    {"name": "google_ads", "display_name": "Google Ads", "strengths": ["Search", "Shopping", "YouTube"], "avg_cpm": 8.5, "avg_cpc": 2.5, "best_for": ["conversions", "sales", "traffic", "leads"], "min_budget": 1},
    {"name": "meta_ads", "display_name": "Meta Ads", "strengths": ["Social", "Visual", "Ecommerce"], "avg_cpm": 12.0, "avg_cpc": 1.5, "best_for": ["awareness", "sales", "conversions", "engagement"], "min_budget": 1},
    {"name": "oceanengine", "display_name": "巨量引擎", "strengths": ["短视频", "直播", "电商"], "avg_cpm": 15.0, "avg_cpc": 3.0, "best_for": ["awareness", "sales", "app_installs", "livestream"], "min_budget": 300},
    {"name": "tencent_ads", "display_name": "腾讯广告", "strengths": ["社交", "小程序", "游戏"], "avg_cpm": 18.0, "avg_cpc": 2.8, "best_for": ["conversions", "app_installs", "gaming"], "min_budget": 50},
    {"name": "kuaishou", "display_name": "快手磁力引擎", "strengths": ["短视频", "下沉市场", "直播"], "avg_cpm": 10.0, "avg_cpc": 2.0, "best_for": ["awareness", "sales", "app_installs"], "min_budget": 100},
    {"name": "baidu_ads", "display_name": "百度营销", "strengths": ["搜索", "B2B"], "avg_cpm": 5.0, "avg_cpc": 4.0, "best_for": ["leads", "traffic", "B2B"], "min_budget": 50},
    {"name": "amazon_dsp", "display_name": "Amazon DSP", "strengths": ["电商", "零售", "购买意向"], "avg_cpm": 6.0, "avg_cpc": 1.2, "best_for": ["sales", "conversions", "retargeting"], "min_budget": 50000},
    {"name": "adform", "display_name": "Adform FLOW", "strengths": ["Display", "Programmatic"], "avg_cpm": 7.5, "avg_cpc": 1.8, "best_for": ["awareness", "conversions", "traffic"], "min_budget": 1000},
]


def _build_platform_response(name: str, display_name: str, platform_type: str,
                             is_connected: bool, capabilities: List[str],
                             objectives: List[str], avg_cpm: float,
                             avg_cpc: float, min_budget: float) -> PlatformResponse:
    """构建 PlatformResponse。"""
    return PlatformResponse(
        id=name, name=name, displayName=display_name, type=platform_type,
        status="connected" if is_connected else "disconnected",
        objectives=objectives, capabilities=capabilities,
        avgCpm=avg_cpm, avgCpc=avg_cpc, minBudget=min_budget,
    )


def _get_platform_type(name: str) -> str:
    return "mcp" if name in _MCP_PLATFORMS else "api"


@router.get("/platforms", response_model=PlatformListResponse, summary="获取所有广告平台列表")
async def list_platforms(agent: AgentDep) -> PlatformListResponse:
    """获取所有广告平台列表

    如果 Agent 已初始化且包含已连接的平台，返回实际平台数据；
    否则返回默认静态数据。
    """
    platforms_data: List[PlatformResponse] = []
    connected_names: set = set()

    # 尝试从 Agent 获取实际平台数据
    if agent is not None:
        try:
            pm = getattr(agent, "platform_manager", None)
            if pm is not None:
                connected_platforms = pm.get_platforms()
                connected_names = set(pm.list_platforms())

                for name, platform in connected_platforms.items():
                    try:
                        cap = platform.get_capability()
                        cap_name = getattr(cap, "display_name", name)
                        cap_strengths = getattr(cap, "strengths", cap.supported_objectives)
                        cap_best_for = getattr(cap, "best_for", cap.supported_objectives)
                        cap_cpm = getattr(cap, "avg_cpm", 0.0)
                        cap_cpc = getattr(cap, "avg_cpc", 0.0)
                        cap_min = getattr(cap, "min_budget", 0.0)
                        ptype = "mcp" if cap.supports_mcp else "api"

                        platforms_data.append(_build_platform_response(
                            name, cap_name, ptype, True,
                            cap_strengths if cap_strengths else cap.supported_objectives,
                            cap_best_for if cap_best_for else cap.supported_objectives,
                            cap_cpm, cap_cpc, cap_min,
                        ))
                    except Exception:
                        pass
        except Exception:
            pass

    # 补充未连接的默认平台
    existing_names = {p.name for p in platforms_data}
    for data in DEFAULT_PLATFORMS:
        name = data["name"]
        if name not in existing_names:
            ptype = _get_platform_type(name)
            platforms_data.append(_build_platform_response(
                name, data["display_name"], ptype,
                name in connected_names,
                data.get("strengths", []), data.get("best_for", []),
                data.get("avg_cpm", 0.0), data.get("avg_cpc", 0.0),
                data.get("min_budget", 0.0),
            ))

    return PlatformListResponse(platforms=platforms_data)


@router.get("/platforms/{name}", response_model=PlatformResponse, summary="获取单个平台详情")
async def get_platform(name: str) -> PlatformResponse:
    """获取单个广告平台详情。"""
    for data in DEFAULT_PLATFORMS:
        if data["name"] == name:
            ptype = _get_platform_type(name)
            return _build_platform_response(
                name, data["display_name"], ptype, False,
                data.get("strengths", []), data.get("best_for", []),
                data.get("avg_cpm", 0.0), data.get("avg_cpc", 0.0),
                data.get("min_budget", 0.0),
            )
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"平台 '{name}' 不存在")


@router.post("/platforms/{name}/health", summary="平台健康检查")
async def check_platform_health(name: str, agent: AgentDep) -> dict:
    """对指定平台执行健康检查。"""
    if agent is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Agent 未初始化")

    pm = getattr(agent, "platform_manager", None)
    if pm is None:
        return {"name": name, "healthy": False, "error": "平台管理器未初始化"}

    platform = pm.get_platform(name)
    if platform is None:
        return {"name": name, "healthy": False, "error": "平台未连接"}

    try:
        healthy = await platform.health_check()
        return {"name": name, "healthy": healthy}
    except Exception as e:
        return {"name": name, "healthy": False, "error": str(e)}
