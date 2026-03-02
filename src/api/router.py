"""
API路由
"""
from fastapi import APIRouter

from .v1.sessions import router as sessions_router
from .v1.health import router as health_router
from .v1.webhook import router as webhook_router

# 创建v1路由器
v1_router = APIRouter(prefix="/api/v1")

# 注册子路由
v1_router.include_router(sessions_router)
v1_router.include_router(health_router)
v1_router.include_router(webhook_router)


__all__ = ["v1_router"]
