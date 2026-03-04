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


def get_bot_open_id(app_id: str, app_secret: str) -> Optional[str]:
    """
    获取机器人自己的 open_id

    Args:
        app_id: 应用 ID
        app_secret: 应用密钥

    Returns:
        机器人的 open_id
    """
    try:
        # 获取 tenant_access_token
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        payload = {"app_id": app_id, "app_secret": app_secret}
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        result = response.json()

        if result.get("code", 0) != 0:
            print(f"[长连接] 获取 tenant_access_token 失败: {result}")
            return None

        tenant_access_token = result["tenant_access_token"]

        # 使用 bot/v3/info 获取机器人信息
        url2 = "https://open.feishu.cn/open-apis/bot/v3/info"
        headers = {
            "Authorization": f"Bearer {tenant_access_token}",
            "Content-Type": "application/json"
        }
        response2 = requests.get(url2, headers=headers, timeout=10)
        response2.raise_for_status()
        result2 = response2.json()

        if result2.get("code", 0) == 0:
            bot_open_id = result2["bot"]["open_id"]
            print(f"[长连接] 获取到机器人 open_id: {bot_open_id}")
            return bot_open_id
        else:
            print(f"[长连接] 获取机器人信息失败: {result2}")
            return None

    except Exception as e:
        print(f"[长连接] 获取机器人 open_id 异常: {e}")
        import traceback
        traceback.print_exc()
        return None


class LarkEventHandler:
    """飞书事件处理器"""

    def __init__(self, main_service_url: str, bot_open_id: Optional[str] = None):
        self.main_service_url = main_service_url
        self.thread_local = threading.local()
        self.bot_open_id = bot_open_id  # 机器人的 open_id

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
        """处理消息事件 - P2ImMessageReceiveV1格式（基于官方demo）"""
        print(f"[长连接] 收到消息事件: {type(event)}")

        try:
            # P2ImMessageReceiveV1 对象结构 - 参考官方demo
            # - event: P2ImMessageReceiveV1Data (包含 sender, message)
            if not hasattr(event, 'event'):
                print(f"[长连接] 无法解析事件格式: 缺少 event 属性")
                return

            # 获取消息基本信息 - 参考官方demo的访问方式
            event_data = event.event
            message = event_data.message
            sender = event_data.sender

            # 获取关键信息
            message_id = message.message_id
            chat_type = message.chat_type
            chat_id = message.chat_id
            root_id = message.root_id
            thread_id = message.thread_id

            sender_id = sender.sender_id
            user_id = sender_id.user_id
            open_id = sender_id.open_id

            # 如果 user_id 为 None，使用 open_id 作为替代（主服务要求 user_id 必须是字符串）
            if not user_id and open_id:
                user_id = open_id
                print(f"[长连接] user_id 为 None，使用 open_id 作为替代")

            # 解析消息内容
            content_str = message.content
            if isinstance(content_str, str):
                try:
                    content = json.loads(content_str)
                    content_text = content.get("text", content_str)
                except json.JSONDecodeError:
                    content_text = content_str
            else:
                content_text = str(content_str)

            print(f"[长连接] 消息详情:")
            print(f"  - chat_type: {chat_type}")
            print(f"  - chat_id: {chat_id}")
            print(f"  - user_id: {user_id}")
            print(f"  - open_id: {open_id}")
            print(f"  - root_id: {root_id}")
            print(f"  - thread_id: {thread_id}")
            print(f"  - content: {content_text[:50] if content_text else ''}...")

            # 检查是否需要处理消息
            should_process = self._should_process_message(message, content_text, thread_id)
            if not should_process:
                print(f"[长连接] 消息不满足处理条件，忽略")
                return

            # 转发到主服务 - 包含群聊相关字段
            self.send_to_main_service(
                event_type="im.message.receive_v1",
                event_data={
                    "event_type": "im.message.receive_v1",
                    "user_id": user_id,
                    "open_id": open_id,
                    "message_id": message_id,
                    "chat_id": chat_id,
                    "chat_type": chat_type,
                    "root_id": root_id,
                    "thread_id": thread_id,
                    "content": content_text
                }
            )

        except Exception as e:
            print(f"[长连接] 处理消息事件异常: {e}")
            import traceback
            traceback.print_exc()
            # 不抛出异常，让 SDK 继续处理其他消息

    def _should_process_message(self, message, content_text: str, thread_id: Optional[str]) -> bool:
        """
        判断是否需要处理消息

        规则：
        1. 私聊消息：总是处理
        2. 群聊话题内消息（thread_id 存在）：总是处理（话题内的消息都需要处理）
        3. 群聊中非话题消息（thread_id 不存在）：必须@机器人才处理

        Args:
            message: 消息对象
            content_text: 消息文本内容
            thread_id: 话题ID

        Returns:
            是否需要处理
        """
        chat_type = message.chat_type

        # 私聊消息总是处理
        if chat_type == "p2p":
            return True

        # 群聊话题内消息总是处理
        if thread_id:
            print(f"[长连接] 群聊话题内消息，需要处理")
            return True

        # 群聊中非话题消息：检查是否@机器人
        if chat_type == "group":
            # 检查消息中的 mentions（使用 try-except 防止 SDK 内部错误）
            mentions = None
            try:
                mentions = getattr(message, 'mentions', None)
                if mentions is None:
                    mentions = []
                # 确保 mentions 是可迭代对象
                if not hasattr(mentions, '__iter__'):
                    mentions = []
            except Exception as e:
                print(f"[长连接] 获取 mentions 异常: {e}，使用空列表")
                mentions = []

            print(f"[长连接] 群聊消息 mentions 数量: {len(mentions) if mentions else 0}")
            print(f"[长连接] 机器人 open_id: {self.bot_open_id}")

            # 如果 mentions 为空，直接返回 False（不处理）
            if not mentions:
                print(f"[长连接] 无 mentions，忽略")
                return False

            if not self.bot_open_id:
                # 没有获取到机器人 ID，使用关键字匹配"分析小助手"
                if "分析小助手" in content_text or "帮" in content_text:
                    print(f"[长连接] 关键字匹配，需要处理")
                    return True
                else:
                    print(f"[长连接] 未匹配关键字，忽略")
                    return False
            else:
                # 检查 mentions 中是否有机器人的 open_id
                bot_mentioned = False
                for mention in mentions:
                    try:
                        # 官方demo: mention.id.open_id
                        mention_open_id = None
                        if hasattr(mention, 'id') and hasattr(mention.id, 'open_id'):
                            mention_open_id = mention.id.open_id

                        print(f"[长连接] mention open_id: {mention_open_id}")

                        if mention_open_id == self.bot_open_id:
                            bot_mentioned = True
                            break
                    except Exception as e:
                        print(f"[长连接] 处理 mention 异常: {e}")
                        continue

                if bot_mentioned:
                    print(f"[长连接] 检测到@机器人，需要处理")
                    return True
                else:
                    print(f"[长连接] 未@机器人，忽略")
                    return False

        return False

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

    # 获取机器人的 open_id
    print(f"[长连接] 正在获取机器人信息...")
    bot_open_id = get_bot_open_id(APP_ID, APP_SECRET)
    if not bot_open_id:
        print(f"[长连接] 警告: 无法获取机器人 open_id，将使用关键字匹配")
        bot_open_id = None
    else:
        print(f"[长连接] 机器人 open_id: {bot_open_id}")

    # 创建事件处理器
    handler = LarkEventHandler(MAIN_SERVICE_URL, bot_open_id)

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
