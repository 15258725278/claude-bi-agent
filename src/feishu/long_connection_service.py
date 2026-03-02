"""
飞书长连接服务（独立进程）- 参考 OpenClaw 实现
"""
import sys
import json
import threading
from typing import Optional
import requests

# 飞书应用配置（从环境或命令行参数获取）
import os

APP_ID = os.getenv("FEISHU_APP_ID", "")
APP_SECRET = os.getenv("FEISHU_APP_SECRET", "")
MAIN_SERVICE_URL = os.getenv("MAIN_SERVICE_URL", "http://localhost:8000")


class LarkEventHandler:
    """飞书事件处理器"""

    def __init__(self, main_service_url: str):
        self.main_service_url = main_service_url
        self.thread_local = threading.local()

    def send_to_main_service(self, event_type: str, event_data: dict) -> bool:
        """
        将事件转发到主服务

        Returns:
            bool: 是否成功发送
        """
        try:
            if event_type == "im.message.receive_v1":
                # 转发消息事件
                response = requests.post(
                    f"{self.main_service_url}/api/v1/webhook/message",
                    json=event_data,
                    timeout=60.0
                )
            elif event_type == "card.action.trigger":
                # 转发卡片动作事件
                response = requests.post(
                    f"{self.main_service_url}/api/v1/webhook/card-action",
                    json=event_data,
                    timeout=60.0
                )
            else:
                print(f"[长连接] 未知事件类型: {event_type}")
                return False

            if response.status_code == 200:
                print(f"[长连接] 成功转发事件到主服务: {event_type}")
                return True
            else:
                print(f"[长连接] 发送到主服务失败: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            print(f"[长连接] 发送到主服务异常: {e}")
            return False

    def handle_message_event(self, event):
        """处理消息事件 - P2ImMessageReceiveV1格式"""
        print(f"[长连接] 收到消息事件: {type(event)}")

        # P2ImMessageReceiveV1 对象结构:
        # - header: 来自 EventContext (父类)
        # - event: P2ImMessageReceiveV1Data (包含 sender 和 message)
        if not hasattr(event, 'event'):
            print(f"[长连接] 无法解析事件格式: 缺少 event 属性")
            return

        message = event.event.message
        sender = event.event.sender

        # 打印 sender 的完整结构，用于调试
        print(f"[长连接] sender 对象: {sender}")
        print(f"[长连接] sender_id: {sender.sender_id}")
        print(f"[长连接] sender_id 属性: {dir(sender.sender_id)}")

        # 尝试获取 user_id 和 open_id
        user_id = sender.sender_id.user_id
        open_id = getattr(sender.sender_id, 'open_id', None)
        print(f"[长连接] user_id={user_id}, open_id={open_id}")

        message_id = message.message_id
        content = message.content
        root_id = event.event.root_id if hasattr(event.event, 'root_id') else None

        # 解析消息内容
        content_text = ""
        if hasattr(content, 'text'):
            content_text = content.text
        elif isinstance(content, str):
            content_text = content
        else:
            content_text = str(content)

        print(f"[长连接] 用户 {user_id} 发送消息: {content_text[:50] if content_text else ''}")

        # 转发到主服务（同时发送 user_id 和 open_id）
        self.send_to_main_service(
            event_type="im.message.receive_v1",
            event_data={
                "event_type": "im.message.receive_v1",
                "user_id": user_id,
                "open_id": open_id,
                "message_id": message_id,
                "content": content_text,
                "root_id": root_id
            }
        )

    def handle_card_action_event(self, event):
        """处理卡片动作事件 - P2CardActionTrigger格式"""
        from lark_oapi.event.callback.model.p2_card_action_trigger import P2CardActionTriggerResponse

        print(f"[长连接] 收到卡片动作事件: {type(event)}")

        # 提取关键信息（包括 open_id）
        user_id = event.operator.user_id
        open_id = getattr(event.operator, 'open_id', None)  # 获取 open_id
        card_id = event.token
        action_tag = event.action.action_tag
        form_values = event.action.form_values

        print(f"[长连接] 卡片动作: user_id={user_id}, open_id={open_id}, action={action_tag}")

        # 转发到主服务（包含 open_id）
        self.send_to_main_service(
            event_type="card.action.trigger",
            event_data={
                "event_type": "card.action.trigger",
                "user_id": user_id,
                "open_id": open_id,
                "card_id": card_id,
                "action_tag": action_tag,
                "form_values": form_values
            }
        )

        # 返回成功的响应
        resp = {"toast": {"type": "success", "content": "卡片交互成功"}}
        return P2CardActionTriggerResponse(resp)


def main():
    """主函数（同步）"""
    if not APP_ID or not APP_SECRET:
        print("错误: FEISHU_APP_ID 和 FEISHU_APP_SECRET 环境变量未设置")
        print("请设置环境变量后重试")
        sys.exit(1)

    print(f"[长连接] 启动飞书长连接服务")
    print(f"[长连接]   应用ID: {APP_ID}")
    print(f"[长连接]   主服务URL: {MAIN_SERVICE_URL}")
    print()

    # 创建事件处理器
    handler = LarkEventHandler(MAIN_SERVICE_URL)

    # 创建事件处理器（lark-oapi 的 EventDispatcherHandler）
    # 注意：对于长连接模式，不需要 encrypt_key 和 verification_token
    from lark_oapi.event.dispatcher_handler import EventDispatcherHandler

    # 注册 p2 格式的事件处理器（长连接使用 p2 格式）
    # 使用 register_p2_im_message_receive_v1 而不是 register_p2_customized_event
    event_handler = (EventDispatcherHandler.builder(
        encrypt_key="",
        verification_token=""
    )
    .register_p2_im_message_receive_v1(handler.handle_message_event)
    .register_p2_card_action_trigger(handler.handle_card_action_event)
    .build())
    print("[长连接] 使用 register_p2_im_message_receive_v1 注册事件处理器")

    # 创建 WebSocket 客户端
    from lark_oapi.ws import Client as WsClient

    ws_client = WsClient(
        app_id=APP_ID,
        app_secret=APP_SECRET,
        event_handler=event_handler
    )

    print("[长连接] 飞书长连接已建立，正在监听事件...")
    print("[长连接] 按 Ctrl+C 停止服务\n")

    # 启动客户端（这会阻塞）
    try:
        ws_client.start()
    except KeyboardInterrupt:
        print("\n[长连接] 收到中断信号，正在关闭长连接...")
    except Exception as e:
        print(f"\n[长连接] 长连接错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        print("[长连接] 长连接服务已关闭")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n程序已退出")
