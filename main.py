"""Compatibility wrapper for the CMMS Local AI API.

The application now lives in app.main. This wrapper preserves existing
commands such as:

    uvicorn main:app --host 127.0.0.1 --port 8000

It also makes `import main` resolve to the real implementation module so
existing smoke tests and monkeypatches continue to behave as before.
"""

from importlib import import_module
import sys

_implementation = import_module("app.main")
sys.modules[__name__] = _implementation
