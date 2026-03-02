"""
Claude SDK integration and tools - simplified version
"""
import asyncio
from typing import Dict, Any, Optional
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, tool
from src.config import settings
from src.models.session import WaitingContext
from src.feishu import FeishuClient
from src.storage import SessionRepository, WaitingContextRepository


def create_simple_echo_tool():
    """
    Create a simple echo tool for testing

    Returns:
        Tool function
    """
    @tool("echo", "Echo back message", {"message": str})
    async def echo_tool(args: Dict[str, Any]) -> Dict[str, Any]:
        print(f"Echo tool called with: {args}")
        return {"content": [{"type": "text", "text": f"Echo: {args.get('message', '')}"}]}

    return echo_tool


def ask_user_for_info(
    feishu_client: FeishuClient,
    session_repository: SessionRepository,
    waiting_repository: WaitingContextRepository,
) -> str:
    """
    Create ask_user_for_info tool (simplified version)

    This tool allows Claude to ask the user for additional information.
    """
    async def tool_func(args: Dict[str, Any]) -> Dict[str, Any]:
        question = args["question"]
        info_type = args.get("info_type", "text")

        from src.utils.logger import logger
        logger.info(f"Received ask_user_for_info request: question={question}, type={info_type}")

        return {
            "content": [{
                "type": "text",
                "text": f"Received question: {question} (info_type: {info_type})."
            }]
        }

    tool_func.__name__ = "ask_user_for_info"


def send_message(
    feishu_client: FeishuClient,
) -> str:
    """
    Create send_message tool (simplified version)

    This tool allows Claude to send a plain text message to the user.
    """
    async def tool_func(args: Dict[str, Any]) -> Dict[str, Any]:
        content = args["content"]

        from src.utils.logger import logger
        logger.info(f"Received send_message request: content={content[:50]}")

        return {
            "content": [{
                "type": "text",
                "text": f"Message prepared: {content[:50]}..."
            }]
        }

    tool_func.__name__ = "send_message"
    return tool_func


def update_card(
    feishu_client: FeishuClient,
) -> str:
    """
    Create update_card tool (simplified version)

    This tool allows Claude to update an interactive card.
    """
    async def tool_func(args: Dict[str, Any]) -> Dict[str, Any]:
        card_id = args["card_id"]
        status = args.get("status", "active")
        content = args.get("content", "")

        from src.utils.logger import logger
        logger.info(f"Received update_card request: card_id={card_id}, status={status}")

        return {
            "content": [{
                "type": "text",
                "text": f"Card update prepared: {content[:50]}..."
            }]
        }

    tool_func.__name__ = "update_card"
    return tool_func


class FeishuToolsManager:
    """
    Feishu tool manager

    Manages tool creation and retrieval
    """

    def __init__(
        self,
        feishu_client: FeishuClient,
        session_repository: SessionRepository,
        waiting_repository: WaitingContextRepository,
    ):
        self.feishu_client = feishu_client
        self.session_repository = session_repository
        self.waiting_repository = waiting_repository
        self._current_session_key: Optional[str] = None

        # Create tool list
        self._tools = [
            create_simple_echo_tool(),
            ask_user_for_info(feishu_client, session_repository, waiting_repository),
            send_message(feishu_client),
            update_card(feishu_client),
        ]

    def set_current_session_key(self, session_key: str) -> None:
        """Set current session key"""
        self._current_session_key = session_key

    def get_tools(self) -> list:
        """
        Get all tools (for MCP server configuration)

        Returns:
            List of tool functions
        """
        # Return tool function list (for create_sdk_mcp_server)
        return [tool for tool in self._tools]

    def get_tool_by_name(self, name: str):
        """
        Get tool by name

        Returns:
            Tool function if found, None otherwise
        """
        for tool in self._tools:
            if tool.__name__ == name:
                return tool
        return None
