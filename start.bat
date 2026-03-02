@echo off
REM 飞书 + Claude 智能对话服务启动脚本
REM 同时启动主服务（FastAPI）和长连接服务

echo ========================================
echo 飞书 + Claude 智能对话服务
echo ========================================
echo.

echo [1/2] 启动主服务 (FastAPI)...
start "" python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --log-level info
REM 使用 start "" 来在新窗口中运行

echo.
echo [2/2] 启动长连接服务...
start "" python src/feishu/long_connection_service.py

echo.
echo ========================================
echo 服务已启动！
echo.
echo 主服务: http://localhost:8000
echo API 文档: http://localhost:8000/docs
echo.
echo 按任意键关闭此窗口（服务将继续运行）...
pause
