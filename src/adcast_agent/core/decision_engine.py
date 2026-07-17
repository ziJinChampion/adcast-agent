"""
投放决策引擎 - 智能选择最优广告平台

核心能力：
1. 多维度平台评分（受众匹配、成本效率、历史ROAS、竞争度）
2. 基于投放目标的平台推荐
3. 跨平台预算分配策略
4. 实时数据驱动的动态调整
"""

import asyncio
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging

from ..platforms.base import (
    BaseAdPlatform, PlatformCampaign, PlatformForecast,
    PlatformAudience, PlatformCapability,
)

logger = logging.getLogger("adcast.decision")


class StrategyType(Enum):
    """投放策略类型"""
    ROAS_MAXIMIZE = "roas_maximize"      # ROAS最大化
    REACH_MAXIMIZE = "reach_maximize"    # 触达最大化
    CONVERSION_MAXIMIZE = "conversion_maximize"  # 转化最大化
    BALANCED = "balanced"                # 均衡策略
    COST_MINIMIZE = "cost_minimize"      # 成本最小化


@dataclass
class PlatformScore:
    """平台评分结果"""
    platform: str
    overall_score: float = 0.0
    audience_match_score: float = 0.0
    cost_efficiency_score: float = 0.0
    roas_potential_score: float = 0.0
    competition_score: float = 0.0
    capability_score: float = 0.0
    forecast: Optional[PlatformForecast] = None
    recommendation: str = ""
    confidence: str = "medium"


@dataclass
class CampaignRequest:
    """投放需求"""
    name: str
    objective: str  # conversions, awareness, traffic, sales, etc.
    budget_total: float
    target_market: str = "global"  # global, domestic, overseas
    audience: Optional[PlatformAudience] = None
    creative_type: str = "video"
    industry: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    daily_budget: float = 0.0
    priority_platforms: List[str] = field(default_factory=list)
    exclude_platforms: List[str] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)


class DecisionEngine:
    """
    投放决策引擎
    
    根据Campaign需求，智能评估各平台的适合度，
    返回推荐的平台列表和预算分配方案。
    """

    # 平台-行业匹配度评分 (1-10)
    INDUSTRY_PLATFORM_MATCH = {
        "ecommerce": {
            "google_ads": 9, "meta_ads": 10, "amazon_dsp": 9,
            "tiktok_ads": 8, "oceanengine": 9, "tencent_ads": 7,
            "kuaishou": 8, "baidu_ads": 6,
        },
        "B2B": {
            "google_ads": 10, "meta_ads": 6, "linkedin_ads": 10,
            "baidu_ads": 8, "tencent_ads": 5, "oceanengine": 4,
        },
        "gaming": {
            "google_ads": 8, "meta_ads": 9, "tiktok_ads": 9,
            "oceanengine": 8, "tencent_ads": 9, "kuaishou": 7,
        },
        "education": {
            "google_ads": 9, "meta_ads": 7, "baidu_ads": 10,
            "oceanengine": 8, "tencent_ads": 8, "kuaishou": 5,
        },
        "finance": {
            "google_ads": 8, "meta_ads": 5, "baidu_ads": 9,
            "oceanengine": 7, "tencent_ads": 6, "kuaishou": 3,
        },
        "local_service": {
            "google_ads": 10, "baidu_ads": 8, "oceanengine": 9,
            "meta_ads": 6, "tencent_ads": 7, "kuaishou": 5,
        },
        "brand": {
            "google_ads": 8, "meta_ads": 9, "tiktok_ads": 9,
            "oceanengine": 9, "tencent_ads": 8, "adform": 8,
        },
        "app": {
            "google_ads": 9, "meta_ads": 9, "tiktok_ads": 8,
            "oceanengine": 8, "tencent_ads": 8, "kuaishou": 7,
        },
    }

    # 平台-目标匹配度评分 (1-10)
    OBJECTIVE_PLATFORM_MATCH = {
        "conversions": {
            "google_ads": 10, "meta_ads": 9, "oceanengine": 9,
            "tencent_ads": 8, "kuaishou": 8, "baidu_ads": 7,
            "amazon_dsp": 8, "adform": 8,
        },
        "awareness": {
            "google_ads": 8, "meta_ads": 10, "tiktok_ads": 10,
            "oceanengine": 9, "tencent_ads": 8, "kuaishou": 8,
            "adform": 9,
        },
        "traffic": {
            "google_ads": 10, "meta_ads": 7, "baidu_ads": 9,
            "oceanengine": 8, "tencent_ads": 7, "kuaishou": 6,
        },
        "sales": {
            "google_ads": 9, "meta_ads": 10, "amazon_dsp": 10,
            "oceanengine": 9, "tiktok_ads": 8, "kuaishou": 8,
        },
        "leads": {
            "google_ads": 9, "meta_ads": 8, "baidu_ads": 10,
            "oceanengine": 8, "tencent_ads": 7, "linkedin_ads": 10,
        },
        "app_installs": {
            "google_ads": 10, "meta_ads": 9, "tiktok_ads": 9,
            "oceanengine": 8, "tencent_ads": 8,
        },
    }

    def __init__(self, platforms: Dict[str, BaseAdPlatform]):
        self.platforms = platforms
        self._historical_roas: Dict[str, float] = {}  # 历史ROAS数据

    async def select_platforms(
        self,
        request: CampaignRequest,
        strategy: StrategyType = StrategyType.ROAS_MAXIMIZE,
        top_n: int = 3,
    ) -> List[PlatformScore]:
        """
        选择最优投放平台
        
        流程：
        1. 基于规则的初步筛选（目标匹配、市场区域）
        2. 获取各平台的投放预测
        3. 多维度评分
        4. 按策略排序
        
        Returns:
            List[PlatformScore]: 排序后的平台推荐列表
        """
        logger.info(f"Selecting platforms for campaign: {request.name} (objective={request.objective})")

        # 1. 初步筛选
        candidates = self._filter_candidates(request)
        logger.info(f"Initial candidate platforms: {list(candidates.keys())}")

        if not candidates:
            logger.warning("No candidate platforms found")
            return []

        # 2. 获取预测数据
        forecasts = await self._get_forecasts(candidates, request)

        # 3. 多维度评分
        scores = []
        for name, platform in candidates.items():
            score = self._score_platform(
                name, platform, request, forecasts.get(name), strategy
            )
            scores.append(score)

        # 4. 按策略排序
        scores.sort(key=lambda s: s.overall_score, reverse=True)

        # 5. 添加推荐说明
        for i, score in enumerate(scores):
            score.recommendation = self._generate_recommendation(score, i == 0)

        logger.info(f"Platform ranking: {[(s.platform, s.overall_score) for s in scores[:top_n]]}")
        return scores[:top_n]

    def _filter_candidates(self, request: CampaignRequest) -> Dict[str, BaseAdPlatform]:
        """初步筛选候选平台"""
        candidates = {}

        for name, platform in self.platforms.items():
            # 排除指定平台
            if name in request.exclude_platforms:
                continue

            # 检查平台是否启用
            if not hasattr(platform, 'config') or not platform.config.get("enabled", True):
                continue

            # 市场区域筛选
            if request.target_market == "domestic":
                if name in ("google_ads", "meta_ads", "amazon_dsp", "adform"):
                    continue
            elif request.target_market == "overseas":
                if name in ("oceanengine", "tencent_ads", "kuaishou", "baidu_ads"):
                    continue

            # 目标匹配检查
            if not platform.supports_objective(request.objective):
                continue

            # 预算门槛检查
            if request.daily_budget > 0:
                min_budget = platform.get_capability().min_budget
                if min_budget > 0 and request.daily_budget < min_budget:
                    logger.debug(f"{name} skipped: budget {request.daily_budget} < min {min_budget}")
                    continue

            candidates[name] = platform

        return candidates

    async def _get_forecasts(
        self,
        candidates: Dict[str, BaseAdPlatform],
        request: CampaignRequest,
    ) -> Dict[str, PlatformForecast]:
        """获取各平台的投放预测"""
        # 构建临时Campaign用于预测
        temp_campaign = PlatformCampaign(
            name=request.name,
            objective=request.objective,
            budget_amount=request.daily_budget or request.budget_total,
            audience=request.audience,
        )

        forecasts = {}
        tasks = []
        names = []

        for name, platform in candidates.items():
            if platform.get_capability().supports_forecast:
                tasks.append(platform.get_forecast(temp_campaign))
                names.append(name)

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for name, result in zip(names, results):
                if isinstance(result, PlatformForecast):
                    forecasts[name] = result
                elif isinstance(result, Exception):
                    logger.warning(f"Forecast failed for {name}: {result}")

        return forecasts

    def _score_platform(
        self,
        name: str,
        platform: BaseAdPlatform,
        request: CampaignRequest,
        forecast: Optional[PlatformForecast],
        strategy: StrategyType,
    ) -> PlatformScore:
        """对单个平台进行多维度评分"""
        score = PlatformScore(platform=name)

        # 1. 受众匹配度评分 (0-100)
        score.audience_match_score = self._score_audience_match(name, request)

        # 2. 成本效率评分 (0-100)
        score.cost_efficiency_score = self._score_cost_efficiency(name, forecast)

        # 3. ROAS潜力评分 (0-100)
        score.roas_potential_score = self._score_roas_potential(name, forecast, request)

        # 4. 竞争度评分 (0-100，越低越好的竞争环境)
        score.competition_score = self._score_competition(name, forecast)

        # 5. 平台能力评分 (0-100)
        score.capability_score = self._score_capability(platform)

        # 根据策略加权
        weights = self._get_strategy_weights(strategy)
        score.overall_score = (
            score.audience_match_score * weights["audience"] +
            score.cost_efficiency_score * weights["cost"] +
            score.roas_potential_score * weights["roas"] +
            score.competition_score * weights["competition"] +
            score.capability_score * weights["capability"]
        )

        score.forecast = forecast
        score.confidence = self._determine_confidence(forecast)

        return score

    def _score_audience_match(self, platform_name: str, request: CampaignRequest) -> float:
        """受众匹配度评分"""
        score = 50.0  # 基础分

        # 行业匹配
        if request.industry:
            industry_scores = self.INDUSTRY_PLATFORM_MATCH.get(request.industry.lower(), {})
            industry_score = industry_scores.get(platform_name, 5)
            score += industry_score * 5  # 0-50分

        # 目标匹配
        objective_scores = self.OBJECTIVE_PLATFORM_MATCH.get(request.objective, {})
        objective_score = objective_scores.get(platform_name, 5)
        score += objective_score * 3  # 0-30分

        # 创意类型匹配
        if request.creative_type == "video" and platform_name in ("tiktok_ads", "oceanengine", "kuaishou"):
            score += 10

        return min(score, 100.0)

    def _score_cost_efficiency(self, platform_name: str, forecast: Optional[PlatformForecast]) -> float:
        """成本效率评分"""
        if not forecast:
            return 50.0

        score = 50.0

        # CPM越低越好
        if forecast.estimated_cpm > 0:
            if forecast.estimated_cpm < 5:
                score += 25
            elif forecast.estimated_cpm < 15:
                score += 15
            elif forecast.estimated_cpm < 30:
                score += 5
            else:
                score -= 10

        # CPC越低越好
        if forecast.estimated_cpc > 0:
            if forecast.estimated_cpc < 0.5:
                score += 25
            elif forecast.estimated_cpc < 1.5:
                score += 15
            elif forecast.estimated_cpc < 3:
                score += 5
            else:
                score -= 10

        return min(max(score, 0), 100)

    def _score_roas_potential(
        self,
        platform_name: str,
        forecast: Optional[PlatformForecast],
        request: CampaignRequest,
    ) -> float:
        """ROAS潜力评分"""
        score = 50.0

        # 预测ROAS
        if forecast and forecast.estimated_roas > 0:
            if forecast.estimated_roas > 5:
                score += 30
            elif forecast.estimated_roas > 3:
                score += 20
            elif forecast.estimated_roas > 1:
                score += 10
            else:
                score -= 20

        # 历史ROAS
        historical = self._historical_roas.get(platform_name, 0)
        if historical > 0:
            if historical > 5:
                score += 20
            elif historical > 3:
                score += 10
            elif historical > 1:
                score += 5

        # 转化目标加分
        if request.objective in ("conversions", "sales"):
            if platform_name in ("google_ads", "meta_ads", "amazon_dsp"):
                score += 10

        return min(score, 100.0)

    def _score_competition(self, platform_name: str, forecast: Optional[PlatformForecast]) -> float:
        """竞争度评分（越低竞争越好）"""
        if not forecast:
            return 50.0

        competition = forecast.competition_level.lower()
        scores = {
            "low": 90,
            "medium": 60,
            "high": 30,
        }
        return scores.get(competition, 50)

    def _score_capability(self, platform: BaseAdPlatform) -> float:
        """平台能力评分"""
        cap = platform.get_capability()
        score = 50.0

        if cap.supports_forecast:
            score += 10
        if cap.supports_auto_bidding:
            score += 10
        if cap.supports_creative_upload:
            score += 10
        if cap.supports_audience:
            score += 10
        if len(cap.supported_objectives) > 5:
            score += 10

        return min(score, 100.0)

    def _get_strategy_weights(self, strategy: StrategyType) -> Dict[str, float]:
        """获取策略权重"""
        weights = {
            StrategyType.ROAS_MAXIMIZE: {
                "audience": 0.15, "cost": 0.15, "roas": 0.40,
                "competition": 0.10, "capability": 0.20,
            },
            StrategyType.REACH_MAXIMIZE: {
                "audience": 0.35, "cost": 0.25, "roas": 0.05,
                "competition": 0.10, "capability": 0.25,
            },
            StrategyType.CONVERSION_MAXIMIZE: {
                "audience": 0.25, "cost": 0.15, "roas": 0.35,
                "competition": 0.10, "capability": 0.15,
            },
            StrategyType.BALANCED: {
                "audience": 0.20, "cost": 0.20, "roas": 0.25,
                "competition": 0.15, "capability": 0.20,
            },
            StrategyType.COST_MINIMIZE: {
                "audience": 0.15, "cost": 0.45, "roas": 0.10,
                "competition": 0.15, "capability": 0.15,
            },
        }
        return weights.get(strategy, weights[StrategyType.BALANCED])

    def _determine_confidence(self, forecast: Optional[PlatformForecast]) -> str:
        """确定预测置信度"""
        if not forecast:
            return "low"
        return forecast.confidence or "medium"

    def _generate_recommendation(self, score: PlatformScore, is_top: bool) -> str:
        """生成推荐说明"""
        parts = []
        
        if is_top:
            parts.append(f"[首选] {score.platform}")
        else:
            parts.append(f"[备选] {score.platform}")

        parts.append(f"综合评分: {score.overall_score:.1f}/100")

        if score.forecast:
            f = score.forecast
            if f.estimated_roas > 0:
                parts.append(f"预估ROAS: {f.estimated_roas:.1f}x")
            if f.estimated_cpm > 0:
                parts.append(f"预估CPM: ${f.estimated_cpm:.2f}")
            if f.audience_size > 0:
                parts.append(f"受众规模: {f.audience_size:,}")

        return " | ".join(parts)

    def update_historical_roas(self, platform: str, roas: float):
        """更新历史ROAS数据"""
        self._historical_roas[platform] = roas
        logger.info(f"Updated historical ROAS for {platform}: {roas:.2f}")
