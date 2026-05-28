"""
Core modules for the Consensus Bug Hunter.

- orchestrator: Main controller for coordinated multi-agent bug hunting
- agent_factory: Creates agents with their tools
- pattern_tracker: Tracks bug pattern usage per protocol
- executor: Code and command executor with robust error handling
- tool_agent: Self-built Tool Calling Agent implementation
- strategies: Pluggable strategy interfaces for flexible agent behavior
- prompt_builder: Centralized prompt construction
- result_parser: Centralized response parsing
- report_generator: Bug report and pattern generation
"""

from .agent_factory import AgentFactory
from .executor import ExecutionResult, Executor, format_error_for_reflection
from .orchestrator import Orchestrator, create_orchestrator
from .pattern_tracker import PatternTracker
from .prompt_builder import PromptBuilder
from .report_generator import ReportGenerator
from .result_parser import ResultParser
from .strategies import (
    AttackScenario,
    ExploitationHandler,
    NullExploitationHandler,
    StrategyContext,
    StrategyGenerator,
    TestResult,
)
from .strategy_impl import (
    DefaultExploitationHandler,
    DefaultStrategyGenerator,
)
from .tool_agent import AgentResponse, Tool, ToolAgent, create_tool, tool

__all__ = [
    # Orchestrator
    "Orchestrator",
    "create_orchestrator",
    # Agent Factory
    "AgentFactory",
    # Pattern Tracker
    "PatternTracker",
    # Strategies
    "StrategyContext",
    "AttackScenario",
    "TestResult",
    "StrategyGenerator",
    "ExploitationHandler",
    "NullExploitationHandler",
    # Strategy Implementations
    "DefaultStrategyGenerator",
    "DefaultExploitationHandler",
    # Prompt Builder
    "PromptBuilder",
    # Result Parser
    "ResultParser",
    # Report Generator
    "ReportGenerator",
    # Executor
    "Executor",
    "ExecutionResult",
    "format_error_for_reflection",
    # Tool Agent
    "ToolAgent",
    "Tool",
    "create_tool",
    "tool",
    "AgentResponse",
]
