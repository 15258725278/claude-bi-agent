"""
Claude 会话工厂 - 基于官方文档简化版
"""
import asyncio
import shutil
import os
from typing import Optional, Dict, Any
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions
from src.config import settings
from src.claude.prompts import get_default_system_prompt

# 查找本地 Claude Code CLI
LOCAL_CLAUDE_CLI = shutil.which('claude')

# 技能目录
SKILLS_DIR = "/root/.claude/skills"


class ClaudeSessionFactory:
    """Claude 会话工厂"""

    def __init__(self):
        """初始化工厂"""
        pass

    async def create_session(
        self,
        system_prompt: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> ClaudeSDKClient:
        """
        创建新的 Claude 会话

        Args:
            system_prompt: 系统提示词，None 则使用默认
            session_id: 恢复会话时使用的 Claude 内部会话 ID

        Returns:
            ClaudeSDKClient 实例
        """
        # 构建技能配置
        skills_config = self._get_skills_config()

        # 使用本地已配置的 Claude Code
        # 显式设置 cli_path 以避免使用 bundled CLI
        options = ClaudeAgentOptions(
            system_prompt=system_prompt or get_default_system_prompt(),
            permission_mode=settings.CLAUDE_PERMISSION_MODE,
            max_turns=settings.CLAUDE_MAX_TURNS,
            model=settings.CLAUDE_MODEL,
            cli_path=LOCAL_CLAUDE_CLI if LOCAL_CLAUDE_CLI else None,
            **skills_config
        )

        # 创建客户端
        client = ClaudeSDKClient(options=options)

        # 连接（不带初始消息）
        await client.connect()

        return client

    def _get_skills_config(self) -> Dict[str, Any]:
        """获取技能配置（MCP服务器格式）"""
        mcp_servers_config = {}

        # 检查技能目录是否存在
        if os.path.exists(SKILLS_DIR):
            # 业务背景知识技能
            business_skill = os.path.join(SKILLS_DIR, "业务背景知识")
            if os.path.exists(business_skill):
                mcp_servers_config["feishu"] = {"path": business_skill, "name": "业务背景知识"}

            # 数据仓库元数据技能
            warehouse_skill = os.path.join(SKILLS_DIR, "数据仓库元数据")
            if os.path.exists(warehouse_skill):
                # 数据仓库技能配置
                mcp_servers_config["warehouse"] = {"path": warehouse_skill, "name": "数据仓库元数据"}

        return {"mcp_servers": mcp_servers_config}

    async def resume_session(
        self,
        claude_session_id: str,
        system_prompt: Optional[str] = None
    ) -> ClaudeSDKClient:
        """
        恢复现有的 Claude 会话

        Args:
            claude_session_id: 之前保存的 Claude 内部会话 ID
            system_prompt: 系统提示词，None 则使用默认

        Returns:
            ClaudeSDKClient 实例
        """
        # 构建技能配置
        skills_config = self._get_skills_config()

        # 使用本地已配置的 Claude Code
        # 显式设置 cli_path 以避免使用 bundled CLI
        options = ClaudeAgentOptions(
            system_prompt=system_prompt or get_default_system_prompt(),
            permission_mode=settings.CLAUDE_PERMISSION_MODE,
            max_turns=settings.CLAUDE_MAX_TURNS,
            resume=claude_session_id,
            model=settings.CLAUDE_MODEL,
            cli_path=LOCAL_CLAUDE_CLI if LOCAL_CLAUDE_CLI else None,
            **skills_config
        )

        # 创建客户端并恢复会话
        client = ClaudeSDKClient(options=options)

        # 连接时不发送任何消息
        await client.connect()

        return client


class ClaudeSessionManager:
    """Claude 会话管理器 - 简化版

    管理多个并发的 Claude 会话实例
    """

    def __init__(self):
        """初始化管理器"""
        self._sessions: Dict[str, ClaudeSDKClient] = {}
        self._lock = asyncio.Lock()

    def _get_skills_config(self) -> Dict[str, Any]:
        """获取技能配置"""
        skills_config = {}

        # 检查技能目录是否存在
        if os.path.exists(SKILLS_DIR):
            # 业务背景知识技能
            business_skill = os.path.join(SKILLS_DIR, "业务背景知识")
            if os.path.exists(business_skill):
                skills_config["skills"] = [business_skill]

            # 数据仓库元数据技能
            warehouse_skill = os.path.join(SKILLS_DIR, "数据仓库元数据")
            if os.path.exists(warehouse_skill):
                # 如果已设置 skills，则追加
                if "skills" in skills_config:
                    skills_config["skills"].append(warehouse_skill)
                else:
                    skills_config["skills"] = [warehouse_skill]

        return skills_config

    async def get_or_create_session(
        self,
        session_key: str,
        resume_session_id: Optional[str] = None
    ) -> ClaudeSDKClient:
        """
        获取或创建会话

        Args:
            session_key: 会话键（user_id:root_id）
            resume_session_id: 恢复的会话 ID（可选）

        Returns:
            ClaudeSDKClient 实例
        """
        async with self._lock:
            # 如果会话已存在且未关闭，返回现有会话
            if session_key in self._sessions:
                return self._sessions[session_key]

            # 创建新会话
            client = await self._create_session(session_id=resume_session_id)

            self._sessions[session_key] = client
            return client

    async def _create_session(
        self,
        session_id: Optional[str] = None
    ) -> ClaudeSDKClient:
        """创建新会话"""
        # 构建技能配置
        skills_config = self._get_skills_config()

        # 使用本地已配置的 Claude Code
        # 显式设置 cli_path 以避免使用 bundled CLI
        options = ClaudeAgentOptions(
            system_prompt=get_default_system_prompt(),
            permission_mode=settings.CLAUDE_PERMISSION_MODE,
            max_turns=settings.CLAUDE_MAX_TURNS,
            resume=session_id,
            model=settings.CLAUDE_MODEL,
            cli_path=LOCAL_CLAUDE_CLI if LOCAL_CLAUDE_CLI else None,
            **skills_config
        )

        # 创建客户端
        client = ClaudeSDKClient(options=options)

        # 连接
        await client.connect()

        return client

    async def close_session(self, session_key: str) -> None:
        """关闭会话"""
        async with self._lock:
            if session_key in self._sessions:
                client = self._sessions.pop(session_key)
                try:
                    await client.disconnect()
                except Exception as e:
                    # 忽略关闭错误，会话已经被移除
                    pass

    async def close_all(self) -> None:
        """关闭所有会话"""
        async with self._lock:
            tasks = []
            for session_key, client in self._sessions.items():
                tasks.append(asyncio.create_task(client.disconnect()))
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            self._sessions.clear()

    async def get_session_info(self, session_key: str) -> Optional[dict]:
        """获取会话信息"""
        if session_key in self._sessions:
            client = self._sessions[session_key]
            if client:
                return {
                    "session_key": session_key,
                    "state": "active"
                }
        return None
