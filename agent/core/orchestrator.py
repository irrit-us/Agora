"""
Orchestrator - Main controller for the Consensus Bug Hunter.

Uses self-built ToolAgent for coordinated multi-agent bug hunting.

Architecture:
- Orchestrator: Controls flow, dispatches agents, records results
- Strategy Agent: Generates attack strategies (context injected by orchestrator)
- TestGen Agent: Implements tests (repo access, code execution)

The Orchestrator uses pluggable components for clean separation of concerns:
- AgentFactory: Creates agents with their tools
- PatternTracker: Tracks bug pattern usage
- PromptBuilder: Centralized prompt construction
- ResultParser: Response parsing and extraction
- ReportGenerator: Bug report and pattern generation
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..memory.pattern_memory import BugPattern

from ..config.settings import ProtocolConfig, Settings, load_settings
from ..mcp_servers.memory_server import MemoryServer, create_memory_server
from ..memory.llm_logs import create_llm_logger, get_action_logger, get_llm_logger
from ..memory.test_history import BugRecord, TestHistory
from ..prompts import get_constraint_for_protocol
from ..utils.metrics import MetricsTracker
from ..utils.token_usage import TokenUsage
from .agent_factory import AgentFactory
from .executor import Executor
from .pattern_tracker import PatternTracker
from .prompt_builder import ATTACK_SCENARIO_FORMAT, PromptBuilder
from .report_generator import ReportGenerator
from .result_parser import ResultParser
from .strategies import AttackScenario, StrategyContext, TestResult

logger = logging.getLogger(__name__)


# ============================================================
# Constants
# ============================================================

# Fatal error patterns that should terminate the workflow immediately
FATAL_ERROR_PATTERNS = [
    "402",  # Payment Required (insufficient credits)
    "Payment Required",
    "401",  # Unauthorized (invalid API key)
    "Unauthorized",
]

# Transient error patterns that are safe to retry at the orchestrator level
TRANSIENT_ERROR_PATTERNS = [
    "RemoteProtocolError",
    "ProtocolError",
    "Protocol error",
    "Connection failed",
    "timeout",
    "Timeout",
    "empty_response_after_retries",
    "incomplete chunked read",
    "peer closed connection",
]


# ============================================================
# Data Classes
# ============================================================


@dataclass
class IterationResult:
    """Result of one complete iteration."""

    iteration: int
    protocol: str
    scenario: AttackScenario | None = None
    test_result: TestResult | None = None
    error: str | None = None
    duration_ms: int = 0
    protocol_complete: bool = False
    bugs_found: int = 0
    token_usage: dict[str, Any] = field(default_factory=dict)


# ============================================================
# Orchestrator
# ============================================================


class Orchestrator:
    """
    Main orchestrator for the Consensus Bug Hunter.

    Uses self-built ToolAgent architecture with:
    - Strategy Agent: Context-injected prompts for attack scenario generation
    - TestGen Agent: Repository access, code execution, test writing

    Components:
    - AgentFactory: Creates agents with their tools
    - PatternTracker: Tracks bug pattern usage
    - PromptBuilder: Centralized prompt construction
    - ResultParser: Response parsing and extraction
    - ReportGenerator: Bug report and pattern generation
    """

    def __init__(
        self,
        protocol_config: ProtocolConfig,
        settings: Settings,
        memory_server: MemoryServer | None = None,
    ):
        self.protocol = protocol_config
        self.settings = settings

        # Initialize memory server
        if memory_server:
            self.memory = memory_server
        else:
            self.memory = create_memory_server(
                api_key=settings.openrouter_api_key if settings.use_embedding else None
            )

        # Resolve repository root
        protocol_name = self._get_protocol_attr("name", "unknown")
        protocol_path = self._get_protocol_attr("path", ".")

        # Find project root (parent of agent/ directory)
        self.project_root = Path(__file__).parent.parent.parent.resolve()

        # Resolve protocol repository path
        self.repo_root = self._resolve_repo_root(protocol_name, protocol_path)
        logger.info(f"Repository root for '{protocol_name}': {self.repo_root}")

        # Initialize executor
        self.executor = Executor(
            working_dir=self.repo_root,
            timeout=settings.test_timeout,
            enforce_working_dir=True,
        )

        # Initialize LLM logger (context-aware for parallel execution)
        # If a logger is already set in the current context (e.g., by ablation experiment),
        # use that logger. Otherwise, create a new one.
        existing_logger = get_llm_logger()
        if existing_logger._action_logger.protocol:
            # Context already has a configured logger, use it
            self.llm_logger = existing_logger
        else:
            # No existing logger, create one for this orchestrator
            self.llm_logger = create_llm_logger(
                protocol=protocol_name,
                base_path=Path(__file__).parent.parent / "data" / "test_history",
            )

        # Initialize pattern tracker
        self.pattern_tracker = PatternTracker()

        # Initialize test history
        test_history_path = Path(__file__).parent.parent / "data" / "test_history"
        self.test_history = TestHistory(test_history_path)

        # Initialize report generator
        self.report_generator = ReportGenerator(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
            model=settings.llm_model,
        )

        # Initialize metrics tracker for structured experiment data
        self.metrics = MetricsTracker(
            protocol=protocol_name,
            model=settings.llm_model,
            base_path=test_history_path,
        )

        # Create agent factory
        self._agent_factory = AgentFactory(
            model=settings.llm_model,
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
            max_tokens=settings.max_thinking_tokens,
            repo_root=self.repo_root,
            executor=self.executor,
            memory=self.memory,
            protocol_name=protocol_name,
            protocol_type=self._get_protocol_attr("type", "cft"),
            protocol_language=self._get_protocol_attr("language", "go"),
            log_callback=self._log_llm_interaction,
            metrics_callback=self._record_metrics_api_call,
        )
        
        # Set pattern tracking callbacks
        self._agent_factory.set_pattern_callbacks(
            mark_viewed=self.pattern_tracker.mark_viewed,
            is_used=self.pattern_tracker.is_used,
        )

        # Create agents
        self.strategy_agent = self._agent_factory.create_strategy_agent()
        self.testgen_agent = self._agent_factory.create_testgen_agent()

        # Statistics
        self.iterations_completed = 0
        self.bugs_found = 0
        self.errors_encountered = 0

        # Token usage tracking
        self.total_token_usage = TokenUsage()
        self.tokens_since_last_bug = TokenUsage()

        # Current agent type label for metrics (set before each agent.run())
        self._current_agent_type: str = "unknown"
        
        # Instance-level rejection context builder (can be overridden by subclasses)
        # This allows ablation experiments to customize behavior without monkey-patching
        self._rejection_context_enabled = True

    async def close(self):
        """Close and cleanup resources."""
        if hasattr(self, 'strategy_agent') and self.strategy_agent:
            await self.strategy_agent.close()
        if hasattr(self, 'testgen_agent') and self.testgen_agent:
            await self.testgen_agent.close()
        if hasattr(self, 'report_generator') and self.report_generator:
            await self.report_generator.close()
        logger.debug("[Orchestrator] Resources cleaned up")

    def _resolve_repo_root(self, protocol_name: str, protocol_path: str) -> Path:
        """Resolve the repository root path."""
        if protocol_path.startswith("./"):
            protocol_path = protocol_path[2:]

        resolved = self.project_root / protocol_path
        if not resolved.exists():
            raise ValueError(f"Repository not found: {resolved}")

        return resolved.resolve()

    def _log_llm_interaction(self, data: dict):
        """Callback for logging LLM interactions."""
        if self.llm_logger:
            self.llm_logger.log(data)

    def _record_metrics_api_call(self, data: dict):
        """Callback from ToolAgent._call_llm() — records each API call to MetricsTracker."""
        self.metrics.record_api_call(
            agent_type=self._current_agent_type,
            model=data.get("model", ""),
            usage=data.get("usage", {}),
            duration_ms=data.get("duration_ms", 0),
            success=data.get("success", True),
            error=data.get("error"),
            generation_id=data.get("generation_id"),
        )

    # ==================== Helper Methods ====================

    def _get_attr(self, obj: Any, attr: str, default: str = "") -> str:
        """Safely get an attribute from an object that may be a dict or dataclass."""
        if isinstance(obj, dict):
            return obj.get(attr, default)
        return getattr(obj, attr, default)

    def _get_protocol_attr(self, attr: str, default: str = "") -> str:
        """Safely get protocol attribute."""
        return self._get_attr(self.protocol, attr, default)

    def _get_scenario_attr(self, scenario: Any, attr: str, default: str = "") -> str:
        """Safely get scenario attribute."""
        return self._get_attr(scenario, attr, default)

    def _get_repo_key(self) -> str:
        """Get normalized repository key for memory lookups."""
        return self._get_protocol_attr("name", "unknown").lower()

    def _build_rejection_context(
        self,
        rejected_strategies: list[str],
        rejected_pattern_ids: list[str],
    ) -> str:
        """
        Build rejection context for strategy generation.
        
        This is an instance method that can be overridden by subclasses
        (e.g., StatelessOrchestrator) to customize behavior without
        affecting other concurrent Orchestrator instances.
        
        Args:
            rejected_strategies: Previously rejected strategy descriptions.
            rejected_pattern_ids: Pattern IDs that must not be reused.
            
        Returns:
            Context string or empty string.
        """
        if not self._rejection_context_enabled:
            return ""
        return PromptBuilder.build_rejection_context(rejected_strategies, rejected_pattern_ids)

    def _get_constraint(self) -> str:
        """
        Get protocol constraint for strategy generation.
        
        This is an instance method that can be overridden by subclasses
        (e.g., NoTypeDistinctionOrchestrator) to customize the constraint
        without affecting other concurrent Orchestrator instances.
        
        Returns:
            Constraint string for strategy generation.
        """
        return get_constraint_for_protocol(self._get_protocol_attr("type", "cft"))

    def _get_test_file_globs(self) -> list[str]:
        """Build glob patterns for locating test files in the repo."""
        patterns: list[str] = []
        config_pattern = self._get_protocol_attr("test_pattern", "")
        if config_pattern:
            if not config_pattern.startswith("**/") and "/" not in config_pattern:
                config_pattern = f"**/{config_pattern}"
            patterns.append(config_pattern)

        language = self._get_protocol_attr("language", "go").lower()
        if language == "go":
            patterns += ["**/*_test.go", "**/tests/**/*.go", "**/test/**/*.go"]
        elif language == "rust":
            patterns += ["**/*_test.rs", "**/tests/**/*.rs"]
        elif language == "java":
            patterns += ["**/*Test.java", "**/*Tests.java", "**/tests/**/*.java", "**/test/**/*.java"]
        elif language == "python":
            patterns += ["**/test_*.py", "**/*_test.py", "**/tests/**/*.py"]
        elif language in ("cpp", "c++"):
            patterns += ["**/*_tests.cpp", "**/test/**/*_tests.cpp", "**/src/test/**/*.cpp"]
        else:
            patterns += ["**/*_test.*", "**/tests/**/*"]

        # Deduplicate while preserving order
        seen = set()
        unique = [p for p in patterns if p and p not in seen and not seen.add(p)]
        return unique

    async def _get_repo_context_summary(self) -> str:
        """Get a compact repository context summary for Strategy Agent."""
        repo_key = self._get_repo_key()
        try:
            summary = await self.memory.repo_knowledge.get_compact_summary(repo_key)
            if summary:
                return summary
        except Exception as e:
            logger.warning(f"Failed to load repo knowledge summary for {repo_key}: {e}")

        protocol_name = self._get_protocol_attr("name", "unknown")
        protocol_type = self._get_protocol_attr("type", "cft").upper()
        protocol_lang = self._get_protocol_attr("language", "go")
        protocol_desc = self._get_protocol_attr("description", "")

        fallback = [f"# Repository: {protocol_name}", f"Type: {protocol_type}", f"Language: {protocol_lang}"]
        if protocol_desc:
            fallback.append(f"Description: {protocol_desc}")
        return "\n".join(fallback)

    async def _self_repair_attack_scenario(
        self,
        original_response: str,
        token_usage: TokenUsage,
    ) -> AttackScenario | None:
        """
        Attempt to salvage a strategy response that failed format parsing.

        Sends the original response back to the LLM with the expected format
        template, asking it to restructure (not regenerate) the content.
        This is a lightweight single-turn call with no tool usage.

        Returns:
            Parsed AttackScenario on success, None on failure.
        """
        action_logger = get_action_logger()
        truncated = original_response[-3000:]
        if len(original_response) > 3000:
            truncated = "...(truncated)\n" + truncated

        repair_prompt = (
            "Your previous response contained valuable analysis but was not "
            "formatted correctly. The response MUST include an <attack_scenario> block.\n\n"
            "Here is your original response (may be truncated):\n"
            "---\n"
            f"{truncated}\n"
            "---\n\n"
            "Reformat your analysis into this exact format:\n\n"
            f"{ATTACK_SCENARIO_FORMAT}\n\n"
            "Output ONLY the <attack_scenario> block based on your original analysis. "
            "Do not add any other text."
        )

        try:
            self._current_agent_type = "strategy-repair"
            repair_response = await self.strategy_agent.run(
                repair_prompt, max_iterations=1
            )
            token_usage.add(repair_response.token_usage)

            if repair_response.error:
                logger.warning(f"[SELF-REPAIR] LLM error: {repair_response.error}")
                return None

            scenario = ResultParser.parse_attack_scenario(repair_response.content)
            if scenario:
                logger.info(f"[SELF-REPAIR] Successfully recovered scenario: {scenario.name}")
                action_logger.info(f"[SELF-REPAIR] Recovered scenario: {scenario.name}")
            else:
                logger.warning("[SELF-REPAIR] Repaired response still failed parsing")
                action_logger.warning("[SELF-REPAIR] Repaired response still failed parsing")
            return scenario
        except Exception as e:
            logger.warning(f"[SELF-REPAIR] Unexpected error: {e}")
            return None

    def _finalize_result(
        self,
        result: IterationResult,
        start_time: float,
        iteration_token_usage: TokenUsage,
        action_logger,
    ) -> IterationResult:
        """
        Finalize result with token usage and duration before returning.
        
        This method ensures that token usage is always recorded, even when
        errors occur and the iteration returns early. This is critical for
        accurate cost tracking in ablation experiments.
        
        Args:
            result: The iteration result to finalize.
            start_time: The start time of the iteration (from time.time()).
            iteration_token_usage: Token usage accumulated during this iteration.
            action_logger: The action logger for logging completion.
            
        Returns:
            The finalized IterationResult with token_usage and duration_ms set.
        """
        result.duration_ms = int((time.time() - start_time) * 1000)
        result.token_usage = iteration_token_usage.to_dict()
        self.total_token_usage += iteration_token_usage
        self.tokens_since_last_bug += iteration_token_usage
        
        action_logger.info(
            f"[ITERATION {result.iteration} COMPLETE] duration={result.duration_ms}ms | "
            f"tokens: {iteration_token_usage.format_summary()}"
        )
        
        # Finalize metrics for this iteration
        scenario_name = None
        if result.scenario:
            scenario_name = self._get_scenario_attr(result.scenario, "name", None)
        
        self.metrics.end_iteration(
            status="error" if result.error else "success",
            duration_ms=result.duration_ms,
            scenario_name=scenario_name,
            bugs_found=result.bugs_found,
            token_usage=iteration_token_usage.to_dict(),
            error=result.error[:200] if result.error else None,
        )
        
        # Log completion status
        if result.error:
            action_logger.iteration_end(result.iteration, f"ERROR: {result.error[:100]}")
        elif result.test_result:
            action_logger.iteration_end(result.iteration, f"{result.test_result.result}")
        else:
            action_logger.iteration_end(result.iteration, "COMPLETED")
        
        return result

    # ==================== Main Workflow ====================

    async def run(self, max_iterations: int = 10, forever: bool = False):
        """Run the main bug hunting workflow."""
        logger.info(f"Starting bug hunting for {self._get_protocol_attr('name', 'unknown')}")
        logger.info(f"Protocol type: {self._get_protocol_attr('type', 'cft')}, Language: {self._get_protocol_attr('language', 'go')}")
        logger.info(f"Repository root: {self.repo_root}")

        iteration = 0
        final_status = "completed"

        try:
            while forever or iteration < max_iterations:
                iteration += 1

                try:
                    result = await self.run_iteration(iteration)
                    self.iterations_completed += 1

                    if result.error:
                        self.errors_encountered += 1
                        logger.warning(f"Iteration {iteration} error: {result.error}")

                        # Check for fatal errors
                        for pattern in FATAL_ERROR_PATTERNS:
                            if pattern.lower() in result.error.lower():
                                logger.error(f"Fatal error detected: {result.error}")
                                final_status = "error"
                                await self.close()
                                return

                    if result.protocol_complete:
                        logger.info("Protocol testing complete - no more unique attack scenarios")
                        break

                except asyncio.CancelledError:
                    logger.info("Workflow cancelled by user")
                    final_status = "interrupted"
                    await self.close()
                    break
                except Exception as e:
                    self.errors_encountered += 1
                    logger.error(f"Iteration {iteration} failed: {e}")

                    for pattern in FATAL_ERROR_PATTERNS:
                        if pattern.lower() in str(e).lower():
                            logger.error(f"Fatal error detected in exception: {e}")
                            final_status = "error"
                            await self.close()
                            return

                await asyncio.sleep(0.5)

            await self.close()
        finally:
            self.metrics.finalize(status=final_status)

        # Log final summary
        logger.info(f"Completed {self.iterations_completed} iterations")
        logger.info(f"Bugs found: {self.bugs_found}")
        logger.info(f"Errors: {self.errors_encountered}")

        action_logger = get_action_logger()
        action_logger.info(
            f"[SUMMARY] iterations={self.iterations_completed} | bugs={self.bugs_found} | "
            f"Total tokens: {self.total_token_usage.format_summary()}"
        )
        
        if self.bugs_found > 0:
            avg_tokens = self.total_token_usage.total_tokens // self.bugs_found
            avg_cost = self.total_token_usage.cost / self.bugs_found
            logger.info(f"[Orchestrator] Average per bug: tokens={avg_tokens:,}, cost=${avg_cost:.4f}")

    async def run_iteration(self, iteration: int) -> IterationResult:
        """Run a single iteration of the bug hunting workflow."""
        start_time = time.time()
        logger.info(f"=== Iteration {iteration} ===")

        # Update loggers context
        self.llm_logger.set_context(iteration=iteration, agent_type="orchestrator")
        action_logger = get_action_logger()
        action_logger.set_context(iteration=iteration, agent_type="orchestrator")
        action_logger.iteration_start(iteration)

        # Start metrics tracking for this iteration
        self.metrics.start_iteration(iteration)

        # Token usage tracking for this iteration
        iteration_token_usage = TokenUsage()

        result = IterationResult(
            iteration=iteration, protocol=self._get_protocol_attr("name", "unknown")
        )

        # Track rejected strategies
        rejected_strategies: list[str] = []
        rejected_pattern_ids: list[str] = []
        max_strategy_retries = self.settings.max_strategy_retries

        try:
            scenario = None
            repo_key = self._get_repo_key()
            repo_context = await self._get_repo_context_summary()
            selected_pattern_id: str | None = None
            selected_pattern_protocol_type: str | None = None

            # Step 1: Generate attack strategy (with retry loop)
            for strategy_attempt in range(max_strategy_retries):
                constraint = self._get_constraint()

                # Build pattern context
                pattern_context, allowed_patterns = await self.pattern_tracker.get_pattern_context(
                    self.memory, self._get_protocol_attr("type", "cft"), repo_key, rejected_pattern_ids
                )
                rejection_context = self._build_rejection_context(rejected_strategies, rejected_pattern_ids)
                
                # Build strategy prompt
                context = StrategyContext(
                    protocol_name=self._get_protocol_attr("name", "unknown"),
                    protocol_type=self._get_protocol_attr("type", "cft"),
                    protocol_language=self._get_protocol_attr("language", "go"),
                    protocol_description=self._get_protocol_attr("description", ""),
                    repo_context=repo_context,
                    pattern_context=pattern_context,
                    constraint=constraint + "\n" + rejection_context,
                )
                strategy_prompt = PromptBuilder.build_strategy_prompt(context)

                logger.info(f"Calling Strategy Agent... (attempt {strategy_attempt + 1}/{max_strategy_retries})")
                action_logger.info(f"[STRATEGY AGENT] Generating attack scenario (attempt {strategy_attempt + 1}/{max_strategy_retries})...")

                self._current_agent_type = "strategy"
                strategy_response = await self.strategy_agent.run(strategy_prompt, max_iterations=50)
                iteration_token_usage.add(strategy_response.token_usage)

                if strategy_response.error:
                    logger.error(f"[STRATEGY AGENT ERROR] {strategy_response.error}")
                    logger.error(f"[STRATEGY AGENT ERROR] iterations={strategy_response.iterations}, tool_calls={strategy_response.tool_calls_made}, duration_ms={strategy_response.duration_ms}")
                    action_logger.error(f"[STRATEGY AGENT ERROR] {strategy_response.error}")

                    is_transient = any(
                        p.lower() in strategy_response.error.lower()
                        for p in TRANSIENT_ERROR_PATTERNS
                    )
                    if is_transient and strategy_attempt < max_strategy_retries - 1:
                        wait_time = min(2 ** (strategy_attempt + 1), 30)
                        action_logger.warning(
                            f"[STRATEGY AGENT] Transient error (attempt {strategy_attempt + 1}/{max_strategy_retries}), "
                            f"retrying in {wait_time}s..."
                        )
                        await asyncio.sleep(wait_time)
                        continue

                    result.error = f"Strategy agent error: {strategy_response.error}"
                    return self._finalize_result(result, start_time, iteration_token_usage, action_logger)

                action_logger.thinking("[STRATEGY AGENT OUTPUT]", strategy_response.content)

                # Parse scenario
                scenario = ResultParser.parse_attack_scenario(strategy_response.content)
                if not scenario:
                    action_logger.info("[STRATEGY AGENT] Parse failed, attempting self-repair...")
                    scenario = await self._self_repair_attack_scenario(
                        strategy_response.content, iteration_token_usage
                    )
                    if not scenario:
                        action_logger.warning(
                            f"[STRATEGY AGENT] Self-repair failed "
                            f"(attempt {strategy_attempt + 1}/{max_strategy_retries})"
                        )
                        continue

                # Validate pattern usage
                selected_pattern_id = None
                selected_pattern_protocol_type = None
                pattern_id = ResultParser.extract_pattern_id(scenario.inspiration_source)
                if pattern_id:
                    selected_pattern_protocol_type = allowed_patterns.get(pattern_id)
                    if not selected_pattern_protocol_type:
                        if pattern_id not in rejected_pattern_ids:
                            rejected_pattern_ids.append(pattern_id)
                        action_logger.info(f"[PATTERN REJECTED] pattern_id '{pattern_id}' is not allowed")
                        scenario = None
                        continue
                    selected_pattern_id = pattern_id

                result.scenario = scenario
                logger.info(f"Generated scenario: {scenario.name}")
                logger.debug(f"[SCENARIO DETAILS] name={scenario.name}, target={scenario.target_component}, category={scenario.attack_category}")
                logger.debug(f"[SCENARIO HYPOTHESIS] {scenario.vulnerability_hypothesis[:200] if scenario.vulnerability_hypothesis else 'N/A'}...")
                action_logger.info(f"[ATTACK SCENARIO] {scenario.name} | Target: {scenario.target_component}")

                # Step 2: Check for similar tests
                test_globs = self._get_test_file_globs()
                similarity_check_prompt = PromptBuilder.build_similarity_check_prompt(scenario, test_globs)

                logger.info(f"[SIMILARITY CHECK] Starting for scenario: {scenario.name}")
                action_logger.info(f"[TESTGEN AGENT] iter={iteration} | Checking for similar tests...")
                self._current_agent_type = "similarity"
                similarity_response = await self.testgen_agent.run(similarity_check_prompt, max_iterations=100)
                iteration_token_usage.add(similarity_response.token_usage)
                
                if similarity_response.error:
                    logger.error(f"[SIMILARITY CHECK ERROR] {similarity_response.error}")
                    logger.error(f"[SIMILARITY CHECK ERROR] iterations={similarity_response.iterations}, tokens={similarity_response.token_usage}")
                else:
                    logger.info(f"[SIMILARITY CHECK] Completed: iterations={similarity_response.iterations}, tokens={similarity_response.token_usage.get('total_tokens', 0)}")

                action_logger.thinking("[SIMILARITY CHECK OUTPUT]", similarity_response.content)

                if ResultParser.has_similar_test(similarity_response.content):
                    test_file, test_name = ResultParser.parse_similar_test_info(similarity_response.content)

                    if test_file:
                        action_logger.info(f"[SIMILAR TEST] Running existing test: {test_file}::{test_name or 'all'}")
                        run_test_prompt = PromptBuilder.build_run_existing_test_prompt(test_file, test_name, scenario)
                        run_response = await self.testgen_agent.run(run_test_prompt, max_iterations=self.settings.max_testgen_iterations)
                        iteration_token_usage.add(run_response.token_usage)
                        action_logger.thinking("[EXISTING TEST RUN OUTPUT]", run_response.content)

                        if ResultParser.has_confirmed_bug(run_response.content):
                            action_logger.info(f"[BUG CONFIRMED] Existing test {test_file} confirmed a bug!")
                            self.bugs_found += 1
                            result.bugs_found += 1
                            bug_token_cost = self.tokens_since_last_bug + iteration_token_usage
                            action_logger.info(f"[BUG TOKEN COST] Bug #{self.bugs_found} | {bug_token_cost.format_summary()}")
                            self.tokens_since_last_bug.reset()

                    rejected_strategies.append(f"{scenario.name}: {scenario.vulnerability_hypothesis}")
                    if selected_pattern_id and selected_pattern_protocol_type:
                        await self.pattern_tracker.mark_tested(
                            self.memory, selected_pattern_id, selected_pattern_protocol_type, repo_key, found_bug=result.bugs_found > 0
                        )
                        if selected_pattern_id not in rejected_pattern_ids:
                            rejected_pattern_ids.append(selected_pattern_id)

                    logger.info(f"Similar test validated for '{scenario.name}', trying next strategy...")
                    scenario = None
                    continue
                else:
                    action_logger.info(f"[NO SIMILAR TEST] Strategy '{scenario.name}' is new, starting implementation...")
                    if selected_pattern_id:
                        self.pattern_tracker.mark_used(self._get_protocol_attr("name", "unknown"), selected_pattern_id)
                    break

            if scenario is None:
                action_logger.info(f"[PROTOCOL COMPLETE] Tried {max_strategy_retries} times, no new attack scenarios")
                result.protocol_complete = True
                return self._finalize_result(result, start_time, iteration_token_usage, action_logger)

            # Step 3: Generate and execute test
            testgen_prompt = PromptBuilder.build_testgen_prompt(scenario)
            prompt_len = len(testgen_prompt) if testgen_prompt else 0
            logger.info(f"Calling TestGen Agent... (prompt_len={prompt_len}, max_iterations={self.settings.max_testgen_iterations})")
            logger.debug(f"[TESTGEN PROMPT PREVIEW] {testgen_prompt[:500] if testgen_prompt else 'EMPTY'}...")
            action_logger.info(f"[TESTGEN AGENT] iter={iteration} | Starting test implementation...")

            self._current_agent_type = "testgen"
            testgen_response = await self.testgen_agent.run(testgen_prompt, max_iterations=self.settings.max_testgen_iterations)
            iteration_token_usage.add(testgen_response.token_usage)
            logger.info(f"[TESTGEN RESPONSE] iterations={testgen_response.iterations}, tool_calls={testgen_response.tool_calls_made}, error={testgen_response.error}")

            if testgen_response.error:
                result.error = f"TestGen agent error: {testgen_response.error}"
                logger.error(f"[TESTGEN AGENT ERROR] {testgen_response.error}")
                logger.error(f"[TESTGEN AGENT ERROR] iterations={testgen_response.iterations}, tool_calls={testgen_response.tool_calls_made}, duration_ms={testgen_response.duration_ms}")
                action_logger.error(f"[TESTGEN AGENT ERROR] {testgen_response.error}")
                return self._finalize_result(result, start_time, iteration_token_usage, action_logger)

            action_logger.thinking("[TESTGEN AGENT OUTPUT]", testgen_response.content)

            if not testgen_response.content.strip():
                result.error = "TestGen agent returned empty response"
                logger.error(f"[TESTGEN AGENT ERROR] Empty response after {testgen_response.iterations} iterations, {testgen_response.tool_calls_made} tool calls")
                action_logger.error(f"[TESTGEN AGENT ERROR] Empty response")
                return self._finalize_result(result, start_time, iteration_token_usage, action_logger)

            # Parse test result
            test_result = ResultParser.parse_test_result(testgen_response.content)
            if test_result:
                result.test_result = test_result
                action_logger.info(f"[TEST RESULT] {test_result.test_file} | {test_result.result}")
                self.metrics.record_test_case()

            confirmed_bug = ResultParser.has_confirmed_bug(testgen_response.content)
            if selected_pattern_id and selected_pattern_protocol_type:
                await self.pattern_tracker.mark_tested(
                    self.memory, selected_pattern_id, selected_pattern_protocol_type, repo_key, found_bug=confirmed_bug
                )

            if confirmed_bug:
                logger.info(f"[BUG FOUND] CONFIRMED BUG: {scenario.name}")
                action_logger.info(f"[CONFIRMED BUG] {scenario.name}")

                bug_token_cost = self.tokens_since_last_bug + iteration_token_usage
                await self._record_potential_bug(scenario, test_result, bug_token_cost)
                result.bugs_found += 1

                action_logger.info(f"[BUG TOKEN COST] Bug #{self.bugs_found} | {bug_token_cost.format_summary()}")
                self.tokens_since_last_bug.reset()

                # Trigger exploitation mode
                if self.settings.max_bug_exploitation_attempts > 0:
                    action_logger.info(f"[BUG EXPLOITATION] Triggering exploitation mode for: {scenario.name}")
                    await self._exploit_bug(scenario, test_result, iteration, iteration_token_usage)

        except asyncio.CancelledError:
            raise
        except (OSError, IOError) as e:
            result.error = f"IO error: {e}"
            logger.error(f"Iteration IO error: {e}")
            action_logger.error(f"[ITERATION ERROR] IO: {str(e)}")
        except json.JSONDecodeError as e:
            result.error = f"JSON parse error: {e}"
            logger.error(f"Iteration JSON error: {e}")
            action_logger.error(f"[ITERATION ERROR] JSON: {str(e)}")
        except ValueError as e:
            result.error = f"Value error: {e}"
            logger.error(f"Iteration value error: {e}")
            action_logger.error(f"[ITERATION ERROR] Value: {str(e)}")
        except RuntimeError as e:
            result.error = f"Runtime error: {e}"
            logger.error(f"Iteration runtime error: {e}")
            logger.debug(f"Full traceback:\n{traceback.format_exc()}")
            action_logger.error(f"[ITERATION ERROR] Runtime: {str(e)}")
        except Exception as e:
            error_type = type(e).__name__
            result.error = f"Unexpected error ({error_type}): {e}"
            logger.error(f"Iteration unexpected error: {error_type}: {e}")
            logger.debug(f"Full traceback:\n{traceback.format_exc()}")
            action_logger.error(f"[ITERATION ERROR] Unexpected: {error_type}: {e}")

        return self._finalize_result(result, start_time, iteration_token_usage, action_logger)

    # ==================== Bug Recording ====================

    async def _generate_bug_report(
        self,
        scenario: AttackScenario,
        result: TestResult,
        bug_token_usage: TokenUsage,
    ) -> tuple[str, "BugPattern | None"]:
        """Generate bug report using ReportGenerator."""
        action_logger = get_action_logger()
        action_logger.info(f"[ORCHESTRATOR LLM] Generating bug report for: {scenario.name}")

        self._current_agent_type = "report"
        report_start = time.time()
        bug_report, bug_pattern = await self.report_generator.generate_bug_report(
            scenario=scenario,
            result=result,
            protocol_name=self._get_protocol_attr("name", "unknown"),
            protocol_type=self._get_protocol_attr("type", "cft"),
            bug_token_usage=bug_token_usage,
        )
        report_duration_ms = int((time.time() - report_start) * 1000)

        report_usage_dict = self.report_generator.get_token_usage()
        report_usage = TokenUsage()
        report_usage.add(report_usage_dict)
        self.total_token_usage += report_usage

        # Record report generation as an API call in metrics
        self.metrics.record_api_call(
            agent_type="report",
            model=self.settings.llm_model,
            usage=report_usage_dict,
            duration_ms=report_duration_ms,
            success=True,
        )

        action_logger.thinking("[BUG REPORT GENERATED]", bug_report[:500] + "...")
        return bug_report, bug_pattern

    async def _record_potential_bug(
        self,
        scenario: AttackScenario,
        result: TestResult,
        bug_token_usage: TokenUsage | None = None,
    ):
        """Record a potential bug when test assertion fails."""
        scenario_name = self._get_scenario_attr(scenario, "name", "unknown")
        scenario_category = self._get_scenario_attr(scenario, "attack_category", "unknown")
        scenario_hypothesis = self._get_scenario_attr(scenario, "vulnerability_hypothesis", "")

        logger.info(f"[BUG FOUND] Potential bug (unverified): {scenario_name}")
        action_logger = get_action_logger()

        if bug_token_usage is None:
            bug_token_usage = self.tokens_since_last_bug.copy()

        bug_report, bug_pattern = await self._generate_bug_report(scenario, result, bug_token_usage)

        # Save bug pattern
        if bug_pattern:
            try:
                await self.memory.pattern_memory.add_pattern(bug_pattern)
                action_logger.info(f"[PATTERN MEMORY] Added bug pattern: {bug_pattern.pattern_id}")
            except Exception as e:
                logger.error(f"[Orchestrator] Failed to save bug pattern: {e}")
                action_logger.error(f"[PATTERN MEMORY ERROR] {e}")

        # Extract test name
        language = self._get_protocol_attr("language", "go")
        test_name = ResultParser.extract_test_name(result.test_code, language)

        bug_record = BugRecord(
            id=datetime.now().strftime("%Y%m%d_%H%M%S"),
            protocol=self._get_protocol_attr("name", "unknown"),
            protocol_type=self._get_protocol_attr("type", "cft"),
            language=self._get_protocol_attr("language", "go"),
            bug_category=scenario_category,
            fault_type=scenario_category,
            scenario_name=scenario_name,
            scenario_description=scenario_hypothesis,
            vulnerability_hypothesis=scenario_hypothesis,
            target_component=self._get_scenario_attr(scenario, "target_component", ""),
            preconditions=self._get_scenario_attr(scenario, "preconditions", []),
            attack_steps=self._get_scenario_attr(scenario, "steps", []),
            expected_bug_behavior=self._get_scenario_attr(scenario, "expected_bug_behavior", ""),
            correct_behavior=self._get_scenario_attr(scenario, "correct_behavior", ""),
            test_name=test_name,
            test_file=result.test_file,
            test_code=result.test_code,
            test_output=result.test_output,
            validation_reason="Unverified - test assertion failed",
            bug_report=bug_report,
            status="unverified",
        )

        await self.test_history.add_bug(bug_record)
        logger.info(f"[SAVED] Potential bug saved to: test_history/bugs/{bug_record.protocol}/")
        self.bugs_found += 1
        return bug_record

    # ==================== Bug Exploitation ====================

    async def _exploit_bug(
        self,
        original_scenario: AttackScenario,
        original_result: TestResult,
        base_iteration: int,
        iteration_token_usage: TokenUsage | None = None,
    ) -> list[IterationResult]:
        """Exploit a confirmed bug to discover related vulnerabilities."""
        from ..prompts import get_bug_exploitation_prompt
        
        max_attempts = self.settings.max_bug_exploitation_attempts
        results: list[IterationResult] = []
        previous_scenarios: list[str] = []

        action_logger = get_action_logger()
        original_bug_name = self._get_scenario_attr(original_scenario, "name", "Unknown")

        logger.info(f"[BUG EXPLOITATION] Starting exploitation mode for bug: {original_bug_name}")
        action_logger.info(f"[BUG EXPLOITATION] Starting exploitation (max {max_attempts} attempts)")

        bug_context = PromptBuilder.format_bug_context(original_scenario, original_result)
        constraint = self._get_constraint()

        for attempt in range(1, max_attempts + 1):
            logger.info(f"[BUG EXPLOITATION] Attempt {attempt}/{max_attempts}")
            action_logger.info(f"[BUG EXPLOITATION] Attempt {attempt}/{max_attempts}")

            exploitation_result = IterationResult(
                iteration=base_iteration, protocol=self._get_protocol_attr("name", "unknown")
            )

            try:
                exploitation_prompt = get_bug_exploitation_prompt(
                    bug_context=bug_context,
                    protocol_name=self._get_protocol_attr("name", "unknown"),
                    protocol_type=self._get_protocol_attr("type", "cft"),
                    constraint=constraint,
                    attempt=attempt,
                    max_attempts=max_attempts,
                    previous_scenarios=previous_scenarios if previous_scenarios else None,
                )

                self.llm_logger.set_context(iteration=base_iteration, agent_type="strategy-exploitation")
                self._current_agent_type = "exploitation"
                strategy_response = await self.strategy_agent.run(exploitation_prompt, max_iterations=50)

                if iteration_token_usage:
                    iteration_token_usage.add(strategy_response.token_usage)

                if strategy_response.error:
                    exploitation_result.error = f"Strategy error: {strategy_response.error}"
                    logger.error(f"[BUG EXPLOITATION] Strategy error: {strategy_response.error}")
                    logger.error(f"[BUG EXPLOITATION] iterations={strategy_response.iterations}, tool_calls={strategy_response.tool_calls_made}")
                    action_logger.error(f"[BUG EXPLOITATION] Strategy error: {strategy_response.error}")
                    results.append(exploitation_result)
                    continue

                action_logger.thinking(f"[BUG EXPLOITATION] Strategy Output", strategy_response.content)

                new_scenario = ResultParser.parse_attack_scenario(strategy_response.content)
                if not new_scenario:
                    action_logger.info("[BUG EXPLOITATION] Parse failed, attempting self-repair...")
                    repair_token_usage = iteration_token_usage if iteration_token_usage else TokenUsage()
                    new_scenario = await self._self_repair_attack_scenario(
                        strategy_response.content, repair_token_usage
                    )
                    if not new_scenario:
                        exploitation_result.error = "Failed to parse exploitation scenario after self-repair"
                        results.append(exploitation_result)
                        continue

                exploitation_result.scenario = new_scenario
                previous_scenarios.append(new_scenario.name)

                action_logger.info(f"[BUG EXPLOITATION] New scenario: {new_scenario.name}")

                self.llm_logger.set_context(iteration=base_iteration, agent_type="testgen-exploitation")
                self._current_agent_type = "exploitation"
                testgen_prompt = PromptBuilder.build_testgen_prompt(new_scenario)
                testgen_response = await self.testgen_agent.run(testgen_prompt, max_iterations=self.settings.max_testgen_iterations)

                if iteration_token_usage:
                    iteration_token_usage.add(testgen_response.token_usage)

                if testgen_response.error:
                    exploitation_result.error = f"TestGen error: {testgen_response.error}"
                    results.append(exploitation_result)
                    continue

                action_logger.thinking(f"[BUG EXPLOITATION] TestGen Output", testgen_response.content)

                test_result = ResultParser.parse_test_result(testgen_response.content)
                if test_result:
                    exploitation_result.test_result = test_result
                    action_logger.info(f"[BUG EXPLOITATION] Test result: {test_result.result}")

                if ResultParser.has_confirmed_bug(testgen_response.content):
                    logger.info(f"[BUG EXPLOITATION] ADDITIONAL BUG FOUND: {new_scenario.name}")
                    action_logger.info(f"[BUG EXPLOITATION] SUCCESS! Additional bug found")

                    if test_result:
                        await self._record_potential_bug(new_scenario, test_result, iteration_token_usage)
                else:
                    action_logger.info(f"[BUG EXPLOITATION] Attempt {attempt}: No additional bug found")

                results.append(exploitation_result)

            except asyncio.CancelledError:
                logger.info("[BUG EXPLOITATION] Cancelled by user")
                raise
            except Exception as e:
                exploitation_result.error = f"Exploitation error: {e}"
                logger.error(f"[BUG EXPLOITATION] Error in attempt {attempt}: {e}")
                results.append(exploitation_result)

        bugs_found_in_exploitation = sum(r.bugs_found for r in results)
        action_logger.info(f"[BUG EXPLOITATION] Complete: {bugs_found_in_exploitation} additional bugs found")

        return results


# ============================================================
# Factory Function
# ============================================================


async def create_orchestrator(
    protocol_name: str, settings: Settings | None = None
) -> Orchestrator:
    """Create an orchestrator for a specific protocol."""
    if settings is None:
        settings = load_settings()

    protocol_config = None
    for name, config in settings.protocols.items():
        if name == protocol_name:
            protocol_config = config
            break

    if not protocol_config:
        raise ValueError(f"Protocol not found: {protocol_name}")

    memory_server = create_memory_server(api_key=settings.openrouter_api_key)

    return Orchestrator(
        protocol_config=protocol_config, settings=settings, memory_server=memory_server
    )
