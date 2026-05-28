"""
Constants used across the agent modules.

This module defines common constants to avoid magic strings and ensure consistency.
"""

from enum import Enum

# ============================================================
# Bug Categories
# ============================================================

# Bug categories for consensus protocol testing
BUG_CATEGORY_SAFETY = "safety"
BUG_CATEGORY_LIVENESS = "liveness"
BUG_CATEGORY_AGREEMENT = "agreement"

BUG_CATEGORIES = frozenset({
    BUG_CATEGORY_SAFETY,
    BUG_CATEGORY_LIVENESS,
    BUG_CATEGORY_AGREEMENT,
})


# ============================================================
# Bug Statuses
# ============================================================

# Status values for bug records
BUG_STATUS_OPEN = "open"
BUG_STATUS_CONFIRMED = "confirmed"
BUG_STATUS_FIXED = "fixed"
BUG_STATUS_WONTFIX = "wontfix"
BUG_STATUS_UNVERIFIED = "unverified"

BUG_STATUSES = frozenset({
    BUG_STATUS_OPEN,
    BUG_STATUS_CONFIRMED,
    BUG_STATUS_FIXED,
    BUG_STATUS_WONTFIX,
    BUG_STATUS_UNVERIFIED,
})


# ============================================================
# Protocol Types
# ============================================================

# Protocol fault tolerance types
PROTOCOL_TYPE_CFT = "cft"
PROTOCOL_TYPE_BFT = "bft"

PROTOCOL_TYPES = frozenset({
    PROTOCOL_TYPE_CFT,
    PROTOCOL_TYPE_BFT,
})


# ============================================================
# Enum Classes (alternative style for type-safe usage)
# ============================================================


class BugCategory(str, Enum):
    """Bug category enumeration."""
    SAFETY = "safety"
    LIVENESS = "liveness"
    AGREEMENT = "agreement"


class BugStatus(str, Enum):
    """Bug status enumeration."""
    OPEN = "open"
    CONFIRMED = "confirmed"
    FIXED = "fixed"
    WONTFIX = "wontfix"
    UNVERIFIED = "unverified"


class ProtocolType(str, Enum):
    """Protocol type enumeration."""
    CFT = "cft"
    BFT = "bft"
