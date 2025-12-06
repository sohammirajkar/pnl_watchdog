import sys
import os
import pkgutil
import importlib
import traceback

# Add the current directory and the library source to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
lib_src_dir = os.path.join(current_dir, "pnl_watchdog_lib", "src")
sys.path.insert(0, current_dir)
sys.path.insert(0, lib_src_dir)

print(f"Checking imports with sys.path: {sys.path}")

def check_import(module_name):
    try:
        importlib.import_module(module_name)
        print(f"✅ Successfully imported {module_name}")
        return True
    except Exception as e:
        print(f"❌ Failed to import {module_name}: {e}")
        traceback.print_exc()
        return False

print("\n--- Checking main.py ---")
# main.py is not a package, so we import it by filename (without .py)
# But since it's in the current directory, we can just import 'main'
check_import("main")

print("\n--- Checking pnl_watchdog package ---")
if check_import("pnl_watchdog"):
    # Walk through the package
    import pnl_watchdog
    package_path = os.path.dirname(pnl_watchdog.__file__)
    
    for root, dirs, files in os.walk(package_path):
        for file in files:
            if file.endswith(".py") and file != "__init__.py":
                # Construct module name
                rel_path = os.path.relpath(os.path.join(root, file), lib_src_dir)
                module_name = rel_path.replace(os.path.sep, ".")[:-3]
                check_import(module_name)
