# test_id.py
import sys
import os

# Ensure Python finds your local code (fixes "ModuleNotFoundError")
sys.path.insert(0, os.path.abspath("src"))

try:
    from pnl_watchdog import PnLWatchdog
    print("✅ Import successful!")

    # Initialize the dog
    dog = PnLWatchdog(broker='alpaca', api_key='test', api_secret='test')

    print("\n" + "="*30)
    print(f"🎉 SUCCESS! ID: {dog.user_id}")
    print("="*30 + "\n")

except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
