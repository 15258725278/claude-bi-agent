# Changelog

所有项目的重大变更都记录在此文件中。

## [3.1.0] - 2026-03-04

### 新增功能

- **群聊支持** - 新增群聊普通问答和需求管理模式
- **话题功能** - 支持创建独立话题，保持需求上下文隔离
- **消息过滤** - 智能过滤群聊消息，只处理@机器人的消息
- **话题内回复** - 支持在话题内回复消息，`reply_in_thread` 参数支持
- **需求管理模式** - 触发关键词创建需求话题，发送需求卡片
- **会话隔离** - 不同需求间会话完全独立，互不干扰

### 改进

- **SystemMessage 过滤** - 群聊响应中过滤 SystemMessage，避免返回技能描述内容
- **机器人 ID 获取** - 通过 `bot/v3/info` API 获取机器人 open_id
- **数据库枚举优化** - 从 enum 对象改为字符串常量，避免 SQLAlchemy 错误

### 修复

- 修复群聊中返回技能描述内容的问题
- 修复话题内未@机器人的消息不处理的问题
- 修复数据库 enum 类型 `'SessionState.ACTIVE' is not among defined enum values` 错误
- 修复长连接服务 user_id 为 None 时的处理问题

### 技术细节

- 新增 `GroupChatHandler` - 群聊消息处理器
- 新增 `GroupChatRouter` - 消息路由器
- 新增 `GroupChatSessionManager` - 群聊会话管理器
- 新增 `TopicService` - 话题服务
- 新增 `DemandService` - 需求管理服务
- 扩展 `FeishuClient` - 添加群聊消息、话题创建方法
- 扩展 `Session` 模型 - 添加 `session_type`, `chat_id`, `thread_id`, `requirement_id` 字段

### 配置变更

- 新增 `GROUP_CHAT_ENABLED` 配置项 - 是否启用群聊功能
- 新增 `DEMAND_TRIGGER_KEYWORD` 配置项 - 需求触发关键词

---

## [3.0.0] - 2026-02-XX

### 新增功能

- **Claude Skills 系统** - 支持业务背景知识、数据仓库元数据等技能渐进式加载
- **长连接服务** - 通过独立进程实现飞书 WebSocket 长连接
- **实时响应** - 接收消息后立即发送确认表情，后台异步处理
- **多用户并发** - 支持多用户同时使用

### 改进

- 使用 `open_id` 代替 `user_id`，避免权限问题
- 异步处理 Webhook 事件
- 完善结构化日志记录

---

## [2.0.0] - 2026-01-XX

### 新增功能

- 基于 Claude SDK 的智能对话
- 飞书机器人集成
- SQLite 数据存储
