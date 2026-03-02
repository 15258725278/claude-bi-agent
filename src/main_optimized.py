"""
主应用入口 - 优化版（单进程长连接）
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.config import settings
from src.utils.logger import logger, setup_logging
from src.api import v1_router
from src.storage import AsyncSessionLocal, SessionRepository, WaitingContextRepository
from src.feishu.integrated_service import init_feishu_service
from src.claude import ClaudeSessionFactory, ClaudeSessionManager
from src.feishu.enhanced_client import PermissionError

# 全局服务实例
feishu_service = None
claude_session_manager = None

# 初始化日志
setup_logging()


async def handle_feishu_message(data: dict):
    """
    处理飞书消息

    Args:
        data: 消息数据
            {
                "type": "message" | "card_action",
                "parsed": ParsedMessage,
                "event": dict
            }
    """
    global claude_session_manager

    try:
        message_type = data.get("type")
        parsed = data.get("parsed")

        if message_type == "message":
            user_id = parsed.sender_id
            text = parsed.text

            logger.info(f"处理用户消息: user_id={user_id}, text={text[:50]}...")

            # TODO: 转发给 Claude 处理
            # 1. 获取或创建会话
            # 2. 发送给 Claude
            # 3. 发送回复

            # 示例：简单回复
            from src.feishu.integrated_service import get_feishu_service
            service = await get_feishu_service()

            await service.send_message(
                user_id=user_id,
                content=f"你说了: {text}"
            )

        elif message_type == "card_action":
            action = data.get("action", {})
            logger.info(f"处理卡片动作: {action}")

            # TODO: 实现卡片动作处理

    except PermissionError as e:
        logger.warning(f"权限错误: {e}")
        # TODO: 发送权限错误提示

    except Exception as e:
        logger.error(f"处理消息失败: {e}", exc_info=True)


@asynccontextmanager
async def get_dependencies():
    """获取全局依赖"""
    global claude_session_manager

    async with AsyncSessionLocal() as db:
        # 创建仓库实例
        session_repository = SessionRepository(db)
        waiting_repository = WaitingContextRepository()

        # 创建会话管理器
        claude_session_manager = ClaudeSessionManager()

        yield {
            "session_repository": session_repository,
            "waiting_repository": waiting_repository,
            "claude_session_manager": claude_session_manager,
        }


# 创建FastAPI应用
app = FastAPI(
    title=settings.APP_NAME,
    version="3.0.0",
    description="飞书 + Claude SDK 智能对话服务（优化版 - 单进程长连接）",
    docs_url="/docs",
    redoc_url="/redoc",
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(v1_router)


@app.get("/")
async def root():
    """根路径"""
    return {
        "name": settings.APP_NAME,
        "version": "3.0.0",
        "status": "running",
        "features": {
            "websocket_long_connection": True,
            "single_process": True,
            "message_deduplication": True,
            "retry_mechanism": True,
            "permission_handling": True,
            "media_support": True,
            "message_history": True,
        },
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    """健康检查"""
    global feishu_service

    return {
        "status": "ok" if feishu_service and feishu_service.is_running else "error",
        "feishu_connected": feishu_service is not None and feishu_service.is_running if feishu_service else False,
    }


@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    global feishu_service

    logger.info(f"应用启动: {settings.APP_NAME} v3.0.0")
    logger.info(f"环境: {settings.APP_ENV}")
    logger.info(f"飞书应用ID: {settings.FEISHU_APP_ID}")
    logger.info("正在启动集成飞书服务（单进程长连接）...")

    # 初始化飞书服务（不自动启动 WebSocket）
    feishu_service = await init_feishu_service(
        message_handler=handle_feishu_message,
        bot_user_id=None  # TODO: 设置机器人的用户 ID
    )

    # 在后台启动 WebSocket 长连接
    asyncio.create_task(feishu_service.start_in_background())

    logger.info("服务启动成功（优化版）")


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件"""
    global feishu_service

    logger.info("正在关闭服务...")

    if feishu_service:
        await feishu_service.stop()

    logger.info("服务已关闭")
