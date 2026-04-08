#!/usr/bin/env python3
"""Debug script - run this to find the actual error."""

import sys
import traceback
import os

print("=" * 60)
print("ATS Resume Evaluator - Debug & Diagnostics")
print("=" * 60)

# Check 1: Can we import everything?
print("\n[1] Testing imports...")
try:
    import config
    print("✓ config")
except Exception as e:
    print(f"✗ config: {e}")
    traceback.print_exc()
    sys.exit(1)

try:
    import utils.storage
    print("✓ utils.storage")
except Exception as e:
    print(f"✗ utils.storage: {e}")
    traceback.print_exc()
    sys.exit(1)

try:
    import utils.llm_client
    print("✓ utils.llm_client")
except Exception as e:
    print(f"✗ utils.llm_client: {e}")
    traceback.print_exc()
    sys.exit(1)

try:
    import agents.state
    print("✓ agents.state")
except Exception as e:
    print(f"✗ agents.state: {e}")
    traceback.print_exc()
    sys.exit(1)

try:
    import agents.graph
    print("✓ agents.graph")
except Exception as e:
    print(f"✗ agents.graph: {e}")
    traceback.print_exc()
    sys.exit(1)

try:
    import main
    print("✓ main (FastAPI app)")
except Exception as e:
    print(f"✗ main: {e}")
    traceback.print_exc()
    sys.exit(1)

# Check 2: Settings validation
print("\n[2] Checking .env configuration...")
from config import settings

print(f"  LLM_PROVIDER: {settings.llm_provider}")
print(f"  Using: {'OpenAI' if settings.is_openai else 'Anthropic'}")

api_key = settings.active_api_key
if not api_key:
    print("  ✗ No API key configured!")
    sys.exit(1)
elif api_key.endswith("here"):
    print("  ✗ API key is placeholder (ends with 'here')")
    sys.exit(1)
else:
    print(f"  ✓ API key present: {api_key[:20]}...")

# Check 3: Directories
print("\n[3] Checking directories...")
os.makedirs(settings.upload_dir, exist_ok=True)
os.makedirs(settings.results_dir, exist_ok=True)
print(f"  ✓ uploads/ exists")
print(f"  ✓ results/ exists")

# Check 4: FastAPI app
print("\n[4] Checking FastAPI app...")
try:
    from main import app
    print("  ✓ FastAPI app created")
    print(f"  ✓ Routes: {len(app.routes)} registered")
except Exception as e:
    print(f"  ✗ Failed to create app: {e}")
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 60)
print("All checks passed! App should start.")
print("=" * 60)
print("\nTo start the server, run:")
print("  python main.py")
print("\nThen open http://localhost:8000 in your browser")
