#!/usr/bin/env python3
"""
Script to generate OpenAPI documentation.
Run this to create API docs in multiple formats.
"""

import sys
import os
from pathlib import Path

# Add backend directory to Python path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from openapi_generator import generate_openapi_docs

if __name__ == "__main__":
    try:
        files = generate_openapi_docs()
        print("\n✅ Documentation generation complete!")
    except Exception as e:
        print(f"\n❌ Error generating documentation: {e}")
        sys.exit(1)