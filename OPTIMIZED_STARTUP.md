# 优化版启动指南

## 快速启动

### 1. 安装新文件

```bash
cd /root/claude-bi-agent

# 复制优化后的文件
cp src/feishu/integrated_service.py src/feishu/integrated_service.py
cp src/feishu/enhanced_client.py src/feishu/enhanced_client.py
cp src/feishu/message_parser.py src/feishu/message_parser.py
cp src/feishu/event_handler.py src/feishu/event_handler.py
```

### 2. 备份旧文件

```bash
# 备份原始的 main.py
cp src/main.py src/main_backup.py
```

### 3. 启动优化版服务

```bash
# 停止旧服务
pkill -f "python3 -m uvicorn"

# 启动优化版（单进程长连接）
cd /root/claude-bi-agent
nohup python3 -m uvicorn src.main_optimized:app \
  --host 0.0.0.0 \
  --port 8000 \
  > /tmp/claude-bot-optimized.log 2>&1 &

# 检查日志
tail -f /tmp/claude-bot-optimized.log
```

### 4. 验证服务

```bash
# 检查进程
ps aux | grep uvicorn | grep -v grep

# 检查健康状态
curl http://localhost:8000/health

# 查看日志
tail -50 /tmp/claude-bot-optimized.log
```

## 优化效果

### 架构简化
- **之前**：主服务 + 长连接服务（2 个进程）
- **现在**：单进程集成服务（1 个进程）

### 功能增强
- ✅ 自动重试（指数退避）
- ✅ 权限错误处理和引导
- ✅ 消息去重
- ✅ 消息历史管理
- ✅ @提及检测
- ✅ 群组策略
- ✅ 支持媒体文件（图片、文件）
- ✅ 卡片更新功能

### 稳定性提升
- ✅ WebSocket 自动重连
- ✅ 错误分类处理
- ✅ 详细日志记录

## 监控和管理

### 查看服务状态
```bash
curl http://localhost:8000/health
```

响应：
```json
{
  "status": "ok",
  "feishu_connected": true
}
```

### 查看日志
```bash
# 实时日志
tail -f /tmp/claude-bot-optimized.log

# 最近 100 行
tail -100 /tmp/claude-bot-optimized.log

# 搜索错误
grep -i error /tmp/claude-bot-optimized.log
```

### 重启服务
```bash
# 停止
pkill -f "python3 -m uvicorn src.main_optimized"

# 启动
nohup python3 -m uvicorn src.main_optimized:app \
  --host 0.0.0.0 \
  --port 8000 \
  > /tmp/claude-bot-optimized.log 2>&1 &
```

## API 文档

启动后访问：
- Swagger UI: http://localhost:8000/docs
- ReDoc UI: http://localhost:8000/redoc

## 故障排查

### 服务无法启动
```bash
# 检查日志
tail -100 /tmp/claude-bot-optimized.log

# 检查端口占用
lsof -i:8000

# 检查飞书配置
cat .env | grep FEISHU
```

### 无法连接飞书
```bash
# 检查飞书应用配置
echo "APP_ID: $FEISHU_APP_ID"
echo "APP_SECRET: $FEISHU_APP_SECRET"

# 查看连接日志
grep -i "连接\|connect" /tmp/claude-bot-optimized.log
```

### 消息收发异常
```bash
# 查看错误日志
grep -i error /tmp/claude-bot-optimized.log | tail -20

# 查看权限错误
grep -i permission /tmp/claude-bot-optimized.log
```

## 下一步优化

1. **完善 Claude 集成**
   - 实现完整的会话管理
   - 添加多轮对话支持
   - 实现信息补充流程

2. **增强功能**
   - 添加群组管理 API
   - 实现动态 Agent 配置
   - 添加文件上传/下载

3. **监控和告警**
   - 添加 Prometheus 指标
   - 实现健康检查
   - 配置日志收集

4. **测试和文档**
   - 编写单元测试
   - 更新 API 文档
   - 完善部署文档
