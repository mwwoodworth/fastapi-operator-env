#!/usr/bin/env python3
"""Test script to verify all imports work correctly."""

import sys
print(f"Python version: {sys.version}")
print(f"Python path: {sys.path}")

try:
    from core.config import settings
    print("✓ Config imported successfully")
    print(f"  - PORT: {settings.PORT}")
except Exception as e:
    print(f"✗ Config import failed: {e}")

try:
    from main import app
    print("✓ FastAPI app imported successfully")
except Exception as e:
    print(f"✗ FastAPI app import failed: {e}")

try:
    from services.assistant import AssistantService
    print("✓ AssistantService imported successfully")
except Exception as e:
    print(f"✗ AssistantService import failed: {e}")

try:
    from services.memory import MemoryService
    print("✓ MemoryService imported successfully")
except Exception as e:
    print(f"✗ MemoryService import failed: {e}")

print("\nAll import tests completed!")