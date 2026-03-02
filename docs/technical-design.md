# 飞书 + Claude SDK 智能对话服务技术方案

> **项目名称**：Feishu-Claude-Intelligent-Bot
> **版本**：v2.0
> **日期**：2026-02-28
> **作者**：Claude

---

## 目录

1. [项目概述](#1-项目概述)
2. [技术栈选型](#2-技术栈选型)
3. [系统架构](#3-系统架构)
4. [核心设计](#4-核心设计)
5. [会话管理方案](#5-会话管理方案)
6. [Claude SDK集成](#6-claude-sdk集成)
7. [飞书集成](#7-飞书集成)
8. [数据库设计](#8-数据库设计)
9. [API设计](#9-api设计)
10. [安全设计](#10-安全设计)
11. [部署方案](#11-部署方案)
12. [实施路线图](#12-实施路线图)
13. [附录](#13-附录)

---

## 1. 项目概述

### 1.1 项目背景

构建一个基于飞书机器人的智能对话服务，通过Claude SDK处理用户需求，支持多轮对话、信息补充澄清、会话保持等功能。

### 1.2 核心需求

| 需求ID | 描述 | 优先级 |
|--------|------|--------|
| REQ-001 | 不同用户@机器人时创建新的会话 | P0 |
| REQ-002 | 同一用户不同需求时创建新会话 | P0 |
| REQ-003 | 同一需求的信息补充保持在同一会话 | P0 |
| REQ-004 | Claude可向用户询问补充信息 | P1 |
| REQ-005 | 用户可继续补充信息完成需求 | P1 |
| REQ-006 | 支持简单文本对话和复杂表单交互 | P1 |
| REQ-007 | 会话超时自动清理 | P2 |

### 1.3 方案选择

采用**混合交互方案**：
- **简单对话**：使用飞书消息回复链（Thread），保持自然聊天体验
- **复杂任务**：使用交互式卡片，结构化收集信息
- **会话标识**：结合 `root_id` + `card_id` 双重标识

### 1.4 重要设计说明

> ⚠️ **Claude SDK关键特性**：
>
> 1. **工具调用是同步的**：Claude调用工具后会立即返回结果，无法"等待"外部事件
> 2. **会话状态由应用层管理**：ClaudeSDKClient保持会话上下文，但"等待用户回复"的状态需要应用层自己维护
> 3. **Webhook需要异步处理**：飞书Webhook响应必须快速返回，Claude处理应在后台任务中执行
> 4. **receive_response()用于单次响应**：只接收当前query的响应，receive_messages()用于持续监听

---

## 2. 技术栈选型

### 2.1 技术选型表

| 组件 | 技术选择 | 版本 | 选型理由 |
|------|----------|------|----------|
| **Web框架** | FastAPI | 0.104+ | 异步支持优秀，自动API文档 |
| **飞书SDK** | lark-oapi | 最新 | 官方Python SDK，功能完整 |
| **Claude SDK** | claude-agent-sdk | v0.1.39+ | 官方SDK，支持多轮对话 |
| **数据库** | PostgreSQL | 15+ | 支持JSONB，关系数据与文档数据并存 |
| **缓存** | Redis | 7+ | 会话缓存、消息队列 |
| **任务队列** | asyncio.create_task | 内置 | 简单的后台任务处理 |
| **ORM** | SQLAlchemy | 2+ | 成熟的ORM框架 |
| **验证** | Pydantic | 2+ | 数据验证与序列化 |
| **日志** | structlog | 23+ | 结构化日志 |
| **监控** | Prometheus | 最新 | 指标收集 |
| **容器** | Docker | 24+ | 容器化部署 |
| **编排** | Docker Compose | 2+ | 开发环境编排 |

### 2.2 依赖清单

```txt
# Web框架
fastapi==0.104.1
uvicorn[standard]==0.24.0
pydantic==2.5.0
pydantic-settings==2.1.0

# 飞书SDK
lark-oapi==1.2.20

# Claude SDK
claude-agent-sdk==0.1.39

# 数据库
sqlalchemy==2.0.23
asyncpg==0.29.0
alembic==1.12.1
redis==5.0.1

# 工具库
structlog==23.2.0
prometheus-client==0.19.0
```

---

## 3. 系统架构

### 3.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                         飞书开放平台                                 │
│  ┌─────────────┐ 用户消息  ┌─────────────┐                           │
│  │   飞书客户端 │──────────>│ 飞书服务器  │                           │
│  └─────────────┘           └─────────────┘                           │
│         │                          │ Webhook (HTTPS)                  │
│         │                          ▼                                  │
│         │                  ┌─────────────────┐                         │
│         │                  │   Nginx反向代理  │                         │
│         │                  └─────────────────┘                         │
│         │                          │                                  │
│         │                          ▼                                  │
│         │                  ┌─────────────────┐                         │
│         │                  │   FastAPI应用    │                         │
│         │                  │                 │                         │
│         │                  │ ┌─────────────┐ │                         │
│         │                  │ │ API路由层    │ │                         │
│         │                  │ └─────────────┘ │                         │
│         │                  │        ↓        │                         │
│         │                  │ ┌─────────────┐ │                         │
│         │                  │ │ 消息分发器    │ │                         │
│         │                  │ └─────────────┘ │                         │
│         │                  │        ↓        │                         │
│         │                  │ ┌─────────────┐ │                         │
│         │                  │ │ 会话管理器    │ │                         │
│         │                  │ └─────────────┘ │                         │
│         │                  └─────────────────┘                         │
│         │         立即返回200 OK      │                          │
│         │                  │                          │                  │
│         │                  ▼                          │                  │
│         │          ┌─────────────────┐                 │                  │
│         │          │  后台任务处理   │ ◄──────────────────┤                  │
│         │          └─────────────────┘                  │                  │
│         │                  │                          │                  │
│         │                  ▼                          │                  │
│         │          ┌─────────────────┐                 │                  │
│         │          │  Claude SDK层    │                 │                  │
│         │          │(ClaudeSDKClient)│                 │                  │
│         │          └─────────────────┘                 │                  │
│         │                  │                          │                  │
│         │         query()                          │                  │
│         │                  │                          │                  │
│         │                  ▼                          │                  │
│         │    receive_response()                    │                  │
│         │                  │                          │                  │
│         │         工具调用                          │                  │
│         │         ask_user_for_info()                │                  │
│         │                  │                          │                  │
│         │   立即返回结果                         │                  │
│         │                  │                          │                  │
│         │                  ▼                          │                  │
│         │    发送问题给用户                       │                  │
│         │         记录等待状态                     │                  │
│         │                  │                          │                  │
│         │                  ▼                          │                  │
│         │    ┌─────────────────┐                 │                  │
│         │    │   持久化层       │                 │                  │
│         │    │ ┌─────────────┐ │                 │                  │
│         │    │ │ PostgreSQL  │ │                 │                  │
│         │    │ └─────────────┘ │                 │                  │
│         │    │ ┌─────────────┐ │                 │                  │
│         │    │ │   Redis     │ │                 │                  │
│         │    │ └─────────────┘ │                 │                  │
│         │    └─────────────────┘                 │                  │
│         │                                          │                  │
│         └──────────────────────────────────────────────────┘                  │
│                            │ 回复消息                                   │
│                            ▼                                           │
│                    ┌─────────────┐                                    │
│                    │   飞书用户   │                                    │
│                    └─────────────┘                                    │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.2 消息处理时序图

```
用户      飞书服务器      Web服务      后台任务      Claude SDK      数据库
 │            │              │              │              │              │
 │ @机器人    │              │              │              │              │
 │───────────>│              │              │              │              │
 │            │ Webhook       │              │              │              │
 │            │─────────────>│              │              │              │
 │            │              │              │              │              │
 │            │              │ 立即200 OK    │              │              │
 │            │<─────────────│              │              │              │
 │            │              │              │              │              │
 │            │              │ 后台处理开始 │              │              │
 │            │              │─────────────>│              │              │
 │            │              │              │ 获取会话     │              │
 │            │              │              │─────────────>│              │
 │            │              │              │<─────────────│              │
 │            │              │              │              │              │
 │            │              │              │ query()      │              │
 │            │              │              │─────────────>│              │
 │            │              │              │              │              │
 │            │              │              │<─────────────│ 工具调用     │
 │            │              │              │              │              │
 │            │              │              │              │─────────────>│ 记录等待     │
 │            │              │              │              │<─────────────│
 │            │              │              │              │              │
 │            │              │              │              │─────────────>│ 发送问题给用户│
 │            │              │              │<─────────────│              │
 │            │              │              │              │              │
 │            │ 发送消息    │              │              │              │
 │            │<─────────────│              │              │              │
 │            │             (完成处理)     │              │              │
 │ 收到问题    │              │              │              │              │
 │<───────────│              │              │              │              │
 │            │              │              │              │              │
 │ 用户回复    │              │              │              │              │
 │───────────>│              │              │              │              │
 │            │ Webhook       │              │              │              │
 │            │─────────────>│              │              │              │
 │            │              │              │              │              │
 │            │              │ 立即200 OK    │              │              │
 │            │<─────────────│              │              │              │
 │            │              │              │              │              │
 │            │              │ 后台处理开始 │              │              │
 │            │              │─────────────>│              │              │
 │            │              │              │ 获取等待上下文│              │
 │            │              │─────────────>│─────────────>│              │
 │            │              │<─────────────│<─────────────│              │
 │            │              │              │              │              │
 │            │              │ 构建上下文query│              │              │
 │            │              │─────────────>│─────────────>│              │
 │            │              │              │<─────────────│ 继续处理     │
 │            │              │              │              │─────────────>│
 │            │              │              │              │<─────────────│
 │            │              │              │              │              │
 │            │              │              │              │─────────────>│ 最终结果     │
 │            │              │              │              │<─────────────│
 │            │              │              │              │              │
 │            │              │              │              │─────────────>│ 保存会话     │
 │            │              │              │              │<─────────────│
 │            │              │              │              │              │
 │            │ 发送最终结果  │              │              │              │
 │            │<─────────────│              │              │              │
 │ 收到结果    │              │              │              │              │
 │<───────────│              │              │              │              │
```

### 3.3 交互流程说明

```
┌─────────────────────────────────────────────────────────────────┐
│                   消息处理流程                             │
│                                                          │
│  1. 用户发送消息                                           │
│     ↓                                                      │
│  2. 飞书Webhook → FastAPI                                  │
│     ↓ (立即返回200 OK)                                      │
│  3. 后台任务开始处理                                        │
│     ↓                                                      │
│  4. 获取/创建会话 (SessionManager)                           │
│     ↓                                                      │
│  5. 检查是否有等待上下文                                      │
│     ├─ 有等待上下文 → 构建带上下文的query                       │
│     └─ 无等待上下文 → 直接使用用户消息                     │
│     ↓                                                      │
│  6. 发送给Claude (client.query())                            │
│     ↓                                                      │
│  7. 接收响应 (receive_response())                             │
│     ↓                                                      │
│  8. 处理AssistantMessage                                    │
│     ├─ 文本 → 发送给用户                                       │
│     └─ 工具调用 → 执行工具                                   │
│         ↓                                                      │
│  9. 处理ask_user_for_info工具                              │
│     ├─ 发送问题给用户                                         │
│     ├─ 记录等待上下文到数据库                                   │
│     └─ 返回结果给Claude                                      │
│         ↓                                                      │
│ 10. Claude继续执行并返回ResultMessage                         │
│     ↓                                                      │
│ 11. 会话状态保持 (不自动完成)                               │
│         ↓                                                  │
│ 12. 等待用户回复...                                         │
│                                                          │
│  用户回复后：                                                 │
│     ↓                                                      │
│ 13. 检测到等待上下文                                         │
│     ↓                                                      │
│ 14. 构建上下文query:                                        │
│     "之前问了X，用户回复Y，请继续处理..."                     │
│     ↓                                                      │
│ 15. 发送给Claude继续处理                                      │
│     ↓                                                      │
│ 16. 完成需求                                               │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. 核心设计

### 4.1 设计原则

1. **单一职责**：每个模块只负责一个核心功能
2. **松耦合**：模块间通过接口通信，降低依赖
3. **可扩展**：支持插件化添加新功能
4. **可观测**：完善的日志、监控和追踪
5. **容错性**：优雅的错误处理和重试机制

### 4.2 核心模块

```
src/
├── main.py                    # 应用入口
├── config/                    # 配置管理
│   ├── __init__.py
│   ├── settings.py           # 配置类
│   └── constants.py          # 常量定义
├── api/                       # API层
│   ├── __init__.py
│   ├── router.py             # 路由注册
│   └── v1/
│       ├── __init__.py
│       ├── webhook.py        # Webhook API
│       ├── sessions.py       # 会话管理API
│       └── health.py         # 健康检查API
├── core/                      # 核心业务层
│   ├── __init__.py
│   ├── dispatcher.py         # 消息分发器
│   ├── session_manager.py   # 会话管理器
│   ├── context.py            # 上下文管理
│   └── handlers/             # 处理器
│       ├── __init__.py
│       ├── message_handler.py    # 消息处理器
│       ├── card_handler.py       # 卡片处理器
│       └── claude_handler.py     # Claude处理器
├── claude/                    # Claude SDK集成
│   ├── __init__.py
│   ├── factory.py            # 会话工厂
│   ├── tools.py              # 工具定义
│   └── client.py             # 客户端封装
├── feishu/                    # 飞书集成
│   ├── __init__.py
│   ├── client.py             # 飞书客户端
│   ├── card_builder.py       # 卡片构建器
│   ├── verifier.py           # 签名验证
│   └── models.py             # 数据模型
├── models/                    # 数据模型
│   ├── __init__.py
│   ├── session.py            # 会话模型
│   ├── message.py            # 消息模型
│   └── card.py               # 卡片模型
├── storage/                   # 存储层
│   ├── __init__.py
│   ├── database.py           # 数据库连接
│   ├── redis_client.py       # Redis客户端
│   └── repository.py         # 数据仓库
├── utils/                     # 工具函数
│   ├── __init__.py
│   ├── logger.py             # 日志工具
│   └── helpers.py            # 辅助函数
└── tests/                     # 测试
    ├── __init__.py
    ├── conftest.py
    ├── test_dispatcher.py
    └── test_session_manager.py
```

---

## 5. 会话管理方案

### 5.1 会话标识设计

```python
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum
import uuid

class SessionType(Enum):
    """会话类型"""
    THREAD = "thread"      # 回复链模式（简单对话）
    CARD = "card"          # 卡片模式（复杂任务）
    HYBRID = "hybrid"      # 混合模式

@dataclass
class SessionKey:
    """会话唯一标识（应用层）"""
    user_id: str           # 飞书用户ID: "ou_xxx"
    root_id: str           # 回复链根消息ID
    session_id: str = field(default_factory=lambda: uuid.uuid4().hex)  # 应用层会话ID
    card_id: Optional[str] = None  # 卡片ID（卡片模式）

    @property
    def key(self) -> str:
        """唯一键（应用层）"""
        if self.card_id:
            return f"{self.user_id}:{self.root_id}:{self.card_id}"
        return f"{self.user_id}:{self.root_id}"

    @property
    def cache_key(self) -> str:
        """缓存键"""
        return f"session:{self.key}"
```

### 5.2 等待上下文管理

```python
from dataclasses import dataclass
from datetime import datetime

@dataclass
class WaitingContext:
    """等待用户回复的上下文"""
    pending_question: str           # Claude提出的问题
    conversation_summary: str        # 对话摘要
    created_at: datetime           # 创建时间
    expires_at: Optional[datetime] = None  # 过期时间
    additional_data: dict = None    # 额外数据（如表单字段）
```

### 5.3 会话状态机

```
                    ┌─────────────────┐
                    │    CREATED       │
                    │   (已创建)       │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │     ACTIVE       │
                    │    (活跃中)      │◄─────────────────────────┐
                    └────────┬────────┘                          │
                             │                                   │
              ┌──────────────┼──────────────┐                   │
              │              │              │                   │
    ┌─────────▼────────┐     │     ┌────────▼────────┐          │
    │  WAITING_FOR_USER│     │     │  PROCESSING     │          │
    │   (等待用户回复) │     │     │   (Claude处理中)  │          │
    └─────────┬────────┘     │     └────────┬────────┘          │
              │              │              │                    │
              │ 用户回复      │              │ 需要补充信息         │
              │              │              │                    │
              └──────────────┼──────────────┘                    │
                             │                                    │
                    ┌────────▼────────┐                          │
                    │   PAUSED        │                          │
                    │  (已暂停/挂起)   │                          │
                    └─────────────────┘                          │
                                                             用户继续
                                                                 │
                                                                 ▼
                    ┌─────────────────┐              ┌─────────────────┐
                    │   COMPLETED     │──────────────│   ACTIVE        │
                    │    (已完成)      │  新任务继续   │    (活跃中)      │
                    └─────────────────┘              └─────────────────┘
                             │
                    ┌────────▼────────┐
                    │   EXPIRED       │
                    │   (已过期)       │
                    └─────────────────┘
```

### 5.4 新需求判断策略

```python
class DemandDetector:
    """需求检测器"""

    NEW_DEMAND_KEYWORDS = [
        "新需求", "新问题", "重新开始", "reset", "new",
        "下一个", "另外", "另一个", "另外一个问题"
    ]

    CONTEXT_SIMILARITY_THRESHOLD = 0.7
    TIME_GAP_THRESHOLD = 1800  # 30分钟

    async def is_new_demand(
        self,
        user_id: str,
        current_message: str,
        session_history: list
    ) -> tuple[bool, str]:
        """
        判断是否为新需求

        Returns:
            (is_new, reason): 是否为新需求及原因
        """

        # 1. 检查显式关键词
        for keyword in self.NEW_DEMAND_KEYWORDS:
            if keyword in current_message.lower():
                return True, f"检测到关键词: {keyword}"

        # 2. 检查是否有等待回复的会话（优先级最高）
        waiting_context = await self._get_waiting_context(user_id)
        if waiting_context:
            return False, f"有等待回复的会话: {waiting_context.pending_question}"

        # 3. 检查话题相似度（使用语义相似度）
        if session_history:
            similarity = await self._calculate_similarity(
                current_message,
                session_history[-1].content
            )
            if similarity < self.CONTEXT_SIMILARITY_THRESHOLD:
                return True, f"话题相似度低: {similarity:.2f}"

        # 4. 检查时间间隔
        if session_history:
            time_gap = (datetime.now() - session_history[-1].created_at).seconds
            if time_gap > self.TIME_GAP_THRESHOLD:
                return True, f"时间间隔过长: {time_gap}秒"

        return False, "继续当前会话"

    async def _calculate_similarity(self, text1: str, text2: str) -> float:
        """计算文本相似度"""
        # 简单实现：可替换为BERT等语义模型
        words1 = set(text1.split())
        words2 = set(text2.split())

        if not words1 or not words2:
            return 0.0

        intersection = len(words1 & words2)
        union = len(words1 | words2)

        return intersection / union if union > 0 else 0.0

    async def _get_waiting_context(self, user_id: str) -> Optional["WaitingContext"]:
        """获取等待上下文"""
        # 从Redis/数据库获取
        pass
```

### 5.5 会话管理器

```python
from typing import Dict, Optional, List
from datetime import datetime, timedelta
import asyncio
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions

class SessionManager:
    """会话管理器"""

    def __init__(
        self,
        redis_client,
        claude_factory: "ClaudeSessionFactory",
        storage: "Storage"
    ):
        self.redis = redis_client
        self.claude_factory = claude_factory
        self.storage = storage
        self.demand_detector = DemandDetector()
        self.locks: Dict[str, asyncio.Lock] = {}

        # 会话缓存（内存）
        self._sessions: Dict[str, "ClaudeSession"] = {}

    async def get_or_create_session(
        self,
        user_id: str,
        message: dict
    ) -> tuple["ClaudeSession", bool]:
        """
        获取或创建会话

        Returns:
            (session, is_new): 会话对象和是否新创建
        """
        message_id = message.get("message_id")
        content = self._extract_text(message)
        root_id = message.get("root_id")

        # 1. 检查是否为卡片回调
        if message.get("card"):
            return await self._handle_card_callback(user_id, message)

        # 2. 检查是否为回复消息
        if root_id:
            return await self._handle_reply(user_id, root_id, message)

        # 3. 新消息，判断是新需求还是补充
        return await self._handle_new_message(user_id, message_id, content)

    async def _handle_new_message(
        self,
        user_id: str,
        message_id: str,
        content: str
    ) -> tuple["ClaudeSession", bool]:
        """处理新消息"""
        # 获取用户会话历史
        history = await self.storage.get_user_sessions(user_id)

        # 判断是否为新需求
        is_new, reason = await self.demand_detector.is_new_demand(
            user_id, content, history
        )

        if is_new:
            # 创建新会话
            session_key = SessionKey(
                user_id=user_id,
                root_id=message_id,
                session_id=uuid.uuid4().hex
            )
            session = await self._create_session(session_key, content)
            return session, True
        else:
            # 使用最近的会话
            recent_session = self._get_most_recent_session(history)
            if recent_session:
                await self._update_session(recent_session)
                return recent_session, False
            else:
                # 创建默认会话
                session_key = SessionKey(
                    user_id=user_id,
                    root_id=message_id,
                    session_id="default"
                )
                session = await self._create_session(session_key, content)
                return session, True

    async def _handle_reply(
        self,
        user_id: str,
        root_id: str,
        message: dict
    ) -> tuple["ClaudeSession", bool]:
        """处理回复消息"""
        session_key = SessionKey(user_id=user_id, root_id=root_id)

        # 获取现有会话
        session = await self._get_cached_session(session_key)
        if session:
            return session, False

        # 从数据库加载
        session = await self.storage.load_session(session_key)
        if session:
            await self._cache_session(session)
            return session, False

        # 创建新会话
        session = await self._create_session(session_key, message.get("content"))
        return session, True

    async def _handle_card_callback(
        self,
        user_id: str,
        message: dict
    ) -> tuple["ClaudeSession", bool]:
        """处理卡片回调"""
        card_id = message.get("card", {}).get("card_id")
        action = message.get("card", {}).get("action", {})

        # 通过card_id查找会话
        session = await self.storage.get_session_by_card_id(card_id)
        if session:
            return session, False

        raise ValueError(f"未找到卡片对应的会话: {card_id}")

    async def _create_session(
        self,
        session_key: SessionKey,
        initial_message: str
    ) -> "ClaudeSession":
        """创建新会话"""
        # 创建Claude客户端
        client = await self.claude_factory.create_session(session_key)

        # 创建会话对象
        session = ClaudeSession(
            session_key=session_key,
            client=client,
            state=SessionState.ACTIVE,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            metadata={}
        )

        # 保存会话
        await self.storage.save_session(session)
        await self._cache_session(session)

        return session

    async def set_waiting_context(
        self,
        session_key: SessionKey,
        pending_question: str,
        conversation_summary: str = "",
        additional_data: dict = None
    ) -> None:
        """设置等待上下文"""
        context = WaitingContext(
            pending_question=pending_question,
            conversation_summary=conversation_summary,
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=1),
            additional_data=additional_data or {}
        )

        # 保存到Redis（带过期时间）
        await self.redis.setex(
            f"waiting:{session_key.key}",
            3600,  # 1小时过期
            context.to_json()
        )

    async def get_waiting_context(
        self,
        session_key: SessionKey
    ) -> Optional[WaitingContext]:
        """获取等待上下文"""
        data = await self.redis.get(f"waiting:{session_key.key}")
        if data:
            return WaitingContext.from_json(data)
        return None

    async def clear_waiting_context(self, session_key: SessionKey) -> None:
        """清除等待上下文"""
        await self.redis.delete(f"waiting:{session_key.key}")

    async def _cache_session(self, session: "ClaudeSession") -> None:
        """缓存会话"""
        self._sessions[session.session_key.key] = session

        # Redis缓存
        await self.redis.setex(
            session.session_key.cache_key,
            3600,  # 1小时过期
            session.to_json()
        )

    async def _get_cached_session(
        self,
        session_key: SessionKey
    ) -> Optional["ClaudeSession"]:
        """获取缓存的会话"""
        # 内存缓存
        if session_key.key in self._sessions:
            return self._sessions[session_key.key]

        # Redis缓存
        data = await self.redis.get(session_key.cache_key)
        if data:
            session = ClaudeSession.from_json(data)
            self._sessions[session_key.key] = session
            return session

        return None

    def _extract_text(self, message: dict) -> str:
        """提取消息文本"""
        content = message.get("content", "{}")
        try:
            import json
            content_dict = json.loads(content)
            return content_dict.get("text", "")
        except:
            return ""

    def _get_most_recent_session(
        self,
        sessions: List["ClaudeSession"]
    ) -> Optional["ClaudeSession"]:
        """获取最近的会话"""
        if not sessions:
            return None

        # 按更新时间排序
        sorted_sessions = sorted(
            sessions,
            key=lambda s: s.updated_at,
            reverse=True
        )

        # 优先返回活跃会话
        for session in sorted_sessions:
            if session.state != SessionState.COMPLETED:
                return session

        return sorted_sessions[0]
```

---

## 6. Claude SDK集成

### 6.1 Claude会话工厂

```python
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions
from claude_agent_sdk.tools import create_sdk_mcp_server

class ClaudeSessionFactory:
    """Claude会话工厂"""

    def __init__(self, feishu_tools: "FeishuTools"):
        self.feishu_tools = feishu_tools
        self._mcp_server = None

    def get_mcp_server(self):
        """获取MCP服务器"""
        if self._mcp_server is None:
            from claude_agent_sdk import create_sdk_mcp_server

            tools = [
                self.feishu_tools.ask_user_tool,
                self.feishu_tools.send_message_tool,
                self.feishu_tools.update_card_tool
            ]

            self._mcp_server = create_sdk_mcp_server(
                name="feishu",
                version="1.0.0",
                tools=tools
            )

        return self._mcp_server

    async def create_session(
        self,
        session_key: SessionKey,
        system_prompt: Optional[str] = None
    ) -> ClaudeSDKClient:
        """创建Claude会话"""

        options = ClaudeAgentOptions(
            system_prompt=system_prompt or self._default_system_prompt(),
            permission_mode='acceptEdits',
            max_turns=50,
            continue_conversation=True,
            mcp_servers={"feishu": self.get_mcp_server()},
            allowed_tools=[
                "mcp__feishu__ask_user_for_info",
                "mcp__feishu__send_message",
                "mcp__feishu__update_card"
            ]
        )

        client = ClaudeSDKClient(options=options)
        await client.connect()

        return client

    def _default_system_prompt(self) -> str:
        """默认系统提示词"""
        return """你是一个通过飞书机器人提供服务的AI助手。

你的职责：
1. 帮助用户解决各种问题和需求
2. 如果信息不足，可以使用 ask_user_for_info 工具向用户询问
3. 一次只处理一个明确的需求
4. 当用户提出新需求时，会创建新的会话

可用工具：
- ask_user_for_info: 向用户询问补充信息（注意：调用后Claude会继续执行，不会等待用户回复）
- send_message: 向用户发送普通消息
- update_card: 更新交互卡片的状态和内容

注意事项：
- 工具调用是同步的，调用后会立即返回结果
- ask_user_for_info 调用后，应用会记录"等待状态"
- 用户回复后，系统会自动将之前的对话上下文和用户回复一起发送给你
- 保持回复简洁明了
- 完成需求后明确告知用户
"""
```

### 6.2 飞书工具定义

```python
from claude_agent_sdk import tool
from typing import Dict, Any

class FeishuTools:
    """飞书工具类"""

    def __init__(
        self,
        feishu_client: "FeishuClient",
        session_manager: "SessionManager"
    ):
        self.feishu_client = feishu_client
        self.session_manager = session_manager
        self._current_session: Optional["ClaudeSession"] = None

    def set_current_session(self, session: "ClaudeSession") -> None:
        """设置当前会话"""
        self._current_session = session

    @tool(
        name="ask_user_for_info",
        description="向用户询问更多信息以继续处理需求。调用后立即返回，Claude会继续执行。",
        input_schema={
            "question": str,
            "info_type": str  # text, form, card
        }
    )
    async def ask_user_for_info(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        向用户询问补充信息

        注意：此工具调用后立即返回，Claude会继续执行。
        系统会记录"等待状态"，当用户回复时会自动补充上下文。

        Args:
            question: 问题描述
            info_type: 信息收集类型
                - "text": 简单文本回复
                - "form": 表单收集
                - "card": 卡片交互
        """
        session = self._current_session
        if not session:
            return {
                "content": [{
                    "type": "text",
                    "text": "错误：未找到当前会话"
                }]
            }

        question = args["question"]
        info_type = args.get("info_type", "text")

        # 1. 记录等待上下文（关键！）
        await self.session_manager.set_waiting_context(
            session_key=session.session_key,
            pending_question=question,
            conversation_summary=self._get_conversation_summary(session),
            additional_data={"info_type": info_type}
        )

        # 2. 发送问题给用户
        if info_type == "text":
            await self.feishu_client.send_message(
                user_id=session.session_key.user_id,
                content=f"为了更好地帮你处理，请补充以下信息：\n\n{question}"
            )
        elif info_type == "form":
            # TODO: 发送表单卡片
            pass
        elif info_type == "card":
            # TODO: 更新卡片
            pass

        # 3. 返回结果（工具调用完成，Claude继续执行）
        return {
            "content": [{
                "type": "text",
                "text": f"已向用户提问：{question}。系统已记录等待上下文。"
            }]
        }

    @tool(
        name="send_message",
        description="向用户发送普通文本消息",
        input_schema={"content": str}
    )
    async def send_message(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """发送消息给用户"""
        session = self._current_session
        if not session:
            return {
                "content": [{
                    "type": "text",
                    "text": "错误：未找到当前会话"
                }]
            }

        content = args["content"]
        await self.feishu_client.send_message(
            user_id=session.session_key.user_id,
            content=content
        )

        return {
            "content": [{
                "type": "text",
                "text": f"消息已发送：{content}"
            }]
        }

    @tool(
        name="update_card",
        description="更新交互卡片的状态和内容",
        input_schema={"status": str, "content": str}
    )
    async def update_card(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """更新卡片"""
        session = self._current_session
        if not session or not session.session_key.card_id:
            return {
                "content": [{
                    "type": "text",
                    "text": "错误：未找到卡片会话"
                }]
            }

        # TODO: 更新卡片
        return {
            "content": [{
                "type": "text",
                "text": "卡片已更新"
            }]
        }

    def _get_conversation_summary(self, session: "ClaudeSession") -> str:
        """获取对话摘要"""
        # TODO: 实现对话摘要逻辑
        return f"当前任务：{session.metadata.get('task', '')}"
```

### 6.3 Claude处理器

```python
from claude_agent_sdk import Message, AssistantMessage, ResultMessage
from typing import Optional

class ClaudeHandler:
    """Claude处理器"""

    def __init__(
        self,
        session_manager: "SessionManager",
        feishu_client: "FeishuClient",
        feishu_tools: "FeishuTools"
    ):
        self.session_manager = session_manager
        self.feishu_client = feishu_client
        self.feishu_tools = feishu_tools

    async def process_message(
        self,
        session: "ClaudeSession",
        user_message: str
    ) -> None:
        """处理用户消息"""
        # 设置当前会话
        self.feishu_tools.set_current_session(session)

        # 构建查询内容（检查是否有等待上下文）
        query_content = await self._build_query_content(session, user_message)

        # 发送给Claude
        await session.client.query(query_content)

        # 接收响应
        await self._receive_and_handle_response(session)

    async def _build_query_content(self, session, user_message: str) -> str:
        """构建查询内容（添加必要的上下文）"""

        # 检查是否有等待上下文
        waiting_context = await self.session_manager.get_waiting_context(
            session.session_key
        )

        if waiting_context:
            # 有等待上下文，组合成连续对话
            query = f"""
            之前的对话：
            Claude: {waiting_context.pending_question}

            用户回复：{user_message}

            请根据用户的回复继续完成之前的任务。
            """

            # 清除等待上下文
            await self.session_manager.clear_waiting_context(session.session_key)

            return query.strip()

        # 普通消息，直接返回
        return user_message

    async def _receive_and_handle_response(self, session) -> None:
        """接收并处理Claude响应"""
        # 使用 receive_response() 接收单次响应
        async for message in session.client.receive_response():
            if isinstance(message, AssistantMessage):
                await self._handle_assistant_message(session, message)
            elif isinstance(message, ResultMessage):
                # 保存Claude session_id以便恢复
                if hasattr(message, 'session_id'):
                    session.claude_session_id = message.session_id
                    await self.storage.save_session(session)

    async def _handle_assistant_message(
        self,
        session,
        message: AssistantMessage
    ) -> None:
        """处理助手消息"""
        user_id = session.session_key.user_id

        # 检查消息内容
        for content in message.content:
            # 文本内容
            if hasattr(content, 'text'):
                await self.feishu_client.send_message(
                    user_id=user_id,
                    content=content.text
                )

            # 工具调用（已在工具内部处理，这里只需记录）
            if hasattr(content, 'name'):
                # 工具调用会自动处理
                pass
```

---

## 7. 飞书集成

### 7.1 飞书客户端

```python
from lark_oapi.api.im.v1 import SendMessageRequest, SendMessageRequestBody
from lark_oapi.api.card.v1 import UpdateCardRequest
from typing import Optional
import json

class FeishuClient:
    """飞书客户端"""

    def __init__(self, app_id: str, app_secret: str):
        self.client = lark_oapi.Client.builder() \
            .app_id(app_id) \
            .app_secret(app_secret) \
            .build()

    async def send_message(
        self,
        user_id: str,
        content: str,
        message_type: str = "text"
    ) -> dict:
        """发送消息"""
        request = SendMessageRequest.builder() \
            .receive_id_type("user_id") \
            .request_body(SendMessageRequestBody.builder()
                .receive_id(user_id)
                .msg_type(message_type)
                .content(json.dumps({"text": content}))
                .build()) \
            .build()

        response = await self.client.im.v1.message.send(request)

        if not response.success():
            raise Exception(f"发送消息失败: {response.code} {response.msg}")

        return response.data

    async def send_card(
        self,
        user_id: str,
        card: dict,
        root_id: Optional[str] = None
    ) -> dict:
        """发送卡片"""
        request = SendMessageRequest.builder() \
            .receive_id_type("user_id") \
            .request_body(SendMessageRequestBody.builder()
                .receive_id(user_id)
                .msg_type("interactive")
                .content(json.dumps(card))
                .root_id(root_id)
                .build()) \
            .build()

        response = await self.client.im.v1.message.send(request)

        if not response.success():
            raise Exception(f"发送卡片失败: {response.code} {response.msg}")

        return response.data

    async def update_card(
        self,
        token: str,
        card: dict
    ) -> dict:
        """更新卡片"""
        request = UpdateCardRequest.builder() \
            .token(token) \
            .card(card) \
            .build()

        response = await self.client.card.v1.update.update(request)

        if not response.success():
            raise Exception(f"更新卡片失败: {response.code} {response.msg}")

        return response.data
```

### 7.2 Webhook处理器（异步处理）

```python
from fastapi import Request, HTTPException
import hmac
import hashlib
import base64
import json
import asyncio

class FeishuWebhookHandler:
    """飞书Webhook处理器"""

    def __init__(
        self,
        app_secret: str,
        session_manager: "SessionManager",
        dispatcher: "MessageDispatcher"
    ):
        self.app_secret = app_secret
        self.session_manager = session_manager
        self.dispatcher = dispatcher

    async def handle(self, request: Request) -> dict:
        """处理Webhook请求"""

        # 1. 验证签名
        if not await self._verify_request(request):
            raise HTTPException(status_code=403, detail="签名验证失败")

        # 2. 解析事件
        event_data = await request.json()

        # 3. 处理URL验证请求（立即返回）
        if "challenge" in event_data:
            return {"challenge": event_data["challenge"]}

        # 4. 异步处理事件（立即返回200 OK）
        asyncio.create_task(self._process_event(event_data))

        # 5. 立即返回成功响应
        return {"msg": "ok"}

    async def _verify_request(self, request: Request) -> bool:
        """验证请求签名"""
        timestamp = request.headers.get("X-Lark-Request-Timestamp")
        nonce = request.headers.get("X-Lark-Request-Nonce")
        body = await request.body()
        signature = request.headers.get("X-Lark-Signature")

        if not all([timestamp, nonce, body, signature]):
            return False

        # 构建签名字符串
        sign_str = f"{timestamp}\n{nonce}\n{body.decode('utf-8')}"

        # 计算签名
        secret_decoded = base64.b64decode(self.app_secret)
        sign_bytes = hmac.new(
            secret_decoded,
            sign_str.encode('utf-8'),
            digestmod=hashlib.sha256
        ).digest()
        expected_signature = base64.b64encode(sign_bytes).decode()

        # 恒时比较
        return hmac.compare_digest(signature, expected_signature)

    async def _process_event(self, event_data: dict) -> None:
        """处理事件（后台任务）"""
        try:
            event_type = event_data.get("header", {}).get("event_type")

            if event_type == "im.message.receive_v1":
                await self._handle_message_event(event_data)

            elif event_type == "card.action.trigger":
                await self._handle_card_action(event_data)

        except Exception as e:
            logger.error(f"处理事件失败: {e}", exc_info=True)

    async def _handle_message_event(self, event_data: dict) -> None:
        """处理消息事件"""
        event = event_data.get("event", {})
        message = event.get("message", {})

        # 提取关键信息
        user_id = message.get("sender", {}).get("sender_id", {}).get("user_id")
        message_id = message.get("message_id")
        content = json.loads(message.get("content", "{}"))
        text = content.get("text", "")

        # 去除@mention
        clean_text = self._remove_mention(text)

        if not user_id or not clean_text:
            return

        # 分发处理（已在后台任务中）
        await self.dispatcher.dispatch(
            user_id=user_id,
            message_id=message_id,
            content=clean_text,
            message=message
        )

    async def _handle_card_action(self, event_data: dict) -> None:
        """处理卡片交互事件"""
        event = event_data.get("event", {})
        action = event.get("action", {})

        user_id = event.get("operator", {}).get("user_id")
        token = event.get("token")  # card_id
        action_tag = action.get("action_tag")
        form_values = action.get("form_values", {})

        await self.dispatcher.dispatch_card_action(
            user_id=user_id,
            card_id=token,
            action_tag=action_tag,
            form_values=form_values
        )

    def _remove_mention(self, text: str) -> str:
        """移除@mention"""
        import re
        text = re.sub(r'<at[^>]*>', '', text)
        text = re.sub(r'</at>', '', text)
        return text.strip()
```

---

## 8. 数据库设计

### 8.1 数据表设计

```sql
-- 会话表
CREATE TABLE sessions (
    id BIGSERIAL PRIMARY KEY,
    session_key VARCHAR(255) UNIQUE NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    root_id VARCHAR(255) NOT NULL,
    card_id VARCHAR(255),
    state VARCHAR(50) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP,
    metadata JSONB DEFAULT '{}',
    claude_session_id VARCHAR(255),  -- Claude内部会话ID

    INDEX idx_user_id (user_id),
    INDEX idx_root_id (root_id),
    INDEX idx_state (state),
    INDEX idx_created_at (created_at)
);

-- 消息记录表
CREATE TABLE messages (
    id BIGSERIAL PRIMARY KEY,
    session_key VARCHAR(255) NOT NULL,
    message_id VARCHAR(255) UNIQUE NOT NULL,
    parent_id VARCHAR(255),
    message_type VARCHAR(50) NOT NULL,
    direction VARCHAR(20) NOT NULL, -- 'user' or 'bot'
    content TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),

    INDEX idx_session_key (session_key),
    INDEX idx_parent_id (parent_id),
    INDEX idx_created_at (created_at),

    FOREIGN KEY (session_key) REFERENCES sessions(session_key)
);

-- 卡片记录表
CREATE TABLE cards (
    id BIGSERIAL PRIMARY KEY,
    card_id VARCHAR(255) UNIQUE NOT NULL,
    session_key VARCHAR(255) NOT NULL,
    card_data JSONB NOT NULL,
    status VARCHAR(50) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),

    INDEX idx_card_id (card_id),
    INDEX idx_session_key (session_key),

    FOREIGN KEY (session_key) REFERENCES sessions(session_key)
);

-- 用户表
CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    user_id VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255),
    avatar_url TEXT,
    first_seen_at TIMESTAMP NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMP NOT NULL DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);
```

### 8.2 数据模型（SQLAlchemy）

```python
from sqlalchemy import Column, BigInteger, String, DateTime, Text, JSON, Enum, Index, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import enum

Base = declarative_base()

class SessionState(enum.Enum):
    """会话状态"""
    CREATED = "created"
    ACTIVE = "active"
    WAITING_FOR_USER = "waiting_for_user"
    PAUSED = "paused"
    COMPLETED = "completed"
    EXPIRED = "expired"

class MessageDirection(enum.Enum):
    """消息方向"""
    USER = "user"
    BOT = "bot"

class Session(Base):
    """会话模型"""
    __tablename__ = "sessions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    session_key = Column(String(255), unique=True, nullable=False, index=True)
    user_id = Column(String(255), nullable=False, index=True)
    root_id = Column(String(255), nullable=False, index=True)
    card_id = Column(String(255))
    state = Column(Enum(SessionState), nullable=False, index=True, default=SessionState.ACTIVE)
    created_at = Column(DateTime, nullable=False, default=datetime.now, index=True)
    updated_at = Column(DateTime, nullable=False, default=datetime.now)
    expires_at = Column(DateTime)
    metadata = Column(JSON, default={})
    claude_session_id = Column(String(255))  # Claude内部会话ID

    messages = relationship("Message", back_populates="session")
    card = relationship("Card", back_populates="session", uselist=False)

class Message(Base):
    """消息模型"""
    __tablename__ = "messages"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    session_key = Column(String(255), nullable=False, index=True)
    message_id = Column(String(255), unique=True, nullable=False)
    parent_id = Column(String(255), index=True)
    message_type = Column(String(50), nullable=False)
    direction = Column(Enum(MessageDirection), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.now, index=True)

    session = relationship("Session", back_populates="messages")

class Card(Base):
    """卡片模型"""
    __tablename__ = "cards"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    card_id = Column(String(255), unique=True, nullable=False, index=True)
    session_key = Column(String(255), nullable=False, index=True)
    card_data = Column(JSON, nullable=False)
    status = Column(String(50), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    updated_at = Column(DateTime, nullable=False, default=datetime.now)

    session = relationship("Session", back_populates="card")

class User(Base):
    """用户模型"""
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(String(255), unique=True, nullable=False)
    name = Column(String(255))
    avatar_url = Column(Text)
    first_seen_at = Column(DateTime, nullable=False, default=datetime.now)
    last_seen_at = Column(DateTime, nullable=False, default=datetime.now)
    metadata = Column(JSON, default={})
```

---

## 9. API设计

### 9.1 API路由

```
/api/v1/
├── /feishu/webhook        # 飞书Webhook
├── /sessions              # 会话管理
│   ├── GET    /           # 获取用户会话列表
│   ├── GET    /{key}      # 获取指定会话
│   ├── POST   /           # 创建新会话
│   └── DELETE /{key}      # 删除会话
└── /health                # 健康检查
```

---

## 10. 安全设计

### 10.1 签名验证

```python
import hmac
import hashlib
import base64

class SignatureVerifier:
    """签名验证器"""

    def __init__(self, app_secret: str):
        self.app_secret = base64.b64decode(app_secret)

    def verify(
        self,
        timestamp: str,
        nonce: str,
        body: bytes,
        signature: str
    ) -> bool:
        """
        验证飞书请求签名

        Args:
            timestamp: 请求时间戳
            nonce: 随机数
            body: 请求体
            signature: 签名值

        Returns:
            是否验证通过
        """
        # 构建签名字符串
        sign_str = f"{timestamp}\n{nonce}\n{body.decode('utf-8')}"

        # 计算签名
        sign_bytes = hmac.new(
            self.app_secret,
            sign_str.encode('utf-8'),
            digestmod=hashlib.sha256
        ).digest()
        expected_signature = base64.b64encode(sign_bytes).decode()

        # 恒时比较（防止时序攻击）
        return hmac.compare_digest(signature, expected_signature)
```

---

## 11. 部署方案

### 11.1 Docker配置

```dockerfile
# Dockerfile
FROM python:3.10-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY src/ .

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

# 运行应用
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 11.2 Docker Compose

```yaml
version: '3.8'

services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://postgres:password@db:5432/feishu_claude
      - REDIS_URL=redis://redis:6379/0
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - FEISHU_APP_ID=${FEISHU_APP_ID}
      - FEISHU_APP_SECRET=${FEISHU_APP_SECRET}
    depends_on:
      - db
      - redis
    restart: unless-stopped

  db:
    image: postgres:15-alpine
    environment:
      - POSTGRES_DB=feishu_claude
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
```

---

## 12. 实施路线图

### 阶段1：基础实现（Week 1-2）

- [ ] 项目初始化（目录结构、依赖配置）
- [ ] 数据库表设计创建
- [ ] 飞书机器人配置和Webhook验证
- [ ] 基础消息接收和回复功能
- [ ] Claude SDK基础集成

### 阶段2：核心功能（Week 3-4）

- [ ] 会话管理器实现
- [ ] 新需求判断逻辑
- [ ] 回复链会话保持
- [ ] Claude多轮对话处理
- [ ] 消息持久化存储

### 阶段3：等待上下文管理（Week 5）

- [ ] 等待上下文数据结构
- [ ] set_waiting_context 实现
- [ ] get_waiting_context 实现
- [ ] 上下文自动清理

### 阶段4：卡片交互（Week 6）

- [ ] 卡片构建器实现
- [ ] 卡片发送和更新
- [ ] 卡片交互事件处理

### 阶段5：优化增强（Week 7-8）

- [ ] 缓存优化（Redis）
- [ ] 并发处理优化
- [ ] 错误处理和重试
- [ ] 日志和监控

### 阶段6：测试部署（Week 9-10）

- [ ] 单元测试
- [ ] 集成测试
- [ ] Docker化
- [ ] 生产环境部署

---

## 13. 附录

### 13.1 环境变量配置

```env
# 应用配置
APP_NAME=FeishuClaudeBot
APP_ENV=production
APP_PORT=8000

# 数据库配置
DATABASE_URL=postgresql://user:password@localhost:5432/feishu_claude

# Redis配置
REDIS_URL=redis://localhost:6379/0
REDIS_CACHE_TTL=3600

# Claude配置
ANTHROPIC_API_KEY=your_api_key_here
CLAUDE_MODEL=claude-3-5-sonnet-latest

# 飞书配置
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=xxx

# 安全配置
SECRET_KEY=your_secret_key_here
```

### 13.2 参考资料

- [Claude Agent SDK文档](https://github.com/anthropics/claude-agent-sdk-python)
- [飞书开放平台](https://open.feishu.cn/)
- [FastAPI文档](https://fastapi.tiangolo.com/)
- [SQLAlchemy文档](https://docs.sqlalchemy.org/)
- [Redis文档](https://redis.io/docs/)

### 13.3 术语表

| 术语 | 说明 |
|------|------|
| Session | 会话，指一次完整的对话过程 |
| SessionKey | 应用层会话标识（user_id + root_id）|
| Claude Session ID | Claude SDK内部的会话ID，用于断线重连 |
| WaitingContext | 等待用户回复的上下文信息 |
| Thread | 回复链，飞书的消息回复机制 |
| Card | 卡片，飞书的结构化消息组件 |
| Root ID | 根消息ID，标识回复链的起点 |
| receive_response() | 接收单次query的完整响应 |
| receive_messages() | 持续接收所有消息直到连接关闭 |

### 13.4 重要设计决策记录

| 决策 | 原因 |
|------|------|
| 使用后台任务处理Claude | Webhook响应必须快速返回，Claude处理是异步的 |
| 使用WaitingContext管理等待状态 | Claude工具是同步的，无法"等待"用户回复，状态需应用层管理 |
| 使用receive_response() | 只需要单次响应，不需要持续监听 |
| 不使用Celery | 对于后台任务处理，asyncio.create_task已足够 |

---

**文档版本**: v2.0
**更新日期**: 2026-02-28
**主要变更**:
- 修正工具调用处理逻辑（工具是同步的）
- 添加WaitingContext管理
- 修正Webhook处理为异步后台任务
- 明确receive_response()的使用
- 添加claude_session_id字段区分不同类型的会话ID
