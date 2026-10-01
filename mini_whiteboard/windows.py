"""Compatibility alias for existing Windows diagnostics and tester scripts.

Shared application code uses platform services. Keep one module object so older
diagnostics that patch a native function still exercise the real adapter.
"""
import sys
from .platform.windows import native

sys.modules[__name__] = native
