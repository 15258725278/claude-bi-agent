"""
飞书事件接收 API（用于长连接服务转发事件）
"""
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import Optional
from src.utils.logger import logger
import asyncio

router = APIRouter(prefix="/webhook", tags=["webhook"])


class MessageEvent(BaseModel):
    """消息事件模型"""
    event_type: str = "im.message.receive_v1"
    user_id: str
    open_id: Optional[str] = None
    message_id: str
    content: str
    root_id: Optional[str] = None
    raw_event: Optional[dict] = None


class CardActionEvent(BaseModel):
    """卡片动作事件模型"""
    event_type: str = "card.action.trigger"
    user_id: str
    open_id: Optional[str] = None  # 添加 open_id 用于发送消息
    card_id: str  # token
    action_tag: Optional[str] = None
    form_values: dict
    raw_event: Optional[dict] = None


# 全局事件处理器（从 main.py 注入）
_event_handler = None


def set_event_handler(handler):
    """设置事件处理器"""
    global _event_handler
    _event_handler = handler


@router.post("/message")
async def receive_message_event(event: MessageEvent) -> dict:
    """
    接收来自长连接服务的消息事件

    新逻辑：立即返回"正在处理中"，然后在后台处理 Claude SDK
    """
    logger.info(f"收到消息事件: user_id={event.user_id}, content={event.content[:50]}")
    logger.info(f"[_event_handler] 当前值: {_event_handler}")

    # 立即返回"正在处理中"，避免长连接超时
    # 创建后台任务处理实际业务逻辑
    task = asyncio.create_task(_process_message_async(event))
    logger.info(f"后台任务已创建: {task}")

    return {"status": "processing", "message": "正在处理中，请稍候..."}


async def _process_message_async(event: MessageEvent) -> None:
    """
    后台处理消息的异步函数
    """
    logger.info(f"[_process_message_async] 开始处理消息，event_handler={_event_handler}")
    try:
        # 调用事件处理器处理消息
        if _event_handler:
            logger.info(f"[_process_message_async] 调用事件处理器...")
            logger.info(f"[_process_message_async] 构建事件数据...")
            event_data = {
                "header": {"event_type": "im.message.receive_v1"},
                "event": {
                    "message": {
                        "sender": {"sender_id": {"user_id": event.user_id, "open_id": event.open_id}},
                        "message_id": event.message_id,
                        "content": event.content
                    }
                }
            }
            logger.info(f"[_process_message_async] 调用 _event_handler，user_id={event.user_id}, open_id={event.open_id}")
            result = await _event_handler(event_data)
            logger.info(f"[_process_message_async] 事件处理器返回: {result}")
    except Exception as e:
        logger.error(f"处理消息事件失败: {e}", exc_info=True)


@router.post("/message-result")
async def receive_message_result(user_id: str, content: str) -> dict:
    """
    接收处理结果并转发到长连接服务

    这是新的端点，供 Claude 处理完成后调用，将结果发回飞书用户
    """
    try:
        logger.info(f"收到处理结果: user_id={user_id}, content={content[:100]}")

        # 调用长连接服务的转发端点
        import requests

        response = requests.post(
            f"http://localhost:8000/api/v1/webhook/message-result",
            json={
                "user_id": user_id,
                "content": content
            },
            timeout=10.0
        )

        if response.status_code == 200:
            result = response.json()
            return {"status": "ok", "result": result}
        else:
            logger.error(f"发送到长连接服务失败: {response.status_code}")
            return {"status": "error", "message": "发送失败"}

    except Exception as e:
        logger.error(f"转发处理结果失败: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


@router.get("/debug")
async def debug_info() -> dict:
    """调试信息"""
    return {
        "event_handler": "已设置" if _event_handler else "未设置",
        "event_handler_type": type(_event_handler).__name__ if _event_handler else None,
    }


@router.post("/card-action")
async def receive_card_action_event(event: CardActionEvent) -> dict:
    """
    接收来自长连接服务的卡片动作事件
    """
    logger.info(f"收到卡片动作事件: user_id={event.user_id}, open_id={event.open_id}, action={event.action_tag}")

    try:
        # 转发给事件处理器（包含 open_id）
        if _event_handler:
            await _event_handler({
                "header": {"event_type": "card.action.trigger"},
                "event": {
                    "operator": {"user_id": event.user_id, "open_id": event.open_id},
                    "token": event.card_id,
                    "action": {
                        "action_tag": event.action_tag,
                        "form_values": event.form_values
                    }
                }
            })
    except Exception as e:
        logger.error(f"处理卡片动作事件失败: {e}", exc_info=True)

    return {"status": "ok"}
