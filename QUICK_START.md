# 优化模块快速使用指南

## ✅ 优化已完成

飞书交互模块优化已完成！所有文件已就位并测试通过。

## 📁 文件清单

```bash
/root/claude-bi-agent/src/feishu/
├── optimized_client.py      # 优化的飞书客户端
├── message_parser.py        # 消息解析器
├── event_handler.py         # 事件处理器
└── client_backup.py         # 原客户端备份
```

## 🚀 快速开始

### 1. 替换飞书客户端

在你的代码中找到这个导入：
\`\`\`python
from src.feishu.client import FeishuClient
\`\`\`

替换为：
\`\`\`python
from src.feishu.optimized_client import FeishuClient as OptimizedFeishuClient
from src.feishu.optimized_client import PermissionError
\`\`\`

然后创建客户端：
\`\`\`python
client = OptimizedFeishuClient(
    app_id=settings.FEISHU_APP_ID,
    app_secret=settings.FEISHU_APP_SECRET,
    max_retries=3,  # 最大重试次数
    retry_delay=1.0  # 重试延迟（秒）
)
\`\`\`

### 2. 使用新功能

#### 发送消息（自动重试）
\`\`\`python
await client.send_message(user_id, "你好")
\`\`\`

#### 发送卡片
\`\`\`python
card = {
    "config": {"wide_screen_mode": True},
    "header": {"title": {"content": "卡片标题", "tag": "plain_text"}},
    "elements": [
        {
            "tag": "div",
            "text": {"content": "卡片内容", "tag": "lark_md"}
        }
    ]
}

await client.send_card(user_id, card)
\`\`\`

#### 发送图片
\`\`\`python
await client.send_image(user_id, image_key="img_xxx")
\`\`\`

#### 发送文件
\`\`\`python
await client.send_file(user_id, file_key="file_xxx")
\`\`\`

#### 处理权限错误
\`\`\`python
try:
    await client.send_card(user_id, card)
except PermissionError as e:
    # e.grant_url 包含授权链接
    await send_permission_notice(user_id, e.grant_url)
\`\`\`

### 3. 使用消息解析器

\`\`\`python
from src.feishu.message_parser import MessageParser, MessageDeduplicator

# 解析消息
parsed = MessageParser.parse(event_data)
print(f"类型: {parsed.message_type.value}")
print(f"文本: {parsed.text}")
print(f"@提及: {parsed.mentions}")
print(f"图片: {parsed.image_key}")

# 消息去重
deduplicator = MessageDeduplicator()
if deduplicator.is_duplicate(message_id):
    return  # 跳过重复消息

# 检查是否 @机器人
if MessageParser.is_bot_mentioned(text, bot_user_id):
    # 处理 @提及
    pass
\`\`\`

### 4. 使用事件处理器

\`\`\`python
from src.feishu.event_handler import GroupPolicyChecker

# 创建群组策略
policy_config = {
    "default": "mention",  # 默认只响应 @提及
    "whitelist": ["group_open_id_1"],  # 白名单群组
    "blacklist": ["group_open_id_2"],  # 黑名单群组
    "groups": {
        "group_open_id_1": "all",  # 白名单：响应所有
    }
}

policy_checker = GroupPolicyChecker(policy_config)

# 检查是否应该响应
if policy_checker.should_respond(
    chat_id=chat_id,
    is_group=True,
    is_mentioned=True
):
    # 响应消息
    pass
\`\`\`

## 📊 优化效果

### 稳定性提升
| 指标 | 优化前 | 优化后 |
|------|--------|--------|
| 网络错误恢复 | ❌ | ✅ 自动重试 |
| 权限错误提示 | ❌ | ✅ 引导用户 |
| 重复消息处理 | ❌ | ✅ 自动去重 |
| 错误日志 | ⚠️ | ✅ 详细分类 |

### 功能完整性
| 功能 | 优化前 | 优化后 |
|------|--------|--------|
| 文本消息 | ✅ | ✅ |
| 图片消息 | ❌ | ✅ |
| 文件消息 | ❌ | ✅ |
| 富文本 | ⚠️ | ✅ |
| 卡片更新 | ❌ TODO | ✅ |
| @提及 | ❌ | ✅ |
| 消息历史 | ❌ | ✅ |
| 群组策略 | ❌ | ✅ |

### 用户体验
| 特性 | 优化前 | 优化后 |
|------|--------|--------|
| 消息发送成功 | ⚠️ | ✅ 更稳定 |
| 权限错误反馈 | ❌ | ✅ 引导授权 |
| 重复消息干扰 | ❌ | ✅ 自动过滤 |
| 上下文感知 | ❌ | ✅ 历史记录 |

## 🧪 测试

运行测试脚本验证功能：
\`\`\`bash
cd /root/claude-bi-agent
python3 test_optimization.py
\`\`\`

## 📝 日志查看

\`\`\`bash
# 查看服务日志
tail -f /tmp/claude-bot.log

# 查看优化版日志
tail -f /tmp/claude-bot-optimized.log

# 搜索错误
grep -i error /tmp/claude-bot-optimized.log

# 搜索权限错误
grep -i permission /tmp/claude-bot-optimized.log
\`\`\`

## 🔄 回滚

如果需要回滚到原客户端：
\`\`\`bash
cd /root/claude-bi-agent/src/feishu
mv optimized_client.py optimized_client.py.new
mv client_backup.py optimized_client.py
\`\`\`

## 📚 相关文档

- `OPTIMIZATION_PLAN.md` - 详细优化方案
- `OPTIMIZATION_COMPLETE.md` - 优化完成说明
- `OPTIMIZATION_FINAL_REPORT.md` - 最终报告

## 🎉 总结

飞书交互模块优化已完成！

主要改进：
1. ✅ 自动重试机制 - 提升稳定性
2. ✅ 权限错误处理 - 改善用户体验
3. ✅ 消息去重 - 避免重复处理
4. ✅ @提及支持 - 增强交互
5. ✅ 媒体支持 - 图片、文件发送
6. ✅ 消息历史 - 上下文感知
7. ✅ 群组策略 - 灵活配置

保持原有架构（双进程），增强了功能！
