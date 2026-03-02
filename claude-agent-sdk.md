# Claude Agent SDK Python 完整参考

本文档整理了官方 `claude-agent-sdk` Python 包的核心接口、配置类及使用方法，基于 Anthropic 官方文档及 SDK 源代码整理 。

## 1. 概述与安装

### 1.1 简介
Claude Agent SDK 是 Anthropic 官方推出的 Python SDK，用于基于 Claude Code 构建生产级的 AI 代理。它支持工具调用、权限管理、多轮会话、流式传输以及与 Model Context Protocol (MCP) 的集成 。

### 1.2 安装
**前置要求**:
- Python 3.10 或更高版本 
- Node.js (用于 Claude Code CLI 后端)
- Claude Code 命令行工具: `npm install -g @anthropic-ai/claude-code` 

**SDK 安装**:
```bash
pip install claude-agent-sdk
```
> **注**: 从 v0.1.8 开始，Claude Code 已默认打包在 SDK 中，通常无需单独安装 CLI 。若需使用特定版本，可通过 `cli_path` 选项指定 。

### 1.3 环境配置
设置 API 密钥 (必需):
```bash
export ANTHROPIC_API_KEY="your-api-key-here"
```
可选 - 使用第三方提供商:
- **Amazon Bedrock**: `export CLAUDE_CODE_USE_BEDROCK=1` (并配置 AWS 凭证)
- **Google Vertex AI**: `export CLAUDE_CODE_USE_VERTEX=1` (并配置 GCP 凭证) 

## 2. 核心交互方式：`query()` 与 `ClaudeSDKClient`

SDK 提供了两种主要的交互模式，应根据使用场景选择 。

| 特性 | `query()` | `ClaudeSDKClient` |
| :--- | :--- | :--- |
| **会话** | 每次调用创建**新会话** | **复用同一会话**，保持上下文 |
| **对话** | 单次问答，无记忆 | 多轮连续对话 |
| **生命周期** | 自动管理 | 手动控制 (连接/断开) |
| **自定义工具** | ❌ 不支持 | ✅ 支持 |
| **钩子 (Hooks)** | ❌ 不支持 | ✅ 支持 |
| **中断 (Interrupt)** | ❌ 不支持 | ✅ 支持 |
| **适用场景** | 独立的、一次性的任务，如简单的脚本自动化。 | 需要记忆的复杂对话、交互式应用、需动态响应的场景。 |

## 3. 函数 API (Function Reference)

### 3.1 `query()`
执行一次性的、无状态的流式查询 。

```python
async def query(
    *,
    prompt: str | AsyncIterable[dict[str, Any]],
    options: ClaudeAgentOptions | None = None,
    transport: Transport | None = None
) -> AsyncIterator[Message]
```

**参数**:
- `prompt` (必须): 输入提示。可以是普通字符串，也可以是用于流式输入的异步迭代器 。
- `options` (可选): `ClaudeAgentOptions` 配置对象。
- `transport` (可选): 自定义传输层实现。

**返回**: `AsyncIterator[Message]`，产生 `Message` 对象 (如 `AssistantMessage`, `ResultMessage` 等) 。

**示例**:
```python
import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions

async def main():
    options = ClaudeAgentOptions(
        system_prompt="You are a helpful assistant.",
        permission_mode='acceptEdits'
    )
    async for message in query(
        prompt="What files are in this directory?",
        options=options
    ):
        print(message)

asyncio.run(main())
```

### 3.2 `tool()`
装饰器，用于将 Python 函数定义为可供 Claude 调用的 MCP 工具 。

```python
def tool(
    name: str,
    description: str,
    input_schema: type | dict[str, Any]
) -> Callable
```

**参数**:
- `name`: 工具的唯一标识符。
- `description`: 工具用途的描述，Claude 据此判断何时调用。
- `input_schema`: 输入参数的 schema 定义 。
    - **简单类型映射** (推荐): `{"param1": str, "param2": int}`
    - **完整 JSON Schema**: 用于复杂验证。

**返回**: 装饰后的异步函数，包装为 `SdkMcpTool` 实例 。

**示例**:
```python
from claude_agent_sdk import tool

@tool("get_weather", "Get current weather for a location", {"location": str})
async def get_weather(args: dict[str, any]) -> dict[str, any]:
    # 模拟天气查询逻辑
    weather_data = {"location": args["location"], "condition": "Sunny", "temp": 25}
    return {
        "content": [{"type": "text", "text": f"当前天气: {weather_data}"}]
    }
```

### 3.3 `create_sdk_mcp_server()`
创建一个进程内的 MCP 服务器，用于托管通过 `@tool` 定义的工具 。

```python
def create_sdk_mcp_server(
    name: str,
    version: str = "1.0.0",
    tools: list[SdkMcpTool[Any]] | None = None
) -> McpSdkServerConfig
```

**参数**:
- `name`: 服务器唯一标识。
- `version`: 服务器版本号。
- `tools`: 由 `@tool` 装饰的函数列表。

**返回**: `McpSdkServerConfig` 对象，可直接传入 `ClaudeAgentOptions` 的 `mcp_servers` 字段 。

**示例**:
```python
from claude_agent_sdk import tool, create_sdk_mcp_server

@tool("add", "Add two numbers", {"a": float, "b": float})
async def add(args):
    return {"content": [{"type": "text", "text": f"Result: {args['a'] + args['b']}"}]}

# 创建服务器
calc_server = create_sdk_mcp_server(
    name="calculator",
    version="1.0.0",
    tools=[add]
)

# 在选项中引用
options = ClaudeAgentOptions(
    mcp_servers={"calc": calc_server},
    allowed_tools=["mcp__calc__add"]
)
```

## 4. 类 API (Class Reference)

### 4.1 `ClaudeSDKClient`
用于管理持久化会话的客户端，支持多轮对话、工具和钩子 。

```python
class ClaudeSDKClient:
    def __init__(
        self,
        options: ClaudeAgentOptions | None = None,
        transport: Transport | None = None
    )
```

**方法**:

| 方法 | 描述 |
| :--- | :--- |
| `connect(prompt: str \| AsyncIterable[dict] \| None = None) -> None` | 建立与 Claude 的连接，并可选择发送初始提示。 |
| `query(prompt: str \| AsyncIterable[dict], session_id: str = "default") -> None` | 在已连接的会话中发送新消息 (流式)。 |
| `receive_messages() -> AsyncIterator[Message]` | 接收所有消息，直到连接关闭。 |
| `receive_response() -> AsyncIterator[Message]` | 接收消息流，直到收到 `ResultMessage` (表示当前响应完成)。 |
| `interrupt() -> None` | 中断 Claude 当前的执行 (仅在流式模式下有效)。 |
| `set_permission_mode(mode: str) -> None` | 动态更改权限模式 (`default`, `acceptEdits`, `plan`, `bypassPermissions`)。 |
| `set_model(model: str \| None = None) -> None` | 动态切换模型。 |
| `get_server_info() -> dict[str, Any] \| None` | 获取服务器的能力和信息。 |
| `disconnect() -> None` | 断开连接并清理资源。 |
| `__aenter__() / __aexit__()` | 异步上下文管理器支持，自动连接和断开。 |

**上下文管理器示例**:
```python
import asyncio
from claude_agent_sdk import ClaudeSDKClient

async def main():
    async with ClaudeSDKClient() as client:
        await client.query("What is the capital of France?")
        async for message in client.receive_response():
            print(message)  # 处理第一个响应

        # 继续同一会话
        await client.query("What is the population of that city?")
        async for message in client.receive_response():
            print(message)  # Claude 记得上下文

asyncio.run(main())
```

## 5. 配置类: `ClaudeAgentOptions`

这是 SDK 中最核心的配置类，用于控制模型行为、权限、工具、工作目录等几乎所有方面 。

```python
@dataclass
class ClaudeAgentOptions:
```

### 5.1 工具控制
| 字段 | 类型 | 描述 | 示例 |
| :--- | :--- | :--- | :--- |
| `allowed_tools` | `list[str]` | 明确允许 Claude 使用的工具列表。为空列表表示无限制 。 | `["Read", "Bash", "Glob"]` |
| `disallowed_tools` | `list[str]` | 明确禁止的工具列表，优先级高于 `allowed_tools` 。 | `["Write", "Edit"]` |
| `mcp_servers` | `dict[str, McpServerConfig] \| str \| Path` | MCP 服务器配置。可以是字典、配置文件路径，或由 `create_sdk_mcp_server` 创建的对象 。 | `{"calc": calc_server}` |

### 5.2 权限与控制流
| 字段 | 类型 | 描述 | 示例 |
| :--- | :--- | :--- | :--- |
| `permission_mode` | `str \| None` | 权限处理模式 。<br>- `'default'`: 危险操作时提示用户 (默认)。<br>- `'acceptEdits'`: 自动接受文件编辑。<br>- `'plan'`: 生成计划但不执行工具。<br>- `'bypassPermissions'`: 允许所有工具 (谨慎使用)。 | `'acceptEdits'` |
| `can_use_tool` | `CanUseTool \| None` | 自定义权限回调函数。在每个工具执行前调用，决定是否允许 。 | `async (tool, input) -> bool` |
| `max_turns` | `int \| None` | 限制会话的最大轮数，防止无限循环 。 | `10` |
| `continue_conversation` | `bool` | 是否继续最近的会话 。 | `True` |
| `resume` | `str \| None` | 恢复指定 ID 的会话 。 | `"sess_12345"` |
| `fork_session` | `bool` | 恢复会话时是否 fork 到一个新的会话 ID 。 | `False` |

### 5.3 系统提示与模型
| 字段 | 类型 | 描述 | 示例 |
| :--- | :--- | :--- | :--- |
| `system_prompt` | `str \| SystemPromptPreset \| None` | 自定义系统提示词，或使用预设 。 | `"You are a Python expert."` 或 `{"type": "preset", "preset": "claude_code"}` |
| `model` | `str \| None` | 指定使用的 Claude 模型 ID 。 | `"claude-3-5-sonnet-latest"` |
| `max_thinking_tokens` | `int \| None` | 控制 Claude 内部推理过程的最大 token 数 。 | `4000` |

### 5.4 执行环境
| 字段 | 类型 | 描述 | 示例 |
| :--- | :--- | :--- | :--- |
| `cwd` | `str \| Path \| None` | 工具执行的工作目录 (文件操作、Bash 命令的相对路径) 。 | `"/home/user/project"` |
| `env` | `dict[str, str]` | 为工具执行设置的环境变量 。 | `{"DEBUG": "true"}` |
| `add_dirs` | `list[str \| Path]` | 添加到 Claude 上下文的额外目录 。 | `["/data", "./src"]` |
| `setting_sources` | `list[SettingSource] \| None` | 从文件系统加载技能 (`skills`)、命令等的来源 。 | `['user', 'project']` |
| `plugins` | `dict[str, SdkPluginConfig] \| None` | 以编程方式加载 Claude Code 插件 。 | `{"my_plugin": {"path": "./plugins/my_plugin"}}` |

### 5.5 高级与调试
| 字段 | 类型 | 描述 | 示例 |
| :--- | :--- | :--- | :--- |
| `hooks` | `dict[HookEvent, list[HookMatcher]] \| None` | 为特定生命周期事件 (如 PreToolUse, PostToolUse) 注册钩子 。 | `{"PreToolUse": [...]}` |
| `include_partial_messages` | `bool` | 是否流式输出部分消息更新 (`StreamEvent`) 。 | `True` |
| `stderr` | `Callable[[str], None] \| None` | 处理 Claude Code CLI 的 stderr 输出的回调函数 。 | `lambda line: logging.debug(f"CLI: {line}")` |
| `cli_path` | `str \| None` | 指定自定义的 Claude Code CLI 路径 。 | `"/path/to/claude"` |
| `max_budget_usd` | `float \| None` | 设置会话的最大美元支出预算，超出后自动终止 。 | `0.05` |

## 6. 消息类型 (`Message`)

SDK 中的响应均为 `Message` 类型，常见子类包括 :
- **`UserMessage`**: 来自用户的消息。
- **`AssistantMessage`**: Claude 的回复，其 `content` 属性是 `ContentBlock` 列表 (如 `TextBlock`, `ToolUseBlock`)。
- **`SystemMessage`**: 系统级消息。
- **`ResultMessage`**: 表示一次响应的结束，包含最终结果及 `session_id`、`cost` 等信息。
- **`StreamEvent`**: 当 `include_partial_messages` 为 `True` 时产生，包含部分生成的内容。

## 7. 版本更新与功能 (截至 v0.1.39)

- **v0.1.8+**: Claude Code 默认打包在 SDK 中，无需单独安装 。
- **v0.1.7+**: 支持结构化输出 (Structured Outputs) 和后备模型处理 。
- **v0.1.6+**: 增加 `max_budget_usd` (成本控制) 和 `max_thinking_tokens` 。
- **v0.1.5+**: 增加插件 (`plugins`) 支持 。
- **v0.1.0+**: 初始版本发布，支持核心功能 。