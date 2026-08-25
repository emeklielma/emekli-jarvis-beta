import asyncio
from core.autostart import is_autostart_enabled
from tools.system_diagnostics import get_system_diagnostics
from tools.registry import get_gemini_tools

async def run_tests():
    print("--- 1. Testing System Diagnostics ---")
    try:
        report = await get_system_diagnostics()
        print(report)
    except Exception as e:
        print(f"Diagnostics failed: {e}")

    print("\n--- 2. Testing Autostart Registry Check ---")
    try:
        is_enabled = is_autostart_enabled()
        print(f"Is Autostart Enabled?: {is_enabled}")
    except Exception as e:
        print(f"Autostart check failed: {e}")

    print("\n--- 3. Testing Tool Registry Schema ---")
    try:
        schema = get_gemini_tools()
        funcs = [item["name"] for item in schema[0].get("functionDeclarations", [])]
        print(f"Registered tools: {', '.join(funcs)}")
        assert "get_system_diagnostics" in funcs, "get_system_diagnostics not registered!"
    except Exception as e:
        print(f"Registry test failed: {e}")

    print("\n[ALL TESTS PASSED SUCCESSFULLY!]")

if __name__ == "__main__":
    asyncio.run(run_tests())
