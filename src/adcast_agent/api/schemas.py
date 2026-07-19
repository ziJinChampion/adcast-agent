"""
AdCast Agent API Pydantic 模型定义

定义所有请求和响应的数据模型。
"""

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


# =============================================================================
# 认证相关模型
# =============================================================================


class Token(BaseModel):
    """JWT Token 响应模型"""

    access_token: str = Field(..., description="JWT 访问令牌")
    token_type: str = Field(default="bearer", description="令牌类型")

    model_config = {"from_attributes": True}


class LoginRequest(BaseModel):
    """用户登录请求模型"""

    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")

    model_config = {"from_attributes": True}


class UserInfo(BaseModel):
    """用户信息模型"""

    id: str = Field(..., description="用户ID")
    username: str = Field(..., description="用户名")
    role: str = Field(default="admin", description="用户角色")

    model_config = {"from_attributes": True}


# =============================================================================
# 平台相关模型
# =============================================================================


class PlatformResponse(BaseModel):
    """广告投放平台响应模型"""

    id: str = Field(..., description="平台唯一标识")
    name: str = Field(..., description="平台名称（英文标识）")
    displayName: str = Field(..., description="平台显示名称")
    type: str = Field(..., description="平台类型：mcp 或 api")
    status: str = Field(default="disconnected", description="连接状态：connected / disconnected")
    objectives: List[str] = Field(default_factory=list, description="支持的广告目标列表")
    capabilities: List[str] = Field(default_factory=list, description="平台能力列表")
    avgCpm: float = Field(default=0.0, description="平均千次展示成本（元）")
    avgCpc: float = Field(default=0.0, description="平均点击成本（元）")
    minBudget: float = Field(default=0.0, description="最低预算要求（元）")

    model_config = {"from_attributes": True}


class PlatformListResponse(BaseModel):
    """平台列表响应模型"""

    platforms: List[PlatformResponse] = Field(default_factory=list, description="平台列表")

    model_config = {"from_attributes": True}


# =============================================================================
# Loop 相关模型
# =============================================================================


class LoopResponse(BaseModel):
    """AI 投放循环响应模型"""

    id: str = Field(..., description="循环唯一标识")
    name: str = Field(..., description="循环名称（对应 Campaign 名称）")
    status: str = Field(default="paused", description="循环状态：running / paused / completed")
    iteration: int = Field(default=0, description="当前迭代次数")
    maxIterations: int = Field(default=10, description="最大迭代次数")
    platforms: List[str] = Field(default_factory=list, description="参与投放的平台列表")
    budget: float = Field(default=0.0, description="总预算（元）")
    spend: float = Field(default=0.0, description="已花费金额（元）")
    roas: float = Field(default=0.0, description="广告支出回报率")
    threadId: Optional[str] = Field(default=None, description="LangGraph 线程ID")
    nextAction: Optional[str] = Field(default=None, description="下一次计划执行的动作")

    model_config = {"from_attributes": True}


class LoopCreateRequest(BaseModel):
    """创建 AI 投放循环请求模型"""

    name: str = Field(..., description="循环名称")
    objective: str = Field(..., description="广告目标")
    budget: float = Field(..., gt=0, description="总预算（元）")
    dailyBudget: float = Field(default=0, gt=0, description="每日预算（元）")
    targetMarket: str = Field(default="global", description="目标市场")
    industry: str = Field(default="", description="行业类型")
    creativeType: str = Field(default="video", description="创意类型")
    intervalMinutes: int = Field(default=60, ge=1, description="循环间隔分钟数")
    maxIterations: int = Field(default=10, ge=1, description="最大迭代次数")

    model_config = {"from_attributes": True}


class LoopControlRequest(BaseModel):
    """控制 AI 投放循环请求模型"""

    action: str = Field(
        ...,
        description="控制动作：pause / resume / stop",
        pattern="^(pause|resume|stop)$",
    )

    model_config = {"from_attributes": True}


class LoopListResponse(BaseModel):
    """Loop 列表响应模型"""

    loops: List[LoopResponse] = Field(default_factory=list, description="循环列表")

    model_config = {"from_attributes": True}


# =============================================================================
# Campaign 相关模型
# =============================================================================


class CampaignResponse(BaseModel):
    """广告活动响应模型"""

    id: str = Field(..., description="活动唯一标识")
    name: str = Field(..., description="活动名称")
    objective: str = Field(..., description="广告目标")
    budget: float = Field(default=0.0, description="总预算（元）")
    dailyBudget: float = Field(default=0.0, description="每日预算（元）")
    platforms: List[str] = Field(default_factory=list, description="投放平台列表")
    status: str = Field(default="planned", description="活动状态：active / paused / completed / planned")
    startDate: Optional[str] = Field(default=None, description="开始日期（ISO 格式）")
    spend: float = Field(default=0.0, description="已花费金额（元）")
    conversions: int = Field(default=0, description="转化次数")
    roas: float = Field(default=0.0, description="广告支出回报率")

    model_config = {"from_attributes": True}


class CampaignCreateRequest(BaseModel):
    """创建广告活动请求模型"""

    name: str = Field(..., description="活动名称")
    objective: str = Field(..., description="广告目标")
    budget: float = Field(..., gt=0, description="总预算（元）")
    dailyBudget: float = Field(default=0, gt=0, description="每日预算（元）")
    targetMarket: str = Field(default="global", description="目标市场")
    platforms: List[str] = Field(default_factory=list, description="投放平台列表")
    startDate: Optional[str] = Field(default=None, description="开始日期（ISO 格式）")
    industry: str = Field(default="", description="行业类型")
    creativeType: str = Field(default="video", description="创意类型")

    model_config = {"from_attributes": True}


class CampaignListResponse(BaseModel):
    """Campaign 列表响应模型"""

    campaigns: List[CampaignResponse] = Field(default_factory=list, description="活动列表")

    model_config = {"from_attributes": True}


# =============================================================================
# AI 思考过程相关模型
# =============================================================================


class ThinkNodeResponse(BaseModel):
    """AI 思考节点响应模型"""

    id: str = Field(..., description="节点唯一标识")
    name: str = Field(..., description="节点名称（如：analyze / decide / execute）")
    status: str = Field(default="pending", description="节点状态：completed / active / pending")
    reasoning: Optional[str] = Field(default=None, description="节点推理过程描述")
    timestamp: Optional[str] = Field(default=None, description="节点执行时间戳（ISO 格式）")
    icon: Optional[str] = Field(default=None, description="节点对应的图标标识")

    model_config = {"from_attributes": True}


class LLMPlatformScore(BaseModel):
    """LLM 平台评分模型"""

    name: str = Field(..., description="平台英文标识名")
    displayName: str = Field(..., description="平台显示名称")
    score: int = Field(default=0, ge=0, le=100, description="平台评分（0-100）")
    confidence: str = Field(default="medium", description="置信度：high / medium / low")

    model_config = {"from_attributes": True}


class LLMDecisionResponse(BaseModel):
    """LLM 决策结果响应模型"""

    reasoning: str = Field(default="", description="决策推理过程")
    selectedPlatforms: List[LLMPlatformScore] = Field(
        default_factory=list, description="选中的平台及评分列表"
    )
    budgetAllocation: Dict[str, float] = Field(
        default_factory=dict, description="平台预算分配（平台名 -> 金额）"
    )
    riskFactors: List[str] = Field(default_factory=list, description="风险因素列表")
    overallStrategy: str = Field(default="", description="整体投放策略描述")

    model_config = {"from_attributes": True}


class ThinkProcessResponse(BaseModel):
    """AI 完整思考过程响应模型"""

    threadId: str = Field(..., description="LangGraph 线程ID")
    campaignName: str = Field(..., description="关联的活动名称")
    iteration: int = Field(default=0, description="当前迭代次数")
    nodes: List[ThinkNodeResponse] = Field(default_factory=list, description="思考节点列表")
    decision: Optional[LLMDecisionResponse] = Field(default=None, description="LLM 决策结果")
    status: str = Field(default="pending", description="思考过程状态")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat(), description="时间戳（ISO 格式）")

    model_config = {"from_attributes": True}


# =============================================================================
# 仪表盘相关模型
# =============================================================================


class KPIData(BaseModel):
    """仪表盘 KPI 数据模型"""

    totalCampaigns: int = Field(default=0, description="活动总数")
    activeLoops: int = Field(default=0, description="活跃 Loop 数量")
    totalSpend: float = Field(default=0.0, description="总花费金额（元）")
    avgRoas: float = Field(default=0.0, description="平均广告支出回报率")

    model_config = {"from_attributes": True}


class BudgetItem(BaseModel):
    """预算分配饼图数据项"""

    name: str = Field(..., description="平台或预算项名称")
    value: float = Field(default=0.0, description="预算金额（元）")
    fill: Optional[str] = Field(default=None, description="图表填充颜色（CSS 颜色值）")

    model_config = {"from_attributes": True}


class ActivityItem(BaseModel):
    """最近活动记录模型"""

    id: str = Field(..., description="活动记录唯一标识")
    action: str = Field(..., description="动作描述")
    platform: str = Field(default="", description="关联平台名称")
    details: Optional[str] = Field(default=None, description="详细信息")
    timestamp: str = Field(..., description="时间戳（ISO 格式）")
    type: str = Field(
        default="info",
        description="活动类型：create / update / pause / analyze / decide / execute / info / success / warning",
    )

    model_config = {"from_attributes": True}


class DashboardResponse(BaseModel):
    """仪表盘综合数据响应模型"""

    kpi: KPIData = Field(default_factory=KPIData, description="KPI 核心指标")
    budgetAllocation: List[BudgetItem] = Field(
        default_factory=list, description="预算分配饼图数据"
    )
    activeLoops: List[LoopResponse] = Field(
        default_factory=list, description="活跃 Loop 列表"
    )
    recentActivity: List[ActivityItem] = Field(
        default_factory=list, description="最近活动记录列表"
    )

    model_config = {"from_attributes": True}


# =============================================================================
# SSE 事件模型
# =============================================================================


class SSEEvent(BaseModel):
    """Server-Sent Events (SSE) 事件模型

    用于向前端实时推送 AI 思考过程、执行日志等事件。
    """

    event: str = Field(
        default="message",
        description="事件类型：node_start / node_end / llm_decision / execution_log / error / complete / heartbeat",
    )
    data: Dict = Field(default_factory=dict, description="事件数据负载")
    timestamp: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat(),
        description="事件时间戳（ISO 格式）",
    )

    model_config = {"from_attributes": True}
