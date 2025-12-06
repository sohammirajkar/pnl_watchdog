import sys
print(f"Python executable: {sys.executable}")
print(f"sys.path: {sys.path}")

try:
    import pnl_core
    print("✅ Successfully imported pnl_core")
    print(f"pnl_core file: {pnl_core.__file__}")
except ImportError as e:
    print(f"❌ Failed to import pnl_core: {e}")

try:
    import pnl_watchdog
    print("✅ Successfully imported pnl_watchdog")
    print(f"pnl_watchdog file: {pnl_watchdog.__file__}")
except ImportError as e:
    print(f"❌ Failed to import pnl_watchdog: {e}")
