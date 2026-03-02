"""
飞书事件接收 API（用于长连接服务转发事件）
"""
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import Optional
from src.utils.logger import logger

router = APIRouter(prefix="/webhook", tags=["webhook"])


class MessageEvent(BaseModel):
    """消息事件模型"""
    event_type: str = "im.message.receive_v1"
    user_id: str
    message_id: str
    content: str
    root_id: Optional[str] = None
    raw_event: dict


class CardActionEvent(BaseModel):
    """卡片动作事件模型"""
    event_type: str = "card.action.trigger"
    user_id: str
    card_id: str  # token
    action_tag: Optional[str] = None
    form_values: dict
    raw_event: dict


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

    这是长连接服务将飞书消息转发到主服务的端点
    """
    logger.info(f"收到消息事件: user_id={event.user_id}, content={event.content[:50]}")

    # 转发给事件处理器
    if _event_handler:
        try:
            await _event_handler({
                "header": {"event_type": "im.message.receive_v1"},
                "event": {
                    "message": {
                        "sender": {"sender_id": {"user_id": event.user_id}},
                        "message_id": event.message_id,
                        "content": event.content
                    }
                }
            })
        except Exception as e:
            logger.error(f"处理消息事件失败: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"处理事件失败: {str(e)}"
            )

    return {"status": "ok"}


@router.post("/card-action")
async def receive_card_action_event(event: CardActionEvent) -> dict:
    """
    接收来自长连接服务的卡片动作事件

    这是长连接服务将飞书卡片动作转发到主服务的端点
    """
    logger.info(f"收到卡片动作事件: user_id={event.user_id}, action={event.action_tag}")

    # 转发给事件处理器
    if _event_handler:
        try:
            await _event_handler({
                "header": {"event_type": "card.action.trigger"},
                "event": {
                    "operator": {"user_id": event.user_id},
                    "token": event.card_id,
                    "action": {
                        "action_tag": event.action_tag,
                        "form_values": event.form_values
                    }
                }
            })
        except Exception as e:
            logger.error(f"处理卡片动作事件失败: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"处理事件失败: {str(e)}"
            )

    return {"status": "ok"}
