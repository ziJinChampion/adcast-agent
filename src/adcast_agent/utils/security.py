"""
安全控制模块 - 预算护栏、人工确认、审计日志
"""

import asyncio
from datetime import datetime, date
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger("adcast.security")


class ApprovalStatus(Enum):
    """审批状态"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    TIMEOUT = "timeout"


class ActionType(Enum):
    """操作类型"""
    CREATE_CAMPAIGN = "create_campaign"
    UPDATE_CAMPAIGN = "update_campaign"
    DELETE_CAMPAIGN = "delete_campaign"
    CREATE_ADGROUP = "create_adgroup"
    UPDATE_ADGROUP = "update_adgroup"
    CREATE_AD = "create_ad"
    UPDATE_BUDGET = "update_budget"
    UPDATE_BID = "update_bid"
    PAUSE_CAMPAIGN = "pause_campaign"
    RESUME_CAMPAIGN = "resume_campaign"


# 需要审批的操作
_APPROVAL_REQUIRED_ACTIONS = {
    ActionType.CREATE_CAMPAIGN,
    ActionType.UPDATE_CAMPAIGN,
    ActionType.DELETE_CAMPAIGN,
    ActionType.CREATE_ADGROUP,
    ActionType.CREATE_AD,
    ActionType.UPDATE_BUDGET,
}

# 高风险操作（总是需要审批）
_HIGH_RISK_ACTIONS = {
    ActionType.DELETE_CAMPAIGN,
    ActionType.UPDATE_BUDGET,
}


@dataclass
class AuditRecord:
    """审计记录"""
    timestamp: datetime
    platform: str
    action: ActionType
    status: str
    campaign_id: Optional[str] = None
    details: Dict = field(default_factory=dict)
    approved_by: Optional[str] = None
    execution_time_ms: Optional[float] = None


@dataclass
class ApprovalRequest:
    """审批请求"""
    id: str
    platform: str
    action: ActionType
    description: str
    details: Dict
    created_at: datetime
    status: ApprovalStatus = ApprovalStatus.PENDING
    resolved_at: Optional[datetime] = None
    approved_by: Optional[str] = None


class BudgetTracker:
    """预算追踪器 - 追踪各平台和全局的花费"""

    def __init__(self, global_limit: float = 10000.0):
        self.global_limit_daily = global_limit
        self._platform_spends: Dict[str, Dict[date, float]] = {}
        self._global_spend: Dict[date, float] = {}

    def record_spend(self, platform: str, amount: float):
        """记录花费"""
        today = date.today()
        
        # 平台花费
        if platform not in self._platform_spends:
            self._platform_spends[platform] = {}
        self._platform_spends[platform][today] = (
            self._platform_spends[platform].get(today, 0) + amount
        )
        
        # 全局花费
        self._global_spend[today] = self._global_spend.get(today, 0) + amount

    def get_platform_spend(self, platform: str, day: Optional[date] = None) -> float:
        """获取平台某日花费"""
        day = day or date.today()
        return self._platform_spends.get(platform, {}).get(day, 0)

    def get_global_spend(self, day: Optional[date] = None) -> float:
        """获取全局某日花费"""
        day = day or date.today()
        return self._global_spend.get(day, 0)

    def get_remaining_budget(self, platform: str, platform_limit: float = 0) -> float:
        """获取剩余预算"""
        global_remaining = self.global_limit_daily - self.get_global_spend()
        
        if platform_limit > 0:
            platform_remaining = platform_limit - self.get_platform_spend(platform)
            return min(global_remaining, platform_remaining)
        
        return global_remaining

    def would_exceed_budget(
        self, platform: str, amount: float, platform_limit: float = 0
    ) -> bool:
        """检查是否会超出预算"""
        remaining = self.get_remaining_budget(platform, platform_limit)
        return amount > remaining


class ApprovalManager:
    """审批管理器 - 管理人工确认流程"""

    def __init__(self, auto_approve_readonly: bool = True):
        self.auto_approve_readonly = auto_approve_readonly
        self._pending_approvals: Dict[str, ApprovalRequest] = {}
        self._approval_callbacks: Dict[str, Callable] = {}

    async def request_approval(
        self,
        request_id: str,
        platform: str,
        action: ActionType,
        description: str,
        details: Dict,
        timeout_seconds: int = 300,
    ) -> ApprovalStatus:
        """
        请求审批
        
        生产环境应该接入企业IM（飞书/钉钉/Slack）或邮件系统
        这里提供可扩展的接口
        """
        # 只读操作自动通过
        if self.auto_approve_readonly and action not in _APPROVAL_REQUIRED_ACTIONS:
            return ApprovalStatus.APPROVED

        request = ApprovalRequest(
            id=request_id,
            platform=platform,
            action=action,
            description=description,
            details=details,
            created_at=datetime.now(),
        )
        self._pending_approvals[request_id] = request

        # 发送审批通知（可扩展为飞书/钉钉/Slack）
        await self._send_notification(request)

        # 等待审批结果
        return await self._wait_for_resolution(request_id, timeout_seconds)

    async def _send_notification(self, request: ApprovalRequest):
        """发送审批通知 - 可扩展"""
        logger.info(
            f"[APPROVAL REQUIRED] {request.platform} - {request.action.value}\n"
            f"Description: {request.description}\n"
            f"Details: {request.details}\n"
            f"Request ID: {request.id}"
        )
        # TODO: 接入飞书/钉钉/Slack机器人

    async def _wait_for_resolution(
        self, request_id: str, timeout_seconds: int
    ) -> ApprovalStatus:
        """等待审批结果"""
        elapsed = 0
        interval = 2
        
        while elapsed < timeout_seconds:
            request = self._pending_approvals.get(request_id)
            if not request:
                return ApprovalStatus.REJECTED
            
            if request.status != ApprovalStatus.PENDING:
                return request.status
            
            await asyncio.sleep(interval)
            elapsed += interval

        # 超时
        request.status = ApprovalStatus.TIMEOUT
        return ApprovalStatus.TIMEOUT

    def approve(self, request_id: str, approved_by: str = "manual"):
        """手动批准"""
        if request := self._pending_approvals.get(request_id):
            request.status = ApprovalStatus.APPROVED
            request.resolved_at = datetime.now()
            request.approved_by = approved_by

    def reject(self, request_id: str):
        """手动拒绝"""
        if request := self._pending_approvals.get(request_id):
            request.status = ApprovalStatus.REJECTED
            request.resolved_at = datetime.now()

    def is_high_risk(self, action: ActionType) -> bool:
        """判断是否为高风险操作"""
        return action in _HIGH_RISK_ACTIONS


class AuditLogger:
    """审计日志 - 记录所有操作"""

    def __init__(self):
        self._records: List[AuditRecord] = []

    def log(
        self,
        platform: str,
        action: ActionType,
        status: str,
        campaign_id: Optional[str] = None,
        details: Optional[Dict] = None,
        execution_time_ms: Optional[float] = None,
    ):
        """记录审计日志"""
        record = AuditRecord(
            timestamp=datetime.now(),
            platform=platform,
            action=action,
            status=status,
            campaign_id=campaign_id,
            details=details or {},
            execution_time_ms=execution_time_ms,
        )
        self._records.append(record)
        
        logger.info(
            f"[AUDIT] {platform} | {action.value} | {status} | "
            f"campaign={campaign_id} | time={execution_time_ms}ms"
        )

    def get_records(
        self,
        platform: Optional[str] = None,
        action: Optional[ActionType] = None,
        limit: int = 100,
    ) -> List[AuditRecord]:
        """获取审计记录"""
        records = self._records
        
        if platform:
            records = [r for r in records if r.platform == platform]
        if action:
            records = [r for r in records if r.action == action]
        
        return records[-limit:]

    def export_to_file(self, filepath: str):
        """导出审计日志到文件"""
        import json
        
        data = [
            {
                "timestamp": r.timestamp.isoformat(),
                "platform": r.platform,
                "action": r.action.value,
                "status": r.status,
                "campaign_id": r.campaign_id,
                "details": r.details,
                "execution_time_ms": r.execution_time_ms,
            }
            for r in self._records
        ]
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)


class SecurityManager:
    """安全管理器 - 统一管理所有安全功能"""

    def __init__(self, config: Optional[Dict] = None):
        from .config import get_config
        
        self.config = config or get_config().security
        self.budget_tracker = BudgetTracker(self.config.global_budget_limit_daily)
        self.approval_manager = ApprovalManager()
        self.audit_logger = AuditLogger()

    async def check_operation(
        self,
        platform: str,
        action: ActionType,
        description: str,
        details: Dict,
        platform_budget_limit: float = 0,
    ) -> bool:
        """
        检查操作是否允许执行
        
        Returns:
            bool: 是否允许执行
        """
        # 1. 检查预算
        estimated_cost = details.get("estimated_cost", 0)
        if estimated_cost > 0 and self.budget_tracker.would_exceed_budget(
            platform, estimated_cost, platform_budget_limit
        ):
            logger.warning(
                f"[BUDGET GUARD] Operation blocked: would exceed budget "
                f"for {platform}"
            )
            self.audit_logger.log(
                platform=platform,
                action=action,
                status="BLOCKED_BUDGET",
                details=details,
            )
            return False

        # 2. 请求审批（如果需要）
        request_id = f"{platform}_{action.value}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        status = await self.approval_manager.request_approval(
            request_id=request_id,
            platform=platform,
            action=action,
            description=description,
            details=details,
        )

        if status != ApprovalStatus.APPROVED:
            logger.warning(
                f"[APPROVAL] Operation {action.value} on {platform} "
                f"was not approved (status: {status.value})"
            )
            self.audit_logger.log(
                platform=platform,
                action=action,
                status=f"BLOCKED_{status.value.upper()}",
                details=details,
            )
            return False

        return True

    def record_execution(
        self,
        platform: str,
        action: ActionType,
        status: str,
        campaign_id: Optional[str] = None,
        details: Optional[Dict] = None,
        execution_time_ms: Optional[float] = None,
    ):
        """记录执行结果"""
        self.audit_logger.log(
            platform=platform,
            action=action,
            status=status,
            campaign_id=campaign_id,
            details=details,
            execution_time_ms=execution_time_ms,
        )
