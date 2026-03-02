"""
健康检查API
"""
from fastapi import APIRouter
from pydantic import BaseModel
from datetime import datetime


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str
    timestamp: str
    services: dict


router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """健康检查"""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now().isoformat(),
        services={
            "database": "ok",  # TODO: 实际检查数据库连接
            "redis": "ok",    # TODO: 实际检查Redis连接
            "claude": "ok",  # TODO: 实际检查Claude SDK
        }
    )
