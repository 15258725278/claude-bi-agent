# 屈臣氏 BI 数据分析智能助手

> 基于飞书 + Claude SDK 的 BI 数据分析智能助手，支持业务背景知识查询、数据仓库元数据查询、销售数据分析等功能。

## 项目特性

- ✅ **实时响应**：接收消息后立即发送 👌 表情确认，后台异步处理
- ✅ **长连接支持**：通过独立进程实现飞书 WebSocket 长连接
- ✅ **智能对话**：基于 Claude SDK 的多轮对话能力
- ✅ **Skills 系统**：支持业务背景知识、数据仓库元数据等技能渐进式加载
- ✅ **open_id 优化**：使用 open_id 代替 user_id，避免权限问题
- ✅ **多用户并发**：支持多用户同时使用
- ✅ **异步处理**：Webhook 快速响应，后台任务处理
- ✅ **完善日志**：结构化日志记录，便于问题排查

## 技术栈

| 组件 | 技术选择 | 版本 | 选型理由 |
|------|----------|------|----------|
| **Web框架** | FastAPI | 0.104+ | 异步支持优秀，自动API文档 |
| **飞书SDK** | lark-oapi | 1.5.3 | 官方Python SDK，功能完整 |
| **飞书模式** | 长连接（WebSocket） | - | 实时消息推送，无需轮询 |
| **Claude SDK** | claude-agent-sdk | v0.1.39+ | 官方SDK，支持Skills、多轮对话 |
| **Claude模型** | glm-4.7 | - | 国内可用模型 |
| **Skills** | 本地SKILL.md | - | 业务背景知识、数据仓库元数据 |
| **数据库** | SQLite（aiosqlite）| 3.44+ | 简单部署，异步支持 |

## 架构说明

```
+-------------------+         +-------------------+
|   飞书平台    |         |  主服务       |
|  (WebSocket)    |         | (FastAPI)      |
|                 +-------->|                 |
|  长连接服务    |  HTTP POST      |  API Router     |
| (独立进程)      |  /webhook/message |                 |
|                 +-------->+-------------------+
                                    |
                                    |
                            +-------+-------+
                            |               |
                      Session Manager  Claude SDK
                      +---------------+       |
                                    |       |
                                    v       v
                            +-------------------+
                            |  Skills  (用户)   |
                            |  - 业务背景知识   |
                            |  - 数仓元数据    |
                            +-------------------+
                                    |
                                    v
                            +---------------+
                            |   SQLite     |
                            +---------------+
```

### 组件说明

- **主服务 (FastAPI)**:
  - 处理飞书事件
  - 管理会话状态
  - 调用 Claude SDK
  - 发送消息确认和回复

- **长连接服务 (独立进程)**:
  - 通过 WebSocket 连接飞书
  - 接收消息和卡片动作事件
  - 通过 HTTP API 转发到主服务
  - 避免 uvicorn 事件循环冲突

### 通信流程

1. 飞书平台 → 长连接服务 (WebSocket)
2. 长连接服务 → 主服务 (HTTP POST /api/v1/webhook/*)
3. 主服务 → 立即返回"处理中" + 发送 👌 表情
4. 主服务 → Claude SDK (后台任务)
5. Claude SDK → Skills 加载 (根据需要加载业务背景知识、数仓元数据)
6. Claude SDK → 主服务 (响应)
7. 主服务 → 飞书平台 (HTTP API 发送消息)

## 项目结构

```
src/
├── main.py                    # 应用入口
├── config/                    # 配置管理
├── api/                       # API层
│   └── v1/
│       └── webhook.py          # Webhook端点
├── core/                      # 核心业务层
│   ├── session_manager.py      # 会话管理器
│   ├── demand_detector.py      # 需求检测器
│   └── context.py            # 上下文管理器
├── claude/                    # Claude SDK集成
│   ├── factory.py             # Claude会话工厂
│   └── prompts.py            # 系统提示词
├── feishu/                    # 飞书集成
│   ├── client.py              # 飞书客户端
│   └── long_connection_service.py  # 长连接服务
├── models/                    # 数据模型
├── storage/                   # 存储层
│   ├── database.py           # 数据库连接
│   ├── repository.py        # 数据仓库
│   └── redis_client.py      # Redis客户端
├── utils/                     # 工具函数
│   └── logger.py             # 日志工具
└── middleware/                # 中间件
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

复制并编辑 `.env` 文件：

```bash
cp .env.example .env
```

需要配置：
- `FEISHU_APP_ID`: 飞书应用ID
- `FEISHU_APP_SECRET`: 飞书应用密钥
- `MAIN_SERVICE_URL`: 主服务URL (默认 http://localhost:8000)

### 3. 启动应用

#### 方式一：使用启动脚本（推荐）

```bash
# 终端1 - 启动主服务
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --log-level info

# 终端2 - 启动长连接服务
python src/feishu/long_connection_service.py
```

#### 方式二：使用便捷脚本

```bash
# Linux/Mac - 同时启动两个服务（使用 start_long_connection.py）
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --log-level info &
python src/feishu/long_connection_service.py
```

#### 方式三：Docker 部署

```bash
docker-compose up
```

## API文档

启动后访问：
- Swagger UI: http://localhost:8000/docs
- ReDoc UI: http://localhost:8000/redoc

## Skills 配置

项目支持 Claude Skills 系统，用于加载业务知识和技能。

### 可用技能

1. **业务背景知识**
   - 位置：`~/.claude/skills/业务背景知识/SKILL.md`
   - 功能：屈臣氏业务概览、销售数据分析、用户行为分析、营销运营分析
   - 参考：包含会员等级、渠道标签、时间周期等业务术语

2. **数据仓库元数据**
   - 位置：`~/.claude/skills/数据仓库元数据/SKILL.md`
   - 功能：数仓架构、表结构、字段定义、开发规范

### 配置技能

将技能文件放置在 `~/.claude/skills/` 目录下，SDK 会自动加载。

### 技能参数配置

```python
options = ClaudeAgentOptions(
    setting_sources=["user"],      # 从 ~/.claude/skills/ 加载用户技能
    allowed_tools=["Skill"],       # 启用技能工具
    add_dirs=["/root/.claude/skills"],  # 允许访问技能参考文件
)
```

## 关键实现说明

### 1. 消息确认机制

```python
# 收到消息后立即发送确认表情
async def dispatch(self, user_id: str, open_id: str, ...):
    # 立即发送确认表情
    await self.feishu_client.send_ack_emoji(user_id=open_id)

    # 然后在后台处理 Claude 请求
    await claude_client.query(content)
    async for msg in claude_client.receive_response():
        # 处理响应...
```

### 2. open_id 代替 user_id

```python
# 飞书客户端使用 open_id 发送消息
class FeishuClient:
    async def send_message(self, user_id: str, content: str):
        request = CreateMessageRequest.builder() \
            .receive_id_type("open_id")  # 使用 open_id
            .request_body(...)
```

**为什么使用 open_id？**
- `user_id` 需要应用具有 `contact:user.employee_id:readonly` 权限
- `open_id` 不需要额外权限，更适合机器人使用

### 3. 长连接服务与主服务通信

```python
# 长连接服务转发事件到主服务
def send_to_main_service(self, event_type: str, event_data: dict):
    response = requests.post(
        f"{self.main_service_url}/api/v1/webhook/message",
        json=event_data,
        timeout=60.0
    )
```

### 4. 主服务后台处理

```python
# Webhook 立即返回，后台任务处理
@router.post("/webhook/message")
async def receive_message_event(event: MessageEvent):
    # 立即返回
    task = asyncio.create_task(_process_message_async(event))
    return {"status": "processing", "message": "正在处理中，请稍候..."}

async def _process_message_async(event: MessageEvent):
    # 后台处理
    await session_manager.dispatch(...)
```

## 常见问题

### Q: 如何配置飞书机器人？

1. 登录[飞书开放平台](https://open.feishu.cn/)
2. 创建企业自建应用
3. 启用机器人功能
4. 配置事件订阅（长连接模式）
5. 设置消息发送权限

### Q: 遇到权限错误 99991672？

**错误信息**: `Access denied. One of the following scopes is required: [contact:user.employee_id:readonly]`

**解决方案**: 项目已使用 `open_id` 代替 `user_id`，请确保：
1. 代码中 `receive_id_type` 设置为 `"open_id"`
2. 飞书应用已启用机器人权限

### Q: 长连接服务连接失败？

1. 检查 `FEISHU_APP_ID` 和 `FEISHU_APP_SECRET` 是否正确
2. 检查主服务是否已启动
3. 检查 `MAIN_SERVICE_URL` 配置是否正确

### Q: 如何查看日志？

- 主服务日志: 终端输出或配置日志文件
- 长连接日志: 重定向到文件或使用 `tail -f` 查看

```bash
# 启动时重定向日志
python src/feishu/long_connection_service.py > /tmp/long_connection.log 2>&1 &
tail -f /tmp/long_connection.log
```

## 开发说明

### 运行测试

```bash
pytest tests/
```

### 代码规范

- 使用类型注解
- 遵循 PEP 8 规范
- 添加适当的错误处理
- 编写 docstring

### 添加新功能

1. 在 `src/feishu/client.py` 添加客户端方法
2. 在 `src/core/session_manager.py` 添加业务逻辑
3. 在 `src/api/v1/webhook.py` 添加 API 端点（如需要）
4. 更新测试用例

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！

## 联系方式

- 技术文档: `docs/technical-design.md`
- API文档: http://localhost:8000/docs
