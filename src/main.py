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
from src.api.v1.webhook import set_event_handler
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
    version="3.0.0",
    description="屈臣氏 BI 数据分析智能助手",
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
    global long_connection_client, feishu_tools_manager, claude_session_manager

    logger.info(f"应用启动: {settings.APP_NAME} v3.0.0")
    logger.info(f"环境: {settings.APP_ENV}")
    logger.info(f"飞书应用ID: {settings.FEISHU_APP_ID}")
    logger.info("开始执行 startup_event...")

    # 初始化数据库表
    from src.storage import init_db
    logger.info("初始化数据库表...")
    await init_db()
    logger.info("数据库表初始化完成")

    # 创建依赖
    logger.info("创建依赖...")
    from src.storage import AsyncSessionLocal, SessionRepository, WaitingContextRepository

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

        # 创建会话管理器
        claude_session_manager = ClaudeSessionManager()

        # 创建消息处理器
        async def handle_feishu_event(event):
            """处理飞书事件"""
            logger.info(f"收到飞书事件: {event.get('header', {}).get('event_type', 'unknown')}")

            try:
                event_type = event.get("header", {}).get("event_type", "")

                if event_type == "im.message.receive_v1":
                    # 消息事件
                    event_data = event.get("event", {})
                    message = event_data.get("message", {})
                    sender_id = message.get("sender", {}).get("sender_id", {})
                    user_id = sender_id.get("user_id", "")
                    open_id = sender_id.get("open_id", "")
                    message_id = message.get("message_id", "")
                    content_str = message.get("content", "{}")

                    # 尝试解析 content，可能是 JSON 或普通字符串
                    if isinstance(content_str, str):
                        try:
                            content = json.loads(content_str)
                            text = content.get("text", content_str)
                        except json.JSONDecodeError:
                            # 不是 JSON，直接使用
                            text = content_str
                    else:
                        text = str(content_str)

                    logger.info(f"收到用户消息: user_id={user_id}, text={text[:50]}...")

                    # 处理消息
                    from src.core.session_manager import SessionManager
                    session_manager = SessionManager(
                        session_repository=session_repository,
                        waiting_repository=waiting_repository,
                        feishu_client=feishu_client,
                        claude_session_manager=claude_session_manager,
                        feishu_tools_manager=feishu_tools_manager,
                    )

                    await session_manager.dispatch(
                        user_id=user_id,
                        open_id=open_id,
                        message_id=message_id,
                        content=text,
                        message=message
                    )

                elif event_type == "card.action.trigger":
                    # 卡片动作事件
                    event_data = event.get("event", {})
                    operator = event_data.get("operator", {})
                    user_id = operator.get("user_id", "")
                    open_id = operator.get("open_id", "")
                    card_id = event_data.get("token", "")
                    action = event_data.get("action", {})
                    action_tag = action.get("action_tag", "")
                    form_values = action.get("form_values", {})

                    logger.info(f"收到卡片动作事件: user_id={user_id}, open_id={open_id}, card_id={card_id}, action={action_tag}")

                    # 处理卡片动作
                    from src.core.session_manager import SessionManager
                    session_manager = SessionManager(
                        session_repository=session_repository,
                        waiting_repository=waiting_repository,
                        feishu_client=feishu_client,
                        claude_session_manager=claude_session_manager,
                        feishu_tools_manager=feishu_tools_manager,
                    )

                    await session_manager.dispatch_card_action(
                        user_id=user_id,
                        open_id=open_id,
                        card_id=card_id,
                        action_tag=action_tag,
                        form_values=form_values
                    )

                else:
                    logger.warning(f"未知事件类型: {event_type}")

                return {"status": "ok"}

            except Exception as e:
                logger.error(f"处理飞书事件失败: {e}", exc_info=True)

        # 设置事件处理器到 webhook 模块
        logger.info("设置事件处理器到 webhook 模块...")
        set_event_handler(handle_feishu_event)

        logger.info("服务启动成功（事件处理器已设置）")


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件"""
    logger.info("应用关闭")
