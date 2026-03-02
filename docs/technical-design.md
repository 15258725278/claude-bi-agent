# 飞书 + Claude SDK 智能对话服务技术方案

> **项目名称**：Feishu-Claude-Intelligent-Bot
> **版本**：v1.0.0
> **日期**：2026-03-02
> **作者**：Claude

---

## 目录

1. [项目概述](#1-项目概述)
2. [技术栈选型](#2-技术栈选型)
3. [系统架构](#3-系统架构)
4. [核心设计](#4-核心设计)
5. [飞书集成](#5-飞书集成)
6. [数据库设计](#6-数据库设计)
7. [API设计](#7-api设计)
8. [安全设计](#8-安全设计)
9. [部署方案](#9-部署方案)

---

## 1. 项目概述

### 1.1 项目背景

构建一个基于飞书机器人的智能对话服务，通过 Claude SDK 处理用户需求，支持消息确认反馈和实时响应。

### 1.2 核心需求

| 需求ID | 描述 | 优先级 | 状态 |
|--------|------|--------|------|
| REQ-001 | 通过 WebSocket 长连接接收飞书消息 | P0 | ✅ 已实现 |
| REQ-002 | 收到消息后立即发送确认表情（👌） | P0 | ✅ 已实现 |
| REQ-003 | 后台异步处理 Claude 请求 | P0 | ✅ 已实现 |
| REQ-004 | 使用 open_id 代替 user_id 避免权限问题 | P0 | ✅ 已实现 |
| REQ-005 | 支持多用户并发 | P1 | ✅ 已实现 |
| REQ-006 | 完善的日志记录 | P1 | ✅ 已实现 |

### 1.3 已解决的关键问题

#### 问题1: 飞书 API 权限错误 (99991672)

**错误信息**:
```
Access denied. One of the following scopes is required: [contact:user.employee_id:readonly]
```

**根本原因**:
- 使用 `receive_id_type="user_id"` 发送消息
- `user_id` 是企业内部员工 ID，属于敏感信息
- 需要应用具有 `contact:user.employee_id:readonly` 权限

**解决方案**:
- 改用 `receive_id_type="open_id"`
- `open_id` 是应用内部 ID，不需要额外权限
- 从飞书事件中正确提取 `open_id`

**修改的文件**:
- `src/feishu/client.py`: receive_id_type 改为 "open_id"
- `src/feishu/long_connection_service.py`: 提取 open_id
- `src/api/v1/webhook.py`: 接收和传递 open_id
- `src/core/session_manager.py`: 使用 open_id 发送消息
- `src/main.py`: 处理 open_id

---

## 2. 技术栈选型

### 2.1 技术选型表

| 组件 | 技术选择 | 版本 | 选型理由 |
|------|----------|------|----------|
| **Web框架** | FastAPI | 0.104+ | 异步支持优秀，自动API文档 |
| **飞书SDK** | lark-oapi | 1.5.3 | 官方Python SDK，功能完整 |
| **飞书模式** | 长连接（WebSocket） | - | 实时消息推送，无需轮询 |
| **Claude SDK** | claude-agent-sdk | v0.1.39+ | 官方SDK，支持多轮对话 |
| **Claude模型** | glm-4.7 | - | 国内可用模型 |
| **数据库** | SQLite（内存/文件可选）| 3.44+ | 简单部署，事务支持 |
| **部署** | Docker | - | 容器化部署，环境隔离 |

---

## 3. 系统架构

### 3.1 整体架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         外部系统                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                │
│  ┌──────────┐      ┌──────────────┐      ┌──────────────┐   │
│  │  飞书用户   │◄────►│  长连接服务  │◄────►│  Claude SDK  │   │
│  └──────────┘      │  (Python）   │      │  (glm-4.7)  │   │
│                    │              └──────┬─────┘      │           │
│                    │                     │              │           │
│                    ▼                     ▼              └──┬───────┐│
│              ┌─────────────────────────┐           │         │
│              │   主服务（FastAPI）    │◄──────────┘         │
│              └─────────────┬───────────┘                   │
│                            │                              │
│                            ▼                              │
│                    ┌─────────────────────────┐              │
│                    │  SQLite / 内存存储    │              │
│                    └─────────────────────────┘              │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.2 服务组件

| 服务 | 功能 | 端口/协议 |
|------|------|-------------|
| 长连接服务 | 连接飞书 WebSocket，接收消息，转发到主服务 | 独立进程 |
| 主服务 | Webhook接收长连接消息，处理业务逻辑 | 8000/HTTP |
| 数据存储 | 会话管理，消息历史 | SQLite/内存 |

### 3.3 关键数据流

```
用户消息 → 飞书 → 长连接服务 → HTTP POST → 主服务 → 👌 确认表情
                    ↓
              主服务处理（后台任务）→ Claude SDK → 响应
                    ↓
              主服务解析响应 → 发送回复 → 飞书
```

---

## 4. 核心设计

### 4.1 消息确认机制

```python
# 收到消息后立即发送确认表情
async def dispatch(self, user_id: str, open_id: str, ...):
    # 立即发送确认表情（👌）
    try:
        await self.feishu_client.send_ack_emoji(user_id=open_id)
        logger.info(f"[SessionManager] 已发送确认表情")
    except Exception as e:
        logger.warning(f"[SessionManager] 发送确认表情失败: {e}")

    # 然后在后台处理 Claude 请求
    await claude_client.query(content)
    async for msg in claude_client.receive_response():
        # 处理响应...
```

### 4.2 open_id 代替 user_id

```python
# 飞书客户端使用 open_id 发送消息
class FeishuClient:
    async def send_message(self, user_id: str, content: str):
        """发送消息（使用 open_id 避免 user_id 权限问题）"""
        request = CreateMessageRequest.builder() \
            .receive_id_type("open_id")  # 使用 open_id
            .request_body(
                CreateMessageRequestBody.builder()
                .receive_id(user_id)
                .msg_type("text")
                .content(json.dumps({"text": content}))
                .build()
            ) \
            .build()
```

**为什么使用 open_id？**

| 参数 | 说明 | 权限要求 |
|------|------|----------|
| `user_id` | 员工 ID（企业内部） | 需要 `contact:user.employee_id:readonly` |
| `open_id` | 应用内部 ID（租户内唯一） | 不需要额外权限 |

---

## 5. 飞书集成

### 5.1 长连接服务

```python
# 使用 lark-oapi WebSocket 客户端
from lark_oapi.ws import Client as WsClient
from lark_oapi.event.dispatcher_handler import EventDispatcherHandler

# 创建 WebSocket 客户端
ws_client = WsClient(
    app_id=APP_ID,
    app_secret=APP_SECRET,
    event_handler=EventDispatcherHandler
        .builder(None, None)
        .register_p2_im_message_receive_v1(handle_message_event)
        .register_p2_card_action_trigger(handle_card_action_event)
        .build()
)

# 启动客户端
ws_client.start()  # 阻塞调用，建立 WebSocket 连接
```

### 5.2 飞书客户端

```python
class FeishuClient:
    """飞书客户端"""

    async def send_message(self, user_id: str, content: str):
        """发送消息（使用 open_id 避免 user_id 权限问题）"""
        request = CreateMessageRequest.builder() \
            .receive_id_type("open_id") \
            .request_body(
                CreateMessageRequestBody.builder()
                .receive_id(user_id)
                .msg_type("text")
                .content(json.dumps({"text": content}))
                .build()
            ) \
            .build()

        response = await self.client.im.v1.message.acreate(request)

        if not response.success():
            raise Exception(f"发送消息失败: {response.code} {response.msg}")

        return response.data

    async def send_ack_emoji(self, user_id: str) -> dict:
        """发送确认表情（表示正在处理）"""
        return await self.send_message(user_id=user_id, content="👌")
```

### 5.3 Webhook 处理器

```python
@router.post("/webhook/message")
async def receive_message_event(event: MessageEvent) -> dict:
    """
    接收来自长连接服务的消息事件

    新逻辑：立即返回"正在处理中"，然后在后台处理 Claude SDK
    """
    logger.info(f"收到消息事件: user_id={event.user_id}, content={event.content[:50]}")

    # 立即返回"正在处理中"，避免长连接超时
    # 创建后台任务处理实际业务逻辑
    task = asyncio.create_task(_process_message_async(event))

    return {"status": "processing", "message": "正在处理中，请稍候..."}
```

---

## 6. 数据库设计

### 6.1 数据表设计

```sql
-- 会话表
CREATE TABLE sessions (
    id BIGSERIAL PRIMARY KEY,
    session_key VARCHAR(255) UNIQUE NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    root_id VARCHAR(255),
    state VARCHAR(50) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP,
    claude_session_id VARCHAR(255),
    metadata JSONB DEFAULT '{}',
    INDEX idx_session_key (session_key),
    INDEX idx_user_id (user_id),
    INDEX idx_state (state)
);
```

---

## 7. API设计

### 7.1 Webhook 端点

```python
# 飞书事件接收（长连接服务调用）
@router.post("/webhook/message")
async def receive_message_event(event: MessageEvent) -> dict:
    """接收长连接转发的消息事件"""
    logger.info(f"收到消息事件: user_id={event.user_id}, open_id={event.open_id}")

    # 创建后台任务处理
    task = asyncio.create_task(_process_message_async(event))

    return {"status": "processing", "message": "正在处理中，请稍候..."}

@router.post("/webhook/card-action")
async def receive_card_action_event(event: CardActionEvent) -> dict:
    """接收长连接转发的卡片动作事件"""
    logger.info(f"收到卡片动作事件: user_id={event.user_id}, open_id={event.open_id}")

    # 创建后台任务处理
    task = asyncio.create_task(_process_card_action_async(event))

    return {"status": "ok"}
```

### 7.2 健康检查

```python
@router.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "ok", "service": "feishu-claude-bot"}
```

---

## 8. 安全设计

### 8.1 数据安全

1. **敏感信息保护**：
   - API 密钥存储在环境变量
   - 不在日志中输出完整密钥
   - 数据库连接字符串使用环境变量

2. **输入验证**：
   - 飞书消息长度限制
   - 消息格式验证
   - 卡片数据 JSON 验证

3. **访问控制**：
   - 每个用户独立的会话隔离
   - 会话过期自动清理

---

## 9. 部署方案

### 9.1 环境变量

```bash
# 飞书配置
FEISHU_APP_ID=cli_xxxxxxxxx
FEISHU_APP_SECRET=xxxxxxxxx

# 主服务 URL（长连接服务需要）
MAIN_SERVICE_URL=http://localhost:8000

# 运行模式
APP_ENV=production
```

### 9.2 启动方式

#### 方式一：手动启动

```bash
# 终端1 - 主服务
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --log-level info

# 终端2 - 长连接服务
python src/feishu/long_connection_service.py
```

#### 方式二：脚本启动

```bash
# 同时启动两个服务
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --log-level info &
python src/feishu/long_connection_service.py
```

---

## 附录

### A.1 已实现的文件清单

```
src/
├── main.py                    # 主应用入口，FastAPI 应用
├── api/v1/
│   └── webhook.py            # Webhook 端点（接收长连接消息）
├── core/
│   ├── session_manager.py     # 会话管理器
│   └── dispatcher.py         # 事件分发器
├── claude/
│   └── factory.py            # Claude 会话工厂
├── feishu/
│   ├── client.py             # 飞书客户端
│   └── long_connection_service.py  # 长连接服务（独立进程）
├── storage/
│   ├── redis_client.py       # Redis 客户端
│   └── repository.py       # 数据仓库
├── utils/
│   └── logger.py           # 日志工具
└── config/                  # 配置管理
```

### A.2 环境变量说明

| 变量名 | 说明 | 是否必需 | 默认值 |
|---------|------|---------|---------|
| `FEISHU_APP_ID` | 飞书应用 ID | 是 | - |
| `FEISHU_APP_SECRET` | 飞书应用密钥 | 是 | - |
| `MAIN_SERVICE_URL` | 主服务 URL | 否 | http://localhost:8000 |
| `APP_ENV` | 运行环境 | 否 | development |

### A.3 端口说明

| 服务 | 端口 | 说明 |
|------|------|------|
| 主服务 | 8000 | FastAPI HTTP 服务 |
| 飞书 WebSocket | - | 自动连接飞书服务 |

### A.4 已修复的问题

| 问题ID | 问题描述 | 解决方案 | 状态 |
|--------|---------|---------|------|
| BUG-001 | `'ClaudeSDKClient' object has no attribute 'send_message'` | 改用 `query()` 方法 | ✅ 已修复 |
| BUG-002 | `'ResultMessage' object has no attribute 'error'` | 移除错误检查代码 | ✅ 已修复 |
| BUG-003 | AssistantMessage.content 包含 TextBlock 对象 | 使用 `block.text` 提取文本 | ✅ 已修复 |
| BUG-004 | `create_message_request.builder()` 不存在 | 改用 `CreateMessageRequest.builder()` | ✅ 已修复 |
| BUG-005 | 权限错误 99991672 | 使用 `open_id` 代替 `user_id` | ✅ 已修复 |

### A.5 版本历史

| 版本 | 日期 | 变更内容 |
|------|------|---------|
| v1.0.0 | 2026-03-02 | 初始版本，实现基础飞书机器人功能 |
| v1.0.1 | 2026-03-02 | 修复权限错误，使用 open_id |
| v1.1.0 | 2026-03-02 | 添加消息确认表情功能 |
