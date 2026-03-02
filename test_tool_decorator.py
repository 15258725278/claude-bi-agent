"""测试Claude SDK工具装饰器"""
import asyncio
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, tool

# 简单测试：创建一个简单的echo工具
@tool("echo", "Echo back message", {"message": str})
async def echo_tool(args):
    print(f"Echo tool called with: {args}")
    return {"content": [{"type": "text", "text": f"Echo: {args.get('message', '')}"}]}

# 测试工具函数
asyncio.run(main())
