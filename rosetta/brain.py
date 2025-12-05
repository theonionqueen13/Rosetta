"""A lightweight brain that builds structured context from lookup data.

The original monolithic implementation has been split into smaller modules:

- ``brain_constants``: lookup tables imported from :mod:`rosetta.lookup`.
- ``brain_helpers``: shared helper utilities and DataFrame access helpers.
- ``brain_context``: object/aspect context assembly logic.
- ``brain_global``: dispositor, compass, and shape summaries.
- ``brain_stars``: fixed star catalog loading and matching.
- ``brain_gemini``: minimal Gemini wrapper helpers.
"""

from __future__ import annotations

import rosetta.brain_constants as brain_constants
import rosetta.brain_context as brain_context
import rosetta.brain_gemini as brain_gemini
import rosetta.brain_global as brain_global
import rosetta.brain_helpers as brain_helpers
import rosetta.brain_stars as brain_stars

from rosetta.brain_constants import *  # noqa: F401,F403
from rosetta.brain_context import *  # noqa: F401,F403
from rosetta.brain_gemini import *  # noqa: F401,F403
from rosetta.brain_global import *  # noqa: F401,F403
from rosetta.brain_helpers import *  # noqa: F401,F403
from rosetta.brain_stars import *  # noqa: F401,F403

__all__ = []  # populated by the imported modules
for _mod in (
    brain_constants,
    brain_context,
    brain_gemini,
    brain_global,
    brain_helpers,
    brain_stars,
):
    __all__.extend(getattr(_mod, "__all__", []))
