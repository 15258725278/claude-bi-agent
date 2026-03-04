# 飞书群聊功能技术设计文档

## 文档信息

| 项目 | 内容 |
|------|------|
| 文档版本 | v1.0 |
| 创建日期 | 2026-03-03 |
| 作者 | Claude Code |
| 项目版本 | 3.1.0 |

---

## 1. 需求概述

### 1.1 功能目标

在现有飞书机器人基础上，增加群聊支持能力，实现：

1. **普通问答模式**：在群聊中@机器人，直接回复用户问题
2. **需求管理模式**：在群聊中@机器人并提及"帮我处理需求"，触发需求卡片，创建独立话题
3. **会话隔离**：每个需求创建独立话题，不同需求间会话完全隔离
4. **上下文保持**：话题内的所有讨论自动聚合，保持完整上下文

### 1.2 关键词识别

| 触发关键词 | 模式 |
|-----------|------|
| "帮我处理需求" | 需求管理模式 |
| 其他消息 | 普通问答模式 |

---

## 2. 架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              飞书群聊功能架构                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                   │
│  │  飞书群聊     │───▶│  长连接服务   │───▶│  主服务      │                   │
│  │  (群消息)    │    │ (事件转发)   │    │ (FastAPI)    │                   │
│  └──────────────┘    └──────────────┘    └──────┬───────┘                   │
│                                                 │                            │
│                                                 ▼                            │
│                                    ┌─────────────────────────┐              │
│                                    │   消息路由层            │              │
│                                    │   (GroupChatRouter)    │              │
│                                    └───────────┬─────────────┘              │
│                                                │                            │
│              ┌─────────────────────────────────┼─────────────────────────┐ │
│              │                                 │                         │ │
│              ▼                                 ▼                         │ │
│    ┌─────────────────┐              ┌─────────────────┐                   │ │
│    │  普通问答模式    │              │  需求管理模式    │                   │ │
│    │  (直接回复)     │              │  (创建话题)     │                   │ │
│    └────────┬────────┘              └────────┬────────┘                   │ │
│             │                                 │                            │ │
│             ▼                                 ▼                            │ │
│    ┌─────────────────┐              ┌─────────────────┐                   │ │
│    │ ClaudeSession  │              │ DemandService   │                   │ │
│    │ (单次问答)      │              │ (需求管理)       │                   │ │
│    └─────────────────┘              └────────┬────────┘                   │ │
│                                               │                            │ │
│                                               ▼                            │ │
│                                   ┌─────────────────────────┐             │ │
│                                   │   数据层                │             │ │
│                                   │   ├─ DemandRepository  │             │ │
│                                   │   └─ SessionManager    │             │ │
│                                   └─────────────────────────┘             │ │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 模块职责

| 模块 | 职责 |
|------|------|
| GroupChatRouter | 消息路由，识别普通问答/需求管理模式 |
| DemandService | 需求管理服务，创建话题、卡片 |
| DemandRepository | 需求数据持久化 |
| ThreadService | 话题服务，创建话题、发送消息 |
| FeishuClient | 飞书API客户端，群聊消息发送 |

---

## 3. 数据模型设计

### 3.1 需求表 (DataRequirement)

```python
class DataRequirement(Base):
    """数据需求表"""
    __tablename__ = "data_requirements"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    requirement_id = Column(String(64), unique=True, nullable=False, index=True)
    title = Column(String(255), nullable=False)                    # 需求标题
    description = Column(Text, nullable=False)                      # 需求描述
    dimensions = Column(JSON)                                      # 分析维度
    time_range = Column(String(100))                               # 时间范围
    priority = Column(String(20), default="normal")                 # 优先级：low/normal/high/urgent

    # 群聊关联
    chat_id = Column(String(64), nullable=False, index=True)       # 群ID
    thread_id = Column(String(64), unique=True, nullable=False)    # 话题ID
    root_id = Column(String(64), nullable=False, index=True)       # 话题根消息ID

    # 卡片关联
    card_message_id = Column(String(64))                           # 需求卡片消息ID
    card_token = Column(String(64))                               # 卡片token（用于更新）

    # 状态管理
    status = Column(String(20), default="pending", index=True)    # 状态：pending/scope_confirmed/analyzing/waiting_feedback/completed/cancelled

    # 用户信息
    created_by = Column(String(64), nullable=False)                # 创建人user_id
    created_by_name = Column(String(100))                         # 创建人名称
    assigned_to = Column(String(64))                              # 指派人user_id

    # 时间信息
    created_at = Column(DateTime, default=datetime.now, index=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    completed_at = Column(DateTime)

    # 分析结果
    analysis_result = Column(JSON)                                # 分析结果
    feedback = Column(Text)                                       # 用户反馈

    # 元数据
    metadata = Column(JSON, default={})
```

### 3.2 会话表扩展 (Session)

新增字段：
```python
session_type = Column(String(20), default="p2p")    # 会话类型：p2p/group
chat_id = Column(String(64))                        # 群ID（群聊场景）
thread_id = Column(String(64))                      # 话题ID（话题场景）
requirement_id = Column(String(64))                 # 关联需求ID
```

### 3.3 话题消息表 (ThreadMessage)

```python
class ThreadMessage(Base):
    """话题消息表"""
    __tablename__ = "thread_messages"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    message_id = Column(String(64), unique=True, nullable=False)
    thread_id = Column(String(64), nullable=False, index=True)
    parent_id = Column(String(64))                          # 父消息ID
    root_id = Column(String(64), nullable=False)            # 根消息ID

    content = Column(Text, nullable=False)
    message_type = Column(String(20))                       # 消息类型：text/image/card
    sender_id = Column(String(64))
    sender_name = Column(String(100))

    created_at = Column(DateTime, default=datetime.now, index=True)
```

---

## 4. 接口设计

### 4.1 飞书API调用

#### 4.1.1 发送群聊消息

```python
async def send_group_message(
    chat_id: str,
    content: str,
    message_type: str = "text",
    root_id: Optional[str] = None,   # 话题根消息ID
) -> dict:
    """发送群聊消息"""
    request = CreateMessageRequest.builder() \
        .receive_id_type("chat_id") \
        .request_body(
            CreateMessageRequestBody.builder()
            .receive_id(chat_id)
            .msg_type(message_type)
            .content(json.dumps({"text": content}))
            .build()
        )

    if root_id:
        request.root_id(root_id)      # 发送到话题

    response = await self.client.im.v1.message.acreate(request)
    return response.data
```

#### 4.1.2 创建话题

```python
async def create_thread(
    chat_id: str,
    title: str,
    first_message: str,
) -> dict:
    """创建话题"""
    # 先发送第一条消息
    response = await self.send_group_message(
        chat_id=chat_id,
        content=first_message
    )

    # 返回消息ID作为根ID
    return {
        "root_id": response.message_id,
        "thread_id": response.message_id,  # 话题ID即为根消息ID
    }
```

#### 4.1.3 发送卡片到话题

```python
async def send_card_to_thread(
    chat_id: str,
    root_id: str,
    card: dict,
) -> dict:
    """发送卡片到话题"""
    request = CreateMessageRequest.builder() \
        .receive_id_type("chat_id") \
        .request_body(
            CreateMessageRequestBody.builder()
            .receive_id(chat_id)
            .msg_type("interactive")
            .content(json.dumps(card))
            .build()
        ) \
        .root_id(root_id)

    response = await self.client.im.v1.message.acreate(request)
    return response.data
```

### 4.2 内部API

#### 4.2.1 处理群聊消息

```python
@router.post("/group/message")
async def handle_group_message(event: GroupMessageEvent) -> dict:
    """处理群聊消息"""
    # 1. 检查是否@机器人
    if not event.mentions_bot:
        return {"status": "ignored"}

    # 2. 识别模式
    if "帮我处理需求" in event.content:
        # 需求管理模式
        return await handle_demand_mode(event)
    else:
        # 普通问答模式
        return await handle_qa_mode(event)
```

---

## 5. 业务流程

### 5.1 普通问答模式流程

```
┌─────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────┐
│ 用户在   │ @   │ 长连接服务   │     │ 主服务      │     │ 机器人   │
│ 群聊发言 │ ──▶│ (事件转发)   │ ──▶│ (消息处理)   │ ──▶│ (Claude) │
└─────────┘     └─────────────┘     └──────┬──────┘     └─────────┘
                                            │
                                            ▼
                                   ┌─────────────┐
                                   │ 创建临时会话 │
                                   └──────┬──────┘
                                            │
                                            ▼
                                   ┌─────────────┐
                                   │ 调用Claude  │
                                   └──────┬──────┘
                                            │
                                            ▼
                                   ┌─────────────┐
                                   │ 群内直接回复 │
                                   └─────────────┘
```

### 5.2 需求管理模式流程

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         需求管理完整流程                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  阶段1: 需求提交                                                          │
│  ┌─────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────┐    │
│  │ 用户@   │ "帮 │ 长连接服务   │     │ 主服务      │     │ 创建    │    │
│  │ 机器人  │ ──▶│ (事件转发)   │ ──▶│ (创建话题)   │ ──▶│ 话题    │    │
│  │ +关键词  │     │             │     │ +卡片       │     │ +卡片   │    │
│  └─────────┘     └─────────────┘     └─────────────┘     └─────────┘    │
│                                              │                             │
│                                              ▼                             │
│                                   ┌─────────────────────┐                │
│                                   │ 发送需求卡片到话题   │                │
│                                   │ 用户填写需求信息     │                │
│                                   └─────────────────────┘                │
│                                                                         │
│  阶段2: 口径确认                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐     │
│  │ 话题内讨论：@相关人员进行口径确认                                  │     │
│  └─────────────────────────────────────────────────────────────────┘     │
│                              │                                          │
│                              ▼                                          │
│                   ┌─────────────────────┐                             │
│                   │ 发送口径确认卡片      │                             │
│                   │ (确认/修改按钮)       │                             │
│                   └─────────────────────┘                             │
│                                                                         │
│  阶段3: 数据分析                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐     │
│  │ 用户点击"确认口径" -> 机器人开始分析                                │     │
│  └─────────────────────────────────────────────────────────────────┘     │
│                              │                                          │
│                              ▼                                          │
│                   ┌─────────────────────┐                             │
│                   │ 调用Claude分析数据   │                             │
│                   └─────────────────────┘                             │
│                                                                         │
│  阶段4: 结果反馈                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐     │
│  │ 分析结果推送到话题 -> 话题内讨论结果                                │     │
│  └─────────────────────────────────────────────────────────────────┘     │
│                              │                                          │
│                              ▼                                          │
│                   ┌─────────────────────┐                             │
│                   │ 发送结果确认卡片      │                             │
│                   │ (确认/驳回按钮)       │                             │
│                   └─────────────────────┘                             │
│                                                                         │
│  阶段5: 结果确认                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐     │
│  │ 用户点击"确认" -> 需求状态更新为"已完成"                           │     │
│  │ 用户点击"驳回" -> 需求状态更新为"已驳回"，可重新分析                   │     │
│  └─────────────────────────────────────────────────────────────────┘     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 6. 会话隔离设计

### 6.1 会话键设计

| 场景 | 会话键格式 | 说明 |
|------|-----------|------|
| 单聊 | `{user_id}:{root_id}` | 当前单聊模式 |
| 群聊-普通问答 | `{user_id}:qa:{chat_id}` | 群内临时问答会话 |
| 群聊-需求话题 | `{requirement_id}:{thread_id}` | 需求话题独立会话 |

### 6.2 会话状态管理

```python
class GroupChatSessionManager:
    """群聊会话管理器"""

    async def get_qa_session(self, user_id: str, chat_id: str):
        """获取普通问答会话（每次创建新会话，不保持上下文）"""
        session_key = f"{user_id}:qa:{chat_id}"
        return await self.claude_session_manager.get_or_create_session(session_key)

    async def get_requirement_session(self, requirement_id: str, thread_id: str):
        """获取需求会话（保持话题内完整上下文）"""
        session_key = f"{requirement_id}:{thread_id}"
        return await self.claude_session_manager.get_or_create_session(session_key)
```

---

## 7. 飞书卡片设计

### 7.1 需求提交卡片

```json
{
  "config": {
    "wide_screen_mode": true
  },
  "header": {
    "title": {
      "tag": "plain_text",
      "content": "📋 提交数据分析需求"
    },
    "template": "blue"
  },
  "elements": [
    {
      "tag": "div",
      "text": {
        "tag": "lark_md",
        "content": "请填写以下需求信息："
      }
    },
    {
      "tag": "form",
      "name": "demand_form",
      "elements": [
        {
          "tag": "input",
          "label": {
            "tag": "plain_text",
            "content": "需求标题"
          },
          "name": "title",
          "placeholder": {
            "tag": "plain_text",
            "content": "请输入需求标题"
          },
          "required": true
        },
        {
          "tag": "textarea",
          "label": {
            "tag": "plain_text",
            "content": "需求描述"
          },
          "name": "description",
          "placeholder": {
            "tag": "plain_text",
            "content": "请详细描述您的分析需求"
          },
          "required": true
        },
        {
          "tag": "select_static",
          "label": {
            "tag": "plain_text",
            "content": "优先级"
          },
          "name": "priority",
          "placeholder": {
            "tag": "plain_text",
            "content": "请选择优先级"
          },
          "options": [
            {"text": {"tag": "plain_text", "content": "低"}, "value": "low"},
            {"text": {"tag": "plain_text", "content": "普通"}, "value": "normal"},
            {"text": {"tag": "plain_text", "content": "高"}, "value": "high"},
            {"text": {"tag": "plain_text", "content": "紧急"}, "value": "urgent"}
          ],
          "required": true
        }
      ]
    },
    {
      "tag": "action",
      "actions": [
        {
          "tag": "button",
          "text": {
            "tag": "plain_text",
            "content": "提交需求"
          },
          "type": "primary",
          "name": "submit_demand"
        },
        {
          "tag": "button",
          "text": {
            "tag": "plain_text",
            "content": "取消"
          },
          "name": "cancel_demand"
        }
      ]
    }
  ]
}
```

### 7.2 口径确认卡片

```json
{
  "config": {
    "wide_screen_mode": true
  },
  "header": {
    "title": {
      "tag": "plain_text",
      "content": "🔍 需求口径确认"
    },
    "template": "yellow"
  },
  "elements": [
    {
      "tag": "div",
      "text": {
        "tag": "lark_md",
        "content": "**需求标题：** {title}\n\n**需求描述：** {description}\n\n请在话题中@相关人员确认分析口径。"
      }
    },
    {
      "tag": "action",
      "actions": [
        {
          "tag": "button",
          "text": {
            "tag": "plain_text",
            "content": "✅ 口径已确认，开始分析"
          },
          "type": "primary",
          "name": "confirm_scope"
        },
        {
          "tag": "button",
          "text": {
            "tag": "plain_text",
            "content": "✏️ 修改需求"
          },
          "name": "edit_demand"
        }
      ]
    }
  ]
}
```

### 7.3 结果确认卡片

```json
{
  "config": {
    "wide_screen_mode": true
  },
  "header": {
    "title": {
      "tag": "plain_text",
      "content": "📊 分析结果"
    },
    "template": "green"
  },
  "elements": [
    {
      "tag": "div",
      "text": {
        "tag": "lark_md",
        "content": "**需求标题：** {title}\n\n**分析结果摘要：**\n{result_summary}\n\n请查看上方完整分析结果。"
      }
    },
    {
      "tag": "action",
      "actions": [
        {
          "tag": "button",
          "text": {
            "tag": "plain_text",
            "content": "✅ 确认结果"
          },
          "type": "primary",
          "name": "confirm_result"
        },
        {
          "tag": "button",
          "text": {
            "tag": "plain_text",
            "content": "❌ 驳回，需重新分析"
          },
          "name": "reject_result"
        }
      ]
    }
  ]
}
```

---

## 8. 实现步骤

### 阶段一：基础框架搭建

| 序号 | 任务 | 说明 |
|------|------|------|
| 1 | 扩展数据库模型 | 添加 DataRequirement、ThreadMessage 表 |
| 2 | 扩展 Session 表 | 添加 chat_id、thread_id、requirement_id 字段 |
| 3 | 创建群聊消息处理器 | GroupChatRouter 识别普通问答/需求管理模式 |
| 4 | 扩展 FeishuClient | 添加群聊消息、话题创建、卡片发送方法 |

### 阶段二：需求管理功能

| 序号 | 任务 | 说明 |
|------|------|------|
| 5 | 创建 DemandService | 需求CRUD、状态管理 |
| 6 | 创建 TopicService | 话题创建、消息发送 |
| 7 | 实现需求卡片 | 需求提交、口径确认、结果确认卡片 |
| 8 | 卡片动作处理器 | 处理提交、确认、驳回等操作 |

### 阶段三：会话隔离实现

| 序号 | 任务 | 说明 |
|------|------|------|
| 9 | 扩展 SessionManager | 支持群聊会话类型 |
| 10 | 实现会话键规则 | 单聊、群聊问答、需求话题不同键格式 |
| 11 | 会话上下文隔离 | 不同需求间完全独立 |

### 阶段四：集成测试

| 序号 | 任务 | 说明 |
|------|------|------|
| 12 | 单元测试 | 各模块功能测试 |
| 13 | 集成测试 | 完整流程测试 |
| 14 | 群聊实际测试 | 飞书群聊环境测试 |

---

## 9. 配置项

```python
# settings.py 新增配置

# 群聊配置
GROUP_CHAT_ENABLED: bool = True                     # 是否启用群聊功能
DEMAND_TRIGGER_KEYWORD: str = "帮我处理需求"         # 需求触发关键词

# 话题配置
THREAD_AUTO_CREATE: bool = True                     # 是否自动创建话题
THREAD_TITLE_PREFIX: str = "【需求】"               # 话题标题前缀

# 需求配置
DEMAND_STATUS_PENDING: str = "pending"               # 待处理
DEMAND_STATUS_SCOPE_CONFIRMED: str = "scope_confirmed"  # 口径已确认
DEMAND_STATUS_ANALYZING: str = "analyzing"           # 分析中
DEMAND_STATUS_WAITING_FEEDBACK: str = "waiting_feedback"  # 待反馈
DEMAND_STATUS_COMPLETED: str = "completed"           # 已完成
DEMAND_STATUS_CANCELLED: str = "cancelled"           # 已取消
```

---

## 10. 错误处理

| 错误场景 | 处理方式 |
|---------|---------|
| 创建话题失败 | 返回错误提示，不创建需求 |
| 发送卡片失败 | 重试3次，失败后发送文本消息 |
| 会话键冲突 | 自动追加时间戳 |
| 状态流转错误 | 记录日志，拒绝非法状态流转 |

---

## 11. 安全考虑

1. **权限验证**：确保机器人有群聊发送权限
2. **消息过滤**：只处理@机器人的消息
3. **敏感信息**：不在卡片中显示敏感数据
4. **输入验证**：对用户输入进行验证和清理

---

## 12. 附录

### 12.1 飞书相关文档

- [飞书开放平台 - 消息API](https://open.feishu.cn/document/im-v1/message/create)
- [飞书开放平台 - 话题功能](https://open.feishu.cn/document/im-v1/message/thread-introduction)
- [飞书开放平台 - 卡片](https://open.feishu.cn/document/common-capabilities/message-card/message-card-content)

### 12.2 参考来源

- [普通群消息形式切换为话题形式](https://www.feishu.cn/hc/zh-CN/articles/630899543442)
- [使用话题群](https://www.feishu.cn/hc/zh-CN/articles/360049067735)
- [创建群组](https://www.feishu.cn/hc/zh-CN/articles/360025113754)

---

**文档结束**
