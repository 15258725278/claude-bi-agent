"""
Simple service test script
"""
import sys

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

print("=" * 60)
print("Feishu + Claude Bot Service Test")
print("=" * 60)
print()

# Test 1: Check Python version
print("[1/4] Checking Python version...")
import sys
print(f"Python version: {sys.version}")
print()

# Test 2: Try importing modules
print("[2/4] Testing module imports...")
try:
    from src.claude import ClaudeSessionFactory, ClaudeSessionManager
    print("  - claude module: OK")
    from src.claude import FeishuToolsManager, create_simple_echo_tool
    print("  - tools module: OK")
    print("  Module imports: Success")
except Exception as e:
    print(f"  - Module imports failed: {e}")
    sys.exit(1)

print()
print("[3/4] Service status...")
print("Current architecture (simplified):")
print("  - Main service: FastAPI app")
print("  - Long connection: Standalone process (to be implemented)")
print("  - Claude SDK: Simplified integration (basic tools)")
print()

print("[4/4] Next steps...")
print("  1. Implement basic Feishu message send/receive")
print("  2. Implement interaction with Claude API")
print("  3. Implement session management")
print("  4. Test complete conversation flow")
print()
print("=" * 60)
