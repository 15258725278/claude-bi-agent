"""
飞书长连接服务（独立进程）
这个脚本在一个独立的进程中运行，避免与 uvicorn 事件循环冲突
"""
import asyncio
import sys
import json
from typing import Optional
import httpx

# 飞书应用配置（从环境或命令行参数获取）
import os

APP_ID = os.getenv("FEISHU_APP_ID", "")
APP_SECRET = os.getenv("FEISHU_APP_SECRET", "")
MAIN_SERVICE_URL = os.getenv("MAIN_SERVICE_URL", "http://localhost:8000")


class LarkEventHandler:
    """飞书事件处理器"""

    def __init__(self, main_service_url: str):
        self.main_service_url = main_service_url
        self.http_client = httpx.AsyncClient(timeout=30.0)

    async def send_to_main_service(self, event_type: str, event_data: dict) -> bool:
        """
        将事件转发到主服务

        Returns:
            bool: 是否成功发送
        """
        try:
            if event_type == "im.message.receive_v1":
                # 转发消息事件
                response = await self.http_client.post(
                    f"{self.main_service_url}/api/v1/webhook/message",
                    json=event_data,
                    timeout=5.0
                )
            elif event_type == "card.action.trigger":
                # 转发卡片动作事件
                response = await self.http_client.post(
                    f"{self.main_service_url}/api/v1/webhook/card-action",
                    json=event_data,
                    timeout=5.0
                )
            else:
                print(f"未知事件类型: {event_type}")
                return False

            if response.status_code == 200:
                return True
            else:
                print(f"发送到主服务失败: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            print(f"发送到主服务异常: {e}")
            return False

    async def handle_message_event(self, event):
        """处理消息事件"""
        print(f"收到消息事件: {json.dumps(event, ensure_ascii=False)[:200]}")

        # 提取关键信息
        header = event.get("header", {})
        event_type = header.get("event_type", "")
        event_data = event.get("event", {})
        message = event_data.get("message", {})

        sender = message.get("sender", {})
        sender_id = sender.get("sender_id", {})
        user_id = sender_id.get("user_id", "")
        message_id = message.get("message_id", "")
        content_data = message.get("content", "{}")

        # 解析内容
        if isinstance(content_data, str):
            try:
                content_obj = json.loads(content_data)
                content_text = content_obj.get("text", "")
            except:
                content_text = content_data
        else:
            content_text = str(content_data)

        # 转发到主服务
        await self.send_to_main_service(
            event_type=event_type,
            event_data={
                "event_type": event_type,
                "user_id": user_id,
                "message_id": message_id,
                "content": content_text,
                "root_id": None,
                "raw_event": event
            }
        )

    async def handle_card_action_event(self, event):
        """处理卡片动作事件"""
        print(f"收到卡片动作事件: {json.dumps(event, ensure_ascii=False)[:200]}")

        # 提取关键信息
        header = event.get("header", {})
        event_type = header.get("event_type", "")
        event_data = event.get("event", {})

        operator = event_data.get("operator", {})
        user_id = operator.get("user_id", "")
        card_id = event_data.get("token", "")

        action = event_data.get("action", {})
        action_tag = action.get("action_tag")
        form_values = action.get("form_values", {})

        # 转发到主服务
        await self.send_to_main_service(
            event_type=event_type,
            event_data={
                "event_type": event_type,
                "user_id": user_id,
                "card_id": card_id,
                "action_tag": action_tag,
                "form_values": form_values,
                "raw_event": event
            }
        )


async def main():
    """主函数"""
    if not APP_ID or not APP_SECRET:
        print("错误: FEISHU_APP_ID 和 FEISHU_APP_SECRET 环境变量未设置")
        print("请设置环境变量后重试")
        sys.exit(1)

    print(f"启动飞书长连接服务")
    print(f"  应用ID: {APP_ID}")
    print(f"  主服务URL: {MAIN_SERVICE_URL}")
    print()

    # 创建事件处理器
    handler = LarkEventHandler(MAIN_SERVICE_URL)

    # 创建事件处理器（lark-oapi 的 EventDispatcherHandler）
    # 注意：对于长连接模式，不需要 encrypt_key 和 verification_token
    from lark_oapi.event.dispatcher_handler import EventDispatcherHandler

    event_handler = EventDispatcherHandler.builder(None, None).build()
    event_handler.on("im.message.receive_v1", handler.handle_message_event)
    event_handler.on("card.action.trigger", handler.handle_card_action_event)

    # 创建 WebSocket 客户端
    from lark_oapi.ws import Client as WsClient

    ws_client = WsClient(
        app_id=APP_ID,
        app_secret=APP_SECRET,
        event_handler=event_handler
    )

    print("飞书长连接已建立，正在监听事件...")
    print("按 Ctrl+C 停止服务\n")

    # 启动客户端（这会阻塞）
    try:
        ws_client.start()
    except KeyboardInterrupt:
        print("\n收到中断信号，正在关闭长连接...")
    except Exception as e:
        print(f"\n长连接错误: {e}")
        sys.exit(1)
    finally:
        await handler.http_client.aclose()
        print("长连接服务已关闭")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n程序已退出")
