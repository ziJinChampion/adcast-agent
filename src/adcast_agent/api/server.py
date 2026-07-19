"""
AdCast Agent - FastAPI Server

AI 自动广告投放 Agent 的 REST API + SSE 服务端。
启动时自动初始化 AdCastAgent，关闭时优雅释放资源。
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from adcast_agent.api.routes import auth, campaigns, dashboard, loops, platforms, think


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    from adcast_agent.api.deps import get_agent, shutdown_agent

    # 启动时初始化 Agent
    agent = await get_agent()
    yield
    # 关闭时清理
    await shutdown_agent()


def create_app() -> FastAPI:
    """创建 FastAPI 应用"""
    app = FastAPI(
        title="AdCast Agent API",
        description="AI 自动广告投放 Agent - REST API + SSE",
        version="1.0.0",
        lifespan=lifespan,
    )

    # CORS - 允许前端开发服务器访问
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://localhost:3000",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:3000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 注册路由
    app.include_router(auth.router, prefix="/api/auth", tags=["认证"])
    app.include_router(platforms.router, prefix="/api", tags=["平台"])
    app.include_router(loops.router, prefix="/api", tags=["Loop 管理"])
    app.include_router(campaigns.router, prefix="/api", tags=["Campaign 管理"])
    app.include_router(think.router, prefix="/api", tags=["AI 思考过程"])
    app.include_router(dashboard.router, prefix="/api", tags=["仪表盘"])

    @app.get("/health", tags=["健康检查"])
    async def health_check():
        return {"status": "ok", "service": "adcast-agent-api", "version": "1.0.0"}

    @app.get("/", tags=["根路径"])
    async def root():
        return {
            "service": "AdCast Agent API",
            "version": "1.0.0",
            "docs": "/docs",
            "openapi": "/openapi.json",
            "health": "/health",
        }

    return app


# 全局应用实例（供 uvicorn 直接导入）
app = create_app()
