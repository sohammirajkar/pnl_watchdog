import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
try:
    import pnl_core
    print("Successfully imported pnl_core")
    print(dir(pnl_core))
except ImportError as e:
    print(f"Failed to import pnl_core: {e}")
except Exception as e:
    print(f"An error occurred: {e}")
