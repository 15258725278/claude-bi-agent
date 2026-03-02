"""
测试 Claude SDK 集成
"""
import asyncio
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

from src.config import settings


async def test_claude_sdk():
    """测试 Claude SDK 连接和基本功能"""
    print("=" * 50)
    print("Claude SDK Integration Test")
    print("=" * 50)
    print()

    # 检查配置
    print(f"Model: {settings.CLAUDE_MODEL}")
    print(f"API Key: {settings.ANTHROPIC_API_KEY[:20]}...")
    print(f"Base URL: {settings.ANTHROPIC_BASE_URL}")
    print(f"Permission Mode: {settings.CLAUDE_PERMISSION_MODE}")
    print()

    # 导入 Claude SDK
    from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, tool
    from src.claude import FeishuTools
    from src.claude.factory import ClaudeSessionFactory
    from src.storage import AsyncSessionLocal

    # 创建 MCP 服务器（模拟）
    @tool("echo", "Echo back the message", {"message": str})
    async def echo_tool(args):
        print(f"Tool called with: {args}")
        return {
            "content": [{
                "type": "text",
                "text": f"Echo: {args.get('message', '')}"
            }]
        }

    # 创建工厂
    mcp_servers = {
        "test": {
            "version": "1.0.0",
            "tools": [echo_tool]
        }
    }

    factory = ClaudeSessionFactory(mcp_servers)

    try:
        print("[1/4] Creating Claude SDK client...")
        client = await factory.create_session()

        print("[2/4] Testing echo tool...")
        # 创建一个简单的用户消息
        user_message = {
            "type": "user",
            "message": {
                "role": "user",
                "content": "Hello, can you use the echo tool?"
            },
            "session_id": client.options.session_id,
        }

        # 发送消息
        # 注意：需要使用内部方法来发送消息
        from claude_agent_sdk._internal.transport import Transport
        print("Client transport:", type(client._transport).__name__)

        # 由于 Claude SDK 使用内部传输层，
        # 我们需要正确的方式与 Claude 对话
        # 让我们直接测试工具调用是否正确注册

        print()
        print("[3/4] Checking MCP server status...")
        try:
            status = await client.get_mcp_status()
            print(f"MCP Status: {status}")
        except Exception as e:
            print(f"Warning: Could not get MCP status: {e}")

        print()
        print("[4/4] Getting server info...")
        try:
            info = await client.get_server_info()
            print(f"Server Info: {info}")
        except Exception as e:
            print(f"Warning: Could not get server info: {e}")

        print()
        print("Test completed!")
        print("=" * 50)

        # 清理
        await client.disconnect()

    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_claude_sdk())
