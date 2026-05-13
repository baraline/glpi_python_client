"""Internal GLPI v2 client implementation packages.

The v2 client implementation is split by responsibility: shared helpers live
under ``common`` while execution-model-specific mixins live under ``sync`` and
``async_``.
"""

from __future__ import annotations
