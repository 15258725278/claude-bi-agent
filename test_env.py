"""
测试环境变量配置
"""
import os
import sys

# Windows 终端编码问题，设置标准输出编码
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

print("=" * 50)
print("Feishu + Claude Bot - Environment Check")
print("=" * 50)
print()

# 检查必要的环境变量
env_vars = {
    "FEISHU_APP_ID": os.getenv("FEISHU_APP_ID"),
    "FEISHU_APP_SECRET": os.getenv("FEISHU_APP_SECRET"),
    "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY"),
    "ANTHROPIC_BASE_URL": os.getenv("ANTHROPIC_BASE_URL"),
    "DATABASE_URL": os.getenv("DATABASE_URL"),
    "REDIS_URL": os.getenv("REDIS_URL"),
    "MAIN_SERVICE_URL": os.getenv("MAIN_SERVICE_URL", "http://localhost:8000"),
}

all_ok = True
for var, value in env_vars.items():
    status = "[OK]" if value else "[MISSING]"
    display_value = value if value else "(not set)"
    print(f"{status} {var:30s}: {display_value}")
    if not value:
        all_ok = False

print()
if all_ok:
    print("[OK] All required environment variables are set")
    print()
    print("Main service start command:")
    print("  python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --log-level info")
    print()
    print("Long connection service start command:")
    print("  python src/feishu/long_connection_service.py")
    print()
    print("Or use startup script:")
    print("  start.bat")
else:
    print("[ERROR] Some environment variables are not set, please check .env file")

print("=" * 50)
