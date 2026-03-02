#!/usr/bin/env python3
"""
飞书交互模块测试脚本
"""
import asyncio
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.feishu.optimized_client import FeishuClient, PermissionError
from src.feishu.message_parser import MessageParser, MessageDeduplicator
from src.config import settings


async def test_client():
    """测试优化的飞书客户端"""
    print("=" * 50)
    print("测试优化的飞书客户端")
    print("=" * 50)

    # 创建客户端
    client = FeishuClient(
        app_id=settings.FEISHU_APP_ID,
        app_secret=settings.FEISHU_APP_SECRET,
        max_retries=3
    )

    print(f"✓ 客户端创建成功")
    print(f"  APP_ID: {client.app_id}")
    print(f"  最大重试次数: {client.max_retries}")
    print(f"  重试延迟: {client.retry_delay}秒")


async def test_message_parser():
    """测试消息解析器"""
    print("\n" + "=" * 50)
    print("测试消息解析器")
    print("=" * 50)

    # 模拟飞书消息
    message_data = {
        "header": {
            "event_type": "im.message.receive_v1"
        },
        "event": {
            "message": {
                "message_id": "om_test_123",
                "sender": {
                    "sender_id": {
                        "user_id": "user_test_123"
                    }
                },
                "content": '{"text": "Hello <at user_id=\"bot_123\">@bot</at>"}',
                "msg_type": "text"
            }
        }
    }

    # 解析消息
    parsed = MessageParser.parse(message_data)

    print(f"✓ 消息解析成功")
    print(f"  消息类型: {parsed.message_type.value}")
    print(f"  发送者: {parsed.sender_id}")
    print(f"  文本: {parsed.text}")
    print(f"  @提及: {parsed.mentions}")


async def test_deduplicator():
    """测试消息去重器"""
    print("\n" + "=" * 50)
    print("测试消息去重器")
    print("=" * 50)

    deduplicator = MessageDeduplicator()

    # 测试去重
    message_id = "om_test_message_123"

    # 第一次
    if not deduplicator.is_duplicate(message_id):
        print(f"✓ 首次处理消息: {message_id}")
    else:
        print(f"✗ 去重错误: {message_id}")

    # 第二次（应该去重）
    if deduplicator.is_duplicate(message_id):
        print(f"✓ 成功去重消息: {message_id}")
    else:
        print(f"✗ 去重失败: {message_id}")


async def test_permission_error():
    """测试权限错误"""
    print("\n" + "=" * 50)
    print("测试权限错误处理")
    print("=" * 50)

    # 创建一个模拟的权限错误
    perm_error = PermissionError(
        message="应用无权限",
        grant_url="https://open.feishu.cn/app/xxxx"
    )

    print(f"✓ 权限错误创建成功")
    print(f"  错误信息: {str(perm_error)}")
    print(f"  授权链接: {perm_error.grant_url}")


async def main():
    """主测试函数"""
    print("\n🚀 开始测试...\n")

    # 测试客户端
    await test_client()

    # 测试消息解析器
    await test_message_parser()

    # 测试去重器
    await test_deduplicator()

    # 测试权限错误
    await test_permission_error()

    print("\n" + "=" * 50)
    print("✅ 所有测试完成!")
    print("=" * 50)
    print("\n优化模块已就绪，可以在项目中使用！\n")


if __name__ == "__main__":
    asyncio.run(main())
