import sys
try:
    import pnl_core
    print(f"✅ Rust Core Loaded: {pnl_core}")
    # Using correct function from lib.rs inspection
    lambda_val = pnl_core.calculate_kyle_lambda_asset_specific("EQUITIES", 100.0, 0.02, 100000.0)
    print(f"   Function Verification (Kyle's Lambda): {lambda_val:.6f}")
except ImportError as e:
    print(f"❌ Rust Core Failed to Load: {e}")
except AttributeError as e:
    print(f"❌ Function Not Found: {e}")
except Exception as e:
    print(f"❌ Unexpected Error: {e}")
