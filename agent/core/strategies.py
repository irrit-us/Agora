"""
Strategy interfaces for pluggable components.

This module defines abstract interfaces that allow different implementations
to be injected into the Orchestrator, enabling clean ablation experiments
without code duplication.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class StrategyContext:
    """Context provided to strategy generators."""
    
    protocol_name: str
    protocol_type: str  # "cft" or "bft"
    protocol_language: str
    protocol_description: str
    
    # Previous strategies that were rejected (for avoiding duplicates)
    rejected_strategies: list[str] = field(default_factory=list)
    rejected_pattern_ids: list[str] = field(default_factory=list)
    
    # Repository context
    repo_context: str = ""
    
    # Bug pattern context (for pattern-based strategies)
    pattern_context: str = ""
    allowed_patterns: dict[str, str] = field(default_factory=dict)
    
    # Constraint text for this protocol type
    constraint: str = ""


@dataclass
class AttackScenario:
    """Parsed attack scenario from Strategy Agent."""
    
    name: str
    target_component: str
    vulnerability_hypothesis: str
    attack_category: str  # safety/liveness/agreement
    preconditions: list[str]
    steps: list[str]
    expected_bug_behavior: str
    correct_behavior: str
    assertions: list[str]
    thinking_chain: str  # Full thinking process
    inspiration_source: str = ""  # pattern_memory/original


@dataclass
class TestResult:
    """Result from TestGen Agent."""
    
    success: bool
    test_code: str
    test_file: str
    test_output: str
    result: str = ""  # "PASS" / "FAIL" / "ERROR"
    error: str = ""
    passed: bool = False


class StrategyGenerator(ABC):
    """
    Abstract interface for attack scenario generation.
    
    Implementations can provide different ways to generate attack scenarios:
    - DefaultStrategyGenerator: Uses Strategy Agent with LLM
    - PatternOnlyGenerator: Uses only pattern memory
    """
    
    @abstractmethod
    async def generate(self, context: StrategyContext) -> AttackScenario | None:
        """
        Generate an attack scenario.
        
        Args:
            context: Strategy generation context.
            
        Returns:
            AttackScenario or None if generation failed.
        """
        pass
    
    @abstractmethod
    def get_token_usage(self) -> dict[str, Any]:
        """Get token usage from the last generation."""
        pass


class ExploitationHandler(ABC):
    """
    Abstract interface for bug exploitation.
    
    Implementations can provide different exploitation strategies:
    - DefaultExploitationHandler: Full exploitation with Strategy Agent
    - NullExploitationHandler: No exploitation (for ablation)
    """
    
    @abstractmethod
    async def exploit(
        self,
        original_scenario: AttackScenario,
        original_result: TestResult,
        context: StrategyContext,
        max_attempts: int,
    ) -> list[tuple[AttackScenario, TestResult | None]]:
        """
        Exploit a confirmed bug to find related vulnerabilities.
        
        Args:
            original_scenario: The scenario that triggered the bug.
            original_result: Test result from the bug.
            context: Strategy context.
            max_attempts: Maximum exploitation attempts.
            
        Returns:
            List of (scenario, test_result) tuples for each exploitation attempt.
        """
        pass
    
    @abstractmethod
    def get_token_usage(self) -> dict[str, Any]:
        """Get cumulative token usage from exploitation."""
        pass


class NullExploitationHandler(ExploitationHandler):
    """
    No-op exploitation handler for ablation experiments.
    
    Simply returns empty results without doing any exploitation.
    """
    
    async def exploit(
        self,
        original_scenario: AttackScenario,
        original_result: TestResult,
        context: StrategyContext,
        max_attempts: int,
    ) -> list[tuple[AttackScenario, TestResult | None]]:
        """No exploitation - returns empty list."""
        return []
    
    def get_token_usage(self) -> dict[str, Any]:
        """No tokens used."""
        return {}
