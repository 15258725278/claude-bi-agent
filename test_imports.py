# Simple module import test
print("Testing module imports...")

try:
    from src.claude import ClaudeSessionFactory, ClaudeSessionManager
    from src.claude import FeishuToolsManager, create_simple_echo_tool
    print("Module imports: OK")
except Exception as e:
    print(f"Module imports failed: {e}")

print("Done")
