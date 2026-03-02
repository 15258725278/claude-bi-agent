"""
主应用入口 - 基于官方文档简化版
"""
import asyncio
import json
import re
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from src.config import settings
from src.utils.logger import logger, setup_logging
from src.utils import safe_json_dumps
from src.api import v1_router
from src.feishu import FeishuClient, FeishuLongConnectionClient
from src.claude import ClaudeSessionFactory, ClaudeSessionManager, FeishuToolsManager
from src.storage import AsyncSessionLocal
from src.middleware import ErrorHandler, LoggingMiddleware

# 长连接客户端（全局）
long_connection_client: Optional[FeishuLongConnectionClient] = None

# 全局会话管理器
claude_session_manager: ClaudeSessionManager()
# 全局工具管理器
feishu_tools_manager = FeishuToolsManager(
    feishu_client=FeishuClient(
        app_id=settings.FEISHU_APP_ID,
        app_secret=settings.FEISHU_APP_SECRET
    ),
    session_repository=None,  # 暂时在启动事件中初始化
    waiting_repository=None,  # 暂时在启动事件中初始化
)

# 初始化日志
setup_logging()


@asynccontextmanager
async def get_dependencies():
    """获取全局依赖"""
    from src.storage import AsyncSessionLocal, SessionRepository, WaitingContextRepository
    from src.claude import ClaudeSessionFactory, ClaudeSessionManager, FeishuToolsManager
    from src.feishu import FeishuClient
    from src.core.demand_detector import DemandDetector

    async with AsyncSessionLocal() as db:
        # 创建仓库实例
        session_repository = SessionRepository(db)
        waiting_repository = WaitingContextRepository()

        # 创建飞书客户端
        feishu_client = FeishuClient(
            app_id=settings.FEISHU_APP_ID,
            app_secret=settings.FEISHU_APP_SECRET
        )

        # 创建工具管理器
        feishu_tools_manager = FeishuToolsManager(
            feishu_client=feishu_client,
            session_repository=session_repository,
            waiting_repository=waiting_repository
        )

        # 创建会话工厂
        claude_factory = ClaudeSessionFactory()

        # 设置工具管理器的会话引用
        feishu_tools_manager.session_repository = session_repository
        feishu_tools_manager.waiting_repository = waiting_repository

        # 创建需求检测器
        from src.core.demand_detector import DemandDetector
        demand_detector = DemandDetector(session_repository)

        # 创建会话管理器
        claude_session_manager = ClaudeSessionManager()

        # 创建简单的消息处理器
        async def handle_feishu_event(event):
            """处理飞书事件 - 简化版"""
            from src.utils.logger import logger
            logger.info(f"收到飞书事件: {event}")

            try:
                event_type = event.get("header", {}).get("event_type", "")

                if event_type == "im.message.receive_v1":
                    # 消息事件 - 简化处理，只记录日志
                    event_data = event.get("event", {})
                    message = event_data.get("message", {})
                    user_id = message.get("sender", {}).get("sender_id", {}).get("user_id", "")
                    content_str = message.get("content", "{}")
                    content = json.loads(content_str) if isinstance(content_str, str) else content_str
                    text = content.get("text", "")

                    logger.info(f"收到用户消息: user_id={user_id}, text={text[:50]}...")

                    # TODO: 转发给 Claude 处理

                elif event_type == "card.action.trigger":
                    # 卡片动作事件
                    logger.info("收到卡片动作事件")

                    # TODO: 转发给 Claude 处理

                else:
                    logger.warning(f"未知事件类型: {event_type}")

                # 返回成功响应
                return {"status": "ok"}

            except Exception as e:
                logger.error(f"处理飞书事件失败: {e}", exc_info=True)

        yield {
            "session_repository": session_repository,
            "feishu_client": feishu_client,
            "dispatcher": None,  # 暂时不需要分发器
            "event_handler": handle_feishu_event,
        }


# 创建FastAPI应用
app = FastAPI(
    title=settings.APP_NAME,
    version="2.0.0",
    description="飞书 + Claude SDK 智能对话服务（简化版）",
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

# 添加自定义中间件
app.add_middleware(ErrorHandler)
app.add_middleware(LoggingMiddleware)

# 注册路由
app.include_router(v1_router)


@app.get("/")
async def root():
    """根路径"""
    return {
        "name": settings.APP_NAME,
        "version": "2.0.0",
        "status": "running",
        "docs": "/docs",
    }


@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    global long_connection_client

    logger.info(f"应用启动: {settings.APP_NAME} v2.0.0")
    logger.info(f"环境: {settings.APP_ENV}")
    logger.info(f"飞书应用ID: {settings.FEISHU_APP_ID}")
    logger.info("服务启动成功（简化版）")


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件"""
    logger.info("应用关闭")
