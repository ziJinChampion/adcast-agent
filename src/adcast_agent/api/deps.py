"""
AdCast Agent API 依赖注入模块

提供 FastAPI 依赖注入函数和类型别名。
"""

import asyncio
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Annotated, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from adcast_agent.api.schemas import UserInfo

logger = logging.getLogger(__name__)

# =============================================================================
# 配置常量
# =============================================================================

SECRET_KEY = os.environ.get(
    "ADCAST_SECRET_KEY", "adcast-dev-secret-key-change-in-production"
)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 1 天

# =============================================================================
# OAuth2 认证方案
# =============================================================================

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/auth/login",
    scheme_name="ADCAST OAuth2",
    auto_error=False,
)

# =============================================================================
# 用户认证依赖
# =============================================================================


async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
) -> Optional[UserInfo]:
    """解析 JWT Token 并返回当前用户信息。

    Mock 模式：token 存在即可通过，解析其中的 username。
    若 token 不存在或无效，返回 None（允许匿名访问）。
    """
    if not token:
        return None

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: Optional[str] = payload.get("sub")
        user_id: Optional[str] = payload.get("id")
        if username is None:
            return None
        return UserInfo(
            id=user_id or "anonymous",
            username=username,
            role=payload.get("role", "admin"),
        )
    except JWTError:
        return None


async def require_user(
    token: Optional[str] = Depends(oauth2_scheme),
) -> UserInfo:
    """要求必须登录的用户认证依赖。"""
    user = await get_current_user(token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未登录或登录已过期",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


# =============================================================================
# AdCastAgent 单例管理
# =============================================================================

_agent_instance: Optional["AdCastAgent"] = None
_agent_lock = asyncio.Lock()


async def get_agent() -> "AdCastAgent":
    """获取 AdCastAgent 单例实例。首次调用时自动初始化。"""
    global _agent_instance

    if _agent_instance is not None:
        return _agent_instance

    async with _agent_lock:
        if _agent_instance is not None:
            return _agent_instance

        try:
            logger.info("首次初始化 AdCastAgent 单例...")
            # 延迟导入避免循环依赖
            from adcast_agent.main import AdCastAgent

            agent = AdCastAgent()
            await agent.initialize()
            _agent_instance = agent
            logger.info(
                f"AdCastAgent 初始化完成，已连接 {len(agent.platforms)} 个平台"
            )
        except Exception as exc:
            logger.error(f"AdCastAgent 初始化失败: {exc}", exc_info=True)
            raise RuntimeError(f"Agent 初始化失败: {exc}") from exc

    return _agent_instance


async def shutdown_agent() -> None:
    """优雅关闭 AdCastAgent 单例实例。"""
    global _agent_instance

    if _agent_instance is not None:
        try:
            logger.info("正在关闭 AdCastAgent...")
            await _agent_instance.shutdown()
            logger.info("AdCastAgent 已关闭")
        except Exception as exc:
            logger.error(f"关闭出错: {exc}", exc_info=True)
        finally:
            _agent_instance = None


def get_agent_sync() -> Optional["AdCastAgent"]:
    """同步获取 Agent 实例（用于 lifespan 等同步上下文）。"""
    return _agent_instance


# =============================================================================
# 类型别名
# =============================================================================

AgentDep = Annotated["AdCastAgent", Depends(get_agent)]
UserDep = Annotated[Optional[UserInfo], Depends(get_current_user)]
RequiredUserDep = Annotated[UserInfo, Depends(require_user)]
