"""
错误处理中间件
"""
from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from src.utils.logger import logger
import traceback


class ErrorHandler(BaseHTTPMiddleware):
    """错误处理中间件"""

    async def dispatch(self, request: Request, call_next):
        """
        处理请求并捕获异常
        """
        try:
            response = await call_next(request)
            return response
        except Exception as exc:
            return await self._handle_exception(request, exc)

    async def _handle_exception(self, request: Request, exc: Exception) -> JSONResponse:
        """处理异常"""
        # 记录错误
        logger.error(
            "处理请求时发生错误",
            path=request.url.path,
            method=request.method,
            error=str(exc),
            traceback=traceback.format_exc()
        )

        # 返回错误响应
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Internal Server Error",
                "message": "抱歉，处理您的请求时出错了，请稍后重试。",
                "detail": str(exc) if settings.APP_ENV != "production" else None
            }
        )
