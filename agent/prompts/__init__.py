"""
Prompts for Claude Agent SDK based consensus bug hunter
"""

from .constraints import BFT_CONSTRAINT, CFT_CONSTRAINT, get_constraint_for_protocol
from .orchestrator import (
    ORCHESTRATOR_SYSTEM_PROMPT,
    get_orchestrator_prompt,
)
from .strategy import (
    BUG_EXPLOITATION_SYSTEM_PROMPT,
    STRATEGY_SYSTEM_PROMPT,
    get_bug_exploitation_prompt,
    get_strategy_prompt,
)
from .testgen import (
    TESTGEN_SYSTEM_PROMPT,
    get_testgen_prompt,
    get_testgen_system_prompt,
)

__all__ = [
    "STRATEGY_SYSTEM_PROMPT",
    "BUG_EXPLOITATION_SYSTEM_PROMPT",
    "ORCHESTRATOR_SYSTEM_PROMPT",
    "TESTGEN_SYSTEM_PROMPT",
    "get_testgen_system_prompt",
    "CFT_CONSTRAINT",
    "BFT_CONSTRAINT",
    "get_strategy_prompt",
    "get_bug_exploitation_prompt",
    "get_orchestrator_prompt",
    "get_testgen_prompt",
    "get_constraint_for_protocol",
]
