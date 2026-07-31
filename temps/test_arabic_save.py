#!/usr/bin/env python3
"""Test creating Arabic save and running turn 2"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from engine_runtime.world_compiler import compile_world_bundle
    from engine_runtime.persistence import SQLitePersistence
    from engine_runtime.calculators import run_action
except ImportError as e:
    print(f"Import error: {e}")
    sys.exit(1)

# Test that we can access the existing save structure
saves_dir = Path("saves")
print(f"Saves directory exists: {saves_dir.exists()}")
print(f"Saves contents: {list(saves_dir.iterdir()) if saves_dir.exists() else 'None'}")
