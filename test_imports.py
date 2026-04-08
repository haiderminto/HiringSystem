#!/usr/bin/env python3
"""Test script to verify all imports work without errors."""

import sys
import traceback

def test_import(module_name):
    """Test if a module can be imported."""
    try:
        __import__(module_name)
        print(f"✓ {module_name}")
        return True
    except Exception as e:
        print(f"✗ {module_name}: {type(e).__name__}: {e}")
        traceback.print_exc()
        return False

print("Testing imports...\n")

modules_to_test = [
    "config",
    "utils.storage",
    "utils.pdf_utils",
    "utils.file_converter",
    "utils.markdown_converter",
    "utils.llm_client",
    "utils.observability",
    "agents.state",
    "agents.prompts.jd_extraction",
    "agents.prompts.resume_evaluation",
    "agents.nodes.file_intake",
    "agents.nodes.jd_extraction",
    "agents.nodes.resume_evaluation",
    "agents.graph",
    "main",
]

results = []
for mod in modules_to_test:
    results.append(test_import(mod))

print(f"\n{sum(results)}/{len(results)} imports successful")

if not all(results):
    print("\nFix the errors above before starting the server.")
    sys.exit(1)
else:
    print("\nAll imports successful! Server should start.")
