# 飞书 + Claude SDK 智能对话服务

> 通过飞书机器人接收用户消息，使用Claude SDK智能处理需求，支持多轮对话和信息补充澄清。

## 项目特性

- ✅ 混合交互模式：支持简单文本对话和复杂卡片交互
- ✅ 智能会话管理：自动识别新需求，保持同一需求的会话上下文
- ✅ 等待上下文机制：支持Claude向用户询问补充信息
- ✅ 多用户并发：支持多用户同时使用
- ✅ 异步处理：Webhook快速响应，后台任务处理
- ✅ 会话持久化：PostgreSQL + Redis双存储
- ✅ 完善的错误处理和日志
- ✅ 长连接支持：通过独立进程实现飞书WebSocket长连接

## 技术栈

- **Web框架**: FastAPI
- **飞书SDK**: lark-oapi
- **Claude SDK**: claude-agent-sdk
- **数据库**: PostgreSQL + Redis
- **部署**: Docker + Docker Compose

## 架构说明

```
+-------------------+         +-------------------+
|   飞书平台    |         |  主服务       |
|  (WebSocket)    |         | (FastAPI)      |
|                 +-------->|                 |
|  长连接服务    |  HTTP POST      |  API Router     |
| (独立进程)      |  /webhook/message |                 |
|                 |  /webhook/card   |                 |
+-------------------+         +-------->+-------------------+
                                    |
                                    |
                            +-------+-------+
                            |               |
                      Session Manager  Claude SDK
                      +---------------+
                                    |
                                    v
                            +---------------+
                            | PostgreSQL    |
                            | + Redis      |
                            +---------------+
```

### 组件说明

- **主服务 (FastAPI)**:
  - 处理飞书事件
  - 管理会话状态
  - 调用 Claude API
  - 提供健康检查和 API 文档

- **长连接服务 (独立进程)**:
  - 通过 WebSocket 连接飞书
  - 接收消息和卡片动作事件
  - 通过 HTTP API 转发到主服务
  - 避免与 uvicorn 事件循环冲突

### 通信流程

1. 飞书平台 -> 长连接服务 (WebSocket)
2. 长连接服务 -> 主服务 (HTTP POST /api/v1/webhook/*)
3. 主服务 -> Session Manager (内存)
4. Session Manager -> Claude SDK (API 调用)
5. Claude SDK -> 主服务 (响应)
6. 主服务 -> 飞书平台 (HTTP API 发送消息)

## 项目结构

```
src/
├── main.py                    # 应用入口
├── config/                    # 配置管理
├── api/                       # API层
├── core/                      # 核心业务层
├── claude/                    # Claude SDK集成
├── feishu/                    # 飞书集成
├── models/                    # 数据模型
├── storage/                   # 存储层
├── utils/                     # 工具函数
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
- `ANTHROPIC_API_KEY`: Claude API密钥
- `FEISHU_APP_ID`: 飞书应用ID
- `FEISHU_APP_SECRET`: 飞书应用密钥
- `DATABASE_URL`: 数据库连接URL
- `REDIS_URL`: Redis连接URL

### 3. 启动数据库

```bash
docker-compose up -d db redis
```

### 4. 运行数据库迁移

```bash
alembic upgrade head
```

### 5. 启动应用

#### 方式一：启动脚本（推荐）

```bash
# Windows
start.bat

# Linux/Mac
# 需要同时启动两个服务：
# 终端1: python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --log-level info
# 终端2: python src/feishu/long_connection_service.py
```

#### 方式二：分别启动

```bash
# 终端1 - 主服务（FastAPI）
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --log-level info

# 终端2 - 长连接服务
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

## 业务流程

### 新需求处理

1. 用户发送消息 → Webhook接收
2. 判断为新需求（话题切换/关键词）
3. 创建新会话（新的ClaudeSDKClient实例）
4. Claude处理需求
5. 返回结果给用户

### 信息补充流程

1. Claude调用`ask_user_for_info`工具
2. 系统记录WaitingContext（Redis）
3. 发送问题给用户
4. 工具立即返回，Claude继续完成当前轮次
5. 用户回复后：
   - 检测到WaitingContext
   - 构建带上下文的query
   - 发送给Claude继续处理
6. 完成需求

### 回复链模式

- 通过`root_id`识别回复链
- 同一需求的多次补充保持在同一会话
- Claude记得之前的对话上下文

## 开发说明

### 运行测试

```bash
pytest tests/
```

### 代码规范

- 使用类型注解
- 遵循PEP 8规范
- 添加适当的错误处理
- 编写docstring

## 常见问题

### Q: 如何配置飞书机器人？

1. 登录[飞书开放平台](https://open.feishu.cn/)
2. 创建企业自建应用
3. 启用机器人功能
4. 配置事件订阅
5. 设置消息接收权限

### Q: Claude SDK如何实现等待用户回复？

- Claude工具调用是同步的，无法"等待"
- 通过应用层记录WaitingContext（Redis）
- 用户回复后，构建带上下文的query继续处理
- 同一ClaudeSDKClient实例保持会话状态

### Q: 如何区分不同需求？

- 话题相似度检测（低于阈值则判定为切换）
- 显式关键词检测（"新需求"、"重新开始"等）
- 时间间隔检测（超过30分钟可能判定为新需求）

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！

## 联系方式

- 项目文档: `docs/technical-design.md`
- API文档: http://localhost:8000/docs
