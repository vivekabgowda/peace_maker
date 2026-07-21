"""Alpha Scanner subsystem (Sprint 3, Steps 1, 3, 5, 6).

Importing this package registers every strategy plugin and exposes the regime
types. The heavier orchestration types (``AlphaScanner``, ``ContextBuilder``,
``Opportunity``) are imported from their submodules directly to keep the package
``__init__`` free of the scanner→ai_engine→scanner import cycle:

    from app.modules.scanner.engine import AlphaScanner, RegimeInputs
    from app.modules.scanner.context import ContextBuilder
    from app.modules.scanner.opportunity import Opportunity, OpportunityBook
"""

from __future__ import annotations

import app.modules.strategy.library  # noqa: F401  (registers strategy plugins)
from app.modules.scanner.regime import RegimeEngine, RegimeState

__all__ = ["RegimeEngine", "RegimeState"]
