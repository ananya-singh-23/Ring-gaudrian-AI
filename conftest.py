"""Pytest configuration: ensure the project root is importable.

This makes `import simulator`, `import alert_engine`, etc. work when
running `py -m pytest` from the project root, regardless of import mode.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
