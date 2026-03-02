"""
Claude客户端封装
"""
from typing import Optional
from claude_agent_sdk import ClaudeSDKClient, Message, AssistantMessage, ResultMessage


class ClaudeClientWrapper:
    """Claude客户端封装"""

    def __init__(self, client: ClaudeSDKClient):
        self.client = client
        self._current_session_id: Optional[str] = None

    async def query(self, prompt: str) -> None:
        """发送查询"""
        await self.client.query(prompt)

    async def receive_response(self):
        """接收单次响应"""
        async for message in self.client.receive_response():
            # 保存Claude session_id
            if isinstance(message, ResultMessage) and hasattr(message, 'session_id'):
                self._current_session_id = message.session_id
            yield message

    @property
    def claude_session_id(self) -> Optional[str]:
        """获取Claude内部会话ID"""
        return self._current_session_id

    async def disconnect(self):
        """断开连接"""
        await self.client.disconnect()
