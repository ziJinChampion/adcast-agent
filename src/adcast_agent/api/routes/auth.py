"""
认证路由模块

提供用户登录和 JWT Token 生成功能。
当前为 Mock 模式：任意用户名/密码均可登录。
"""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, status
from jose import jwt

from adcast_agent.api.deps import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
from adcast_agent.api.schemas import Token, LoginRequest

router = APIRouter(tags=["认证"])


def _create_access_token(username: str, expires_delta: Optional[timedelta] = None) -> str:
    """创建 JWT 访问令牌。"""
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode = {
        "sub": username,
        "id": f"user_{username}",
        "role": "admin",
        "exp": expire,
    }
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


@router.post("/login", response_model=Token, summary="用户登录")
async def login(request: LoginRequest) -> Token:
    """用户登录接口

    Mock 模式：任意用户名/密码均可登录，返回 JWT Token。
    生产环境应连接真实用户数据库验证密码。
    """
    # Mock 验证：任意用户名密码都通过
    access_token = _create_access_token(request.username)
    return Token(access_token=access_token)


@router.get("/me", summary="获取当前用户信息")
async def get_me(user: Optional[dict] = None) -> dict:
    """获取当前登录用户信息。"""
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未登录",
        )
    return user
