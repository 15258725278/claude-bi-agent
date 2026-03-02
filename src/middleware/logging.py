"""
日志中间件
"""
import time
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from src.utils.logger import logger


class LoggingMiddleware(BaseHTTPMiddleware):
    """日志中间件"""

    async def dispatch(self, request: Request, call_next):
        """处理请求并记录日志"""
        start_time = time.time()

        # 记录请求
        logger.info(
            "incoming_request",
            method=request.method,
            path=request.url.path,
            query_params=str(request.query_params),
            client=request.client.host if request.client else None,
        )

        # 调用下一个中间件/路由
        response = await call_next(request)

        # 记录响应
        process_time = (time.time() - start_time) * 1000
        logger.info(
            "outgoing_response",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            process_time_ms=f"{process_time:.2f}",
        )

        return response
