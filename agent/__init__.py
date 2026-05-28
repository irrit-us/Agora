"""
Distributed Protocol Bug Hunter - Multi-Agent System
"""

__version__ = "0.1.0"

# Export constants for convenience
from .constants import (
    BUG_CATEGORIES,
    BUG_CATEGORY_AGREEMENT,
    BUG_CATEGORY_LIVENESS,
    BUG_CATEGORY_SAFETY,
    BUG_STATUS_CONFIRMED,
    BUG_STATUS_FIXED,
    BUG_STATUS_OPEN,
    BUG_STATUS_UNVERIFIED,
    BUG_STATUS_WONTFIX,
    BUG_STATUSES,
    PROTOCOL_TYPE_BFT,
    PROTOCOL_TYPE_CFT,
    PROTOCOL_TYPES,
    BugCategory,
    BugStatus,
    ProtocolType,
)

__all__ = [
    "__version__",
    # Bug categories
    "BUG_CATEGORY_SAFETY",
    "BUG_CATEGORY_LIVENESS",
    "BUG_CATEGORY_AGREEMENT",
    "BUG_CATEGORIES",
    # Bug statuses
    "BUG_STATUS_OPEN",
    "BUG_STATUS_CONFIRMED",
    "BUG_STATUS_FIXED",
    "BUG_STATUS_WONTFIX",
    "BUG_STATUS_UNVERIFIED",
    "BUG_STATUSES",
    # Protocol types
    "PROTOCOL_TYPE_CFT",
    "PROTOCOL_TYPE_BFT",
    "PROTOCOL_TYPES",
    # Enum classes
    "BugCategory",
    "BugStatus",
    "ProtocolType",
]
