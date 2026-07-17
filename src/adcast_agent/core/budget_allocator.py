"""
预算分配器 - 基于ROAS的智能预算分配

策略：
1. 等比例分配：各平台均分
2. ROAS加权分配：按预估ROAS比例分配
3. 马太效应：高ROAS平台获得更多预算
4. 探索-利用平衡：保留部分预算给新平台
"""

from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from enum import Enum
import logging

from .decision_engine import PlatformScore, StrategyType

logger = logging.getLogger("adcast.budget")


class AllocationStrategy(Enum):
    """预算分配策略"""
    EQUAL = "equal"                    # 等比例
    ROAS_WEIGHTED = "roas_weighted"    # ROAS加权
    MATTHEW = "matthew"                # 马太效应（平方加权）
    EXPLORATION = "exploration"        # 探索-利用平衡


@dataclass
class BudgetAllocation:
    """预算分配结果"""
    platform: str
    daily_budget: float
    percentage: float
    reasoning: str


class BudgetAllocator:
    """预算分配器"""

    def __init__(self, min_budget_per_platform: float = 100.0):
        self.min_budget_per_platform = min_budget_per_platform

    def allocate(
        self,
        platform_scores: List[PlatformScore],
        total_daily_budget: float,
        strategy: AllocationStrategy = AllocationStrategy.ROAS_WEIGHTED,
        exploration_ratio: float = 0.15,  # 探索比例
    ) -> List[BudgetAllocation]:
        """
        分配预算到各平台
        
        Args:
            platform_scores: 平台评分列表
            total_daily_budget: 总日预算
            strategy: 分配策略
            exploration_ratio: 探索比例（用于exploration策略）
        """
        if not platform_scores:
            return []

        n = len(platform_scores)
        
        # 检查总预算是否满足最低要求
        min_required = self.min_budget_per_platform * n
        if total_daily_budget < min_required:
            logger.warning(
                f"Total budget ${total_daily_budget} is less than minimum "
                f"required ${min_required} for {n} platforms. "
                f"Some platforms may be dropped."
            )

        if strategy == AllocationStrategy.EQUAL:
            allocations = self._allocate_equal(platform_scores, total_daily_budget)
        elif strategy == AllocationStrategy.ROAS_WEIGHTED:
            allocations = self._allocate_roas_weighted(platform_scores, total_daily_budget)
        elif strategy == AllocationStrategy.MATTHEW:
            allocations = self._allocate_matthew(platform_scores, total_daily_budget)
        elif strategy == AllocationStrategy.EXPLORATION:
            allocations = self._allocate_exploration(
                platform_scores, total_daily_budget, exploration_ratio
            )
        else:
            allocations = self._allocate_roas_weighted(platform_scores, total_daily_budget)

        logger.info(
            f"Budget allocation ({strategy.value}): "
            f"{[(a.platform, f'${a.daily_budget:.0f}') for a in allocations]}"
        )
        return allocations

    def _allocate_equal(
        self,
        scores: List[PlatformScore],
        total: float,
    ) -> List[BudgetAllocation]:
        """等比例分配"""
        n = len(scores)
        per_platform = total / n
        
        return [
            BudgetAllocation(
                platform=s.platform,
                daily_budget=per_platform,
                percentage=100.0 / n,
                reasoning=f"等比例分配: ${per_platform:.0f}/天",
            )
            for s in scores
        ]

    def _allocate_roas_weighted(
        self,
        scores: List[PlatformScore],
        total: float,
    ) -> List[BudgetAllocation]:
        """ROAS加权分配"""
        # 获取各平台的ROAS权重
        weights = []
        for s in scores:
            roas = s.forecast.estimated_roas if s.forecast else 0
            # 保底权重
            weight = max(roas, 0.5)
            weights.append(weight)

        total_weight = sum(weights)
        
        allocations = []
        for s, w in zip(scores, weights):
            percentage = (w / total_weight) * 100 if total_weight > 0 else 100.0 / len(scores)
            budget = total * (w / total_weight) if total_weight > 0 else total / len(scores)
            
            # 确保不低于最低预算
            budget = max(budget, self.min_budget_per_platform)
            
            allocations.append(BudgetAllocation(
                platform=s.platform,
                daily_budget=budget,
                percentage=percentage,
                reasoning=f"ROAS加权 (预估ROAS: {w:.1f}x): ${budget:.0f}/天",
            ))

        return allocations

    def _allocate_matthew(
        self,
        scores: List[PlatformScore],
        total: float,
    ) -> List[BudgetAllocation]:
        """马太效应分配（平方加权，强者获得更多）"""
        weights = []
        for s in scores:
            roas = s.forecast.estimated_roas if s.forecast else 0
            weight = max(roas ** 2, 0.25)  # 平方加权
            weights.append(weight)

        total_weight = sum(weights)
        
        allocations = []
        for s, w in zip(scores, weights):
            percentage = (w / total_weight) * 100 if total_weight > 0 else 100.0 / len(scores)
            budget = total * (w / total_weight) if total_weight > 0 else total / len(scores)
            budget = max(budget, self.min_budget_per_platform)
            
            allocations.append(BudgetAllocation(
                platform=s.platform,
                daily_budget=budget,
                percentage=percentage,
                reasoning=f"马太效应 (权重: {w:.1f}): ${budget:.0f}/天",
            ))

        return allocations

    def _allocate_exploration(
        self,
        scores: List[PlatformScore],
        total: float,
        exploration_ratio: float,
    ) -> List[BudgetAllocation]:
        """
        探索-利用平衡分配
        
        大部分预算按ROAS分配给表现好的平台（利用），
        小部分预算分配给新平台用于探索。
        """
        exploration_budget = total * exploration_ratio
        exploitation_budget = total - exploration_budget

        # 利用部分：ROAS加权
        roas_allocations = self._allocate_roas_weighted(scores, exploitation_budget)

        # 探索部分：等比例
        n = len(scores)
        exploration_per_platform = exploration_budget / n

        # 合并
        allocations = []
        for ra in roas_allocations:
            total_budget = ra.daily_budget + exploration_per_platform
            allocations.append(BudgetAllocation(
                platform=ra.platform,
                daily_budget=total_budget,
                percentage=(total_budget / total) * 100,
                reasoning=f"利用(${ra.daily_budget:.0f}) + 探索(${exploration_per_platform:.0f}) = ${total_budget:.0f}/天",
            ))

        return allocations

    def reallocate(
        self,
        current_allocations: List[BudgetAllocation],
        performance_data: Dict[str, float],  # platform -> ROAS
        total_budget: float,
        adjustment_threshold: float = 0.2,  # 调整阈值
    ) -> List[BudgetAllocation]:
        """
        基于实际表现重新分配预算
        
        如果某平台实际ROAS与预期差异过大，触发重新分配。
        """
        new_allocations = []
        
        for alloc in current_allocations:
            actual_roas = performance_data.get(alloc.platform, 0)
            
            # 如果ROAS表现极差（<0.5），减少预算
            if actual_roas < 0.5 and actual_roas > 0:
                new_budget = alloc.daily_budget * 0.5
                reason = f"ROAS过低({actual_roas:.1f}x)，预算减半"
            # 如果ROAS表现极好（>5），增加预算
            elif actual_roas > 5:
                new_budget = alloc.daily_budget * 1.3
                reason = f"ROAS优秀({actual_roas:.1f}x)，预算+30%"
            else:
                new_budget = alloc.daily_budget
                reason = f"ROAS正常({actual_roas:.1f}x)，预算不变"

            new_allocations.append(BudgetAllocation(
                platform=alloc.platform,
                daily_budget=min(new_budget, total_budget * 0.6),  # 单个平台不超过60%
                percentage=(new_budget / total_budget) * 100 if total_budget > 0 else 0,
                reasoning=reason,
            ))

        return new_allocations
