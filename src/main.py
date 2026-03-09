"""
主应用入口 - 支持群聊功能
"""
import os
import asyncio
import json
from typing import Optional
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.config import settings
from src.utils.logger import logger, setup_logging
from src.api import v1_router
from src.api.v1.webhook import set_event_handler
from src.feishu import FeishuClient
from src.claude import ClaudeSessionFactory, ClaudeSessionManager, FeishuToolsManager
from src.storage import AsyncSessionLocal, SessionRepository, WaitingContextRepository, init_db
from src.core import DemandService
from src.core.group_chat_handler import GroupChatHandler
from src.core.group_chat_session_manager import GroupChatSessionManager
from src.feishu import TopicService
from src.middleware import ErrorHandler, LoggingMiddleware

# 初始化日志
setup_logging()

# 设置 Claude SDK 工作目录
# 这样可以确保 Claude Code CLI 使用正确的工作目录
claude_work_dir = os.path.expanduser(settings.CLAUDE_WORK_DIR)
logger.info(f"Claude SDK 工作目录设置为: {claude_work_dir}")
os.environ['HOME'] = claude_work_dir

# 全局变量 - 在 startup 中初始化
feishu_client: Optional[FeishuClient] = None
topic_service: Optional[TopicService] = None
demand_service: Optional[DemandService] = None
feishu_tools_manager: Optional[FeishuToolsManager] = None
claude_session_manager: Optional[ClaudeSessionManager] = None
group_chat_session_manager: Optional[GroupChatSessionManager] = None
group_chat_handler: Optional[GroupChatHandler] = None
session_repository: Optional[SessionRepository] = None
waiting_repository: Optional[WaitingContextRepository] = None


# 创建FastAPI应用
app = FastAPI(
    title=settings.APP_NAME,
    version="3.1.0",
    description="飞书 + Claude SDK 智能对话服务（支持群聊）",
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
        "version": "3.1.0",
        "status": "running",
        "group_chat_enabled": settings.GROUP_CHAT_ENABLED,
        "docs": "/docs",
    }


@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    global feishu_client, topic_service, demand_service
    global feishu_tools_manager, claude_session_manager
    global group_chat_session_manager, group_chat_handler
    global session_repository, waiting_repository

    logger.info(f"应用启动: {settings.APP_NAME} v3.1.0")
    logger.info(f"环境: {settings.APP_ENV}")
    logger.info(f"飞书应用ID: {settings.FEISHU_APP_ID}")
    logger.info(f"群聊功能: {'启用' if settings.GROUP_CHAT_ENABLED else '禁用'}")

    # 初始化数据库
    logger.info("初始化数据库...")
    await init_db()

    # 创建仓库实例（全局，供后台任务使用）
    logger.info("创建仓库实例...")
    session_repository = SessionRepository()
    waiting_repository = WaitingContextRepository()

    # 创建飞书客户端（全局）
    feishu_client = FeishuClient(
        app_id=settings.FEISHU_APP_ID,
        app_secret=settings.FEISHU_APP_SECRET
    )

    # 创建话题服务（全局）
    topic_service = TopicService(feishu_client)

    # 创建需求服务（全局）
    demand_service = DemandService(topic_service)

    # 创建会话工厂
    claude_factory = ClaudeSessionFactory()

    # 创建工具管理器（全局）
    feishu_tools_manager = FeishuToolsManager(
        feishu_client=feishu_client,
        session_repository=session_repository,
        waiting_repository=waiting_repository
    )

    # 创建会话管理器（全局）
    claude_session_manager = ClaudeSessionManager()

    # 创建群聊会话管理器（全局）
    if settings.GROUP_CHAT_ENABLED:
        group_chat_session_manager = GroupChatSessionManager(
            claude_session_manager=claude_session_manager,
            session_repository=session_repository,
            feishu_client=feishu_client
        )

        # 创建群聊处理器（全局）
        group_chat_handler = GroupChatHandler(
            feishu_client=feishu_client,
            topic_service=topic_service,
            demand_service=demand_service,
            group_chat_session_manager=group_chat_session_manager,
            claude_session_manager=claude_session_manager,
            session_repository=session_repository
        )
        logger.info("群聊处理器已初始化")

    # 创建消息处理器（使用全局变量）
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
                chat_id = message.get("chat_id", "")  # 会话ID
                chat_type = message.get("chat_type", "")  # 会话类型：p2p/group
                root_id = message.get("root_id")  # 话题根消息ID
                thread_id = message.get("thread_id")  # 话题ID
                content_str = message.get("content", "{}")

                # 尝试解析 content
                if isinstance(content_str, str):
                    try:
                        content = json.loads(content_str)
                        text = content.get("text", content_str)
                    except json.JSONDecodeError:
                        text = content_str
                else:
                    text = str(content_str)

                logger.info(f"收到消息: user_id={user_id}, chat_id={chat_id}, chat_type={chat_type}, text={text[:50]}...")

                # 检查是否是群聊消息
                is_group_chat = chat_type == "group" and settings.GROUP_CHAT_ENABLED

                if is_group_chat:
                    logger.info(f"检测到群聊消息: chat_id={chat_id}")
                    if group_chat_handler:
                        logger.info(f"调用群聊处理器...")
                        result = await group_chat_handler.handle_group_message(event)
                        logger.info(f"群聊处理器返回: {result}")
                        return {"status": "ok"}
                    else:
                        logger.warning("群聊处理器未初始化，跳过群聊消息")

                # 单聊消息处理（包括 p2p 和没有 chat_type 的情况）
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
                chat_id = event_data.get("chat_id")  # 群聊ID

                logger.info(f"收到卡片动作: user_id={user_id}, open_id={open_id}, card_id={card_id}, action={action_tag}, chat_id={chat_id}")

                # 检查是否是群聊卡片动作
                if chat_id and settings.GROUP_CHAT_ENABLED:
                    logger.info(f"检测到群聊卡片动作: chat_id={chat_id}")
                    if group_chat_handler:
                        result = await group_chat_handler.handle_demand_card_action(
                            user_id=user_id,
                            open_id=open_id,
                            card_id=card_id,
                            action_tag=action_tag,
                            form_values=form_values,
                            raw_event=event_data
                        )
                        logger.info(f"群聊卡片处理器返回: {result}")
                        return {"status": "ok"}
                    else:
                        logger.warning("群聊处理器未初始化，跳过群聊卡片动作")

                # 单聊卡片动作处理
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
            return {"status": "error", "message": str(e)}

    # 设置事件处理器到 webhook 模块
    logger.info("设置事件处理器到 webhook 模块...")
    set_event_handler(handle_feishu_event)

    logger.info("服务启动成功（事件处理器已设置）")


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件"""
    logger.info("应用关闭")
