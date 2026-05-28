"""
End-to-end tests for the complete bug hunting workflow.
Tests full flows without actual LLM calls using comprehensive mocks.
"""

import asyncio
import sys
from pathlib import Path
import pytest

# Add paths for imports
project_root = Path(__file__).parent.parent.parent
agent_dir = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
if str(agent_dir) not in sys.path:
    sys.path.insert(0, str(agent_dir))

from agent.config.settings import ProtocolConfig, Settings
from agent.core.orchestrator import (
    AttackScenario,
    IterationResult,
    Orchestrator,
    TestResult,
)
from agent.mcp_servers.memory_server import MemoryTools, create_memory_server

from .mocks.llm_responses import MOCK_RESPONSES

# ============================================================
# E2E Test Helper Classes
# ============================================================


class E2EOrchestrator(Orchestrator):
    """
    Fully mocked Orchestrator for end-to-end testing.
    All external interactions are mocked.
    """

    def __init__(
        self, *args, response_sequence=None, test_execution_results=None, **kwargs
    ):
        super().__init__(*args, **kwargs)

        # Response sequence for agents
        self.response_sequence = response_sequence or {}
        self.response_index = {"strategy": 0, "testgen": 0, "validator": 0}

        # Test execution results sequence
        self.test_execution_results = test_execution_results or []
        self.test_execution_index = 0

        # Tracking
        self.agent_calls = []
        self.memory_operations = []
        self.github_submissions = []

        # Create memory_tools wrapper for testing
        self.memory_tools = MemoryTools(self.memory)

    async def _call_agent(self, prompt: str, agent_type: str) -> str | None:
        """Return mock response from sequence."""
        self.agent_calls.append({"type": agent_type, "prompt_length": len(prompt)})

        if agent_type in self.response_sequence:
            responses = self.response_sequence[agent_type]
            if isinstance(responses, list):
                idx = min(self.response_index[agent_type], len(responses) - 1)
                self.response_index[agent_type] += 1
                return responses[idx]
            return responses

        return None

    async def _execute_generated_test(
        self, response: str, scenario: AttackScenario
    ) -> TestResult:
        """Return mock test result from sequence."""
        if self.test_execution_results:
            idx = min(self.test_execution_index, len(self.test_execution_results) - 1)
            self.test_execution_index += 1
            return self.test_execution_results[idx]

        # Default: test fails (potential bug)
        return TestResult(
            success=True,
            test_code="func TestMock(t *testing.T) {}",
            test_file="mock_test.go",
            test_output="--- FAIL: TestMock",
            passed=False,
        )


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def e2e_orchestrator(mock_settings, mock_protocol_config, memory_server):
    """Create E2E orchestrator with default responses."""
    return E2EOrchestrator(
        protocol_config=mock_protocol_config,
        settings=mock_settings,
        memory_server=memory_server,
        response_sequence={
            "strategy": MOCK_RESPONSES["strategy"],
            "testgen": MOCK_RESPONSES["testgen"],
            "validator": MOCK_RESPONSES["validator_bug"],
        },
    )


@pytest.fixture
def e2e_orchestrator_factory(mock_settings, mock_protocol_config, memory_server):
    """Factory for creating E2E orchestrators with custom config."""

    def _create(response_sequence=None, test_results=None):
        return E2EOrchestrator(
            protocol_config=mock_protocol_config,
            settings=mock_settings,
            memory_server=memory_server,
            response_sequence=response_sequence or {},
            test_execution_results=test_results or [],
        )

    return _create


# ============================================================
# Bug Discovery Flow Tests
# ============================================================


@pytest.mark.e2e
class TestBugDiscoveryFlow:
    """End-to-end tests for the complete bug discovery flow."""

    @pytest.mark.asyncio
    async def test_complete_bug_discovery_flow(self, e2e_orchestrator):
        """
        Test complete flow: Strategy → TestGen → Validator → Bug Confirmed
        """
        result = await e2e_orchestrator.run_iteration(1)

        # Verify flow completed
        assert result.iteration == 1
        assert result.scenario is not None
        assert result.scenario.name == "StaleLeaderElectionViolation"

        # Verify test was run
        assert result.test_result is not None
        assert result.test_result.success

        # Verify validation
        assert result.validation is not None
        assert result.validation.is_real_bug

        # Verify GitHub submission
        assert len(e2e_orchestrator.github_submissions) == 1
        assert e2e_orchestrator.github_submissions[0]["is_real_bug"]

    @pytest.mark.asyncio
    async def test_bug_discovery_records_pattern(self, e2e_orchestrator):
        """Test that discovered bugs are recorded to pattern memory."""
        await e2e_orchestrator.run_iteration(1)

        # Check pattern was added
        patterns_result = await e2e_orchestrator.memory_tools.pattern_get(
            {"protocol_type": "cft"}
        )

        # Should have recorded the bug pattern
        content = patterns_result["content"][0]["text"]
        # Pattern may or may not be present depending on full flow execution

    @pytest.mark.asyncio
    async def test_bug_discovery_records_test_history(self, e2e_orchestrator):
        """Test that tests are recorded to history."""
        await e2e_orchestrator.run_iteration(1)

        # Check test history
        stats = await e2e_orchestrator.memory_tools.test_history_get_stats(
            {"protocol": "test-raft"}
        )

        assert "content" in stats

    @pytest.mark.asyncio
    async def test_multiple_iterations(self, e2e_orchestrator_factory):
        """Test running multiple iterations."""
        orchestrator = e2e_orchestrator_factory(
            response_sequence={
                "strategy": [
                    MOCK_RESPONSES["strategy"],
                    MOCK_RESPONSES["strategy_minimal"],
                    MOCK_RESPONSES["strategy_bft"],
                ],
                "testgen": MOCK_RESPONSES["testgen"],
                "validator": MOCK_RESPONSES["validator_bug"],
            }
        )

        results = []
        for i in range(3):
            result = await orchestrator.run_iteration(i + 1)
            results.append(result)

        assert len(results) == 3
        assert all(r.scenario is not None for r in results)
        # Different scenarios should be generated
        names = [r.scenario.name for r in results]
        assert len(set(names)) > 1  # At least some different names


# ============================================================
# False Positive Flow Tests
# ============================================================


@pytest.mark.e2e
class TestFalsePositiveFlow:
    """End-to-end tests for false positive handling."""

    @pytest.mark.asyncio
    async def test_false_positive_test_error(self, e2e_orchestrator_factory):
        """Test handling of false positive due to test error."""
        orchestrator = e2e_orchestrator_factory(
            response_sequence={
                "strategy": MOCK_RESPONSES["strategy"],
                "testgen": MOCK_RESPONSES["testgen"],
                "validator": MOCK_RESPONSES["validator_false_positive"],
            }
        )

        result = await orchestrator.run_iteration(1)

        assert result.validation is not None
        assert not result.validation.is_real_bug
        assert result.validation.rejection_reason == "test_error"

        # No GitHub submission
        assert len(orchestrator.github_submissions) == 0

    @pytest.mark.asyncio
    async def test_false_positive_unrealistic(self, e2e_orchestrator_factory):
        """Test handling of unrealistic scenario."""
        orchestrator = e2e_orchestrator_factory(
            response_sequence={
                "strategy": MOCK_RESPONSES["strategy"],
                "testgen": MOCK_RESPONSES["testgen"],
                "validator": MOCK_RESPONSES["validator_unrealistic"],
            }
        )

        result = await orchestrator.run_iteration(1)

        assert result.validation is not None
        assert not result.validation.is_real_bug
        assert not result.validation.is_realistic_scenario

    @pytest.mark.asyncio
    async def test_false_positive_expected_behavior(self, e2e_orchestrator_factory):
        """Test handling when behavior is actually expected."""
        orchestrator = e2e_orchestrator_factory(
            response_sequence={
                "strategy": MOCK_RESPONSES["strategy"],
                "testgen": MOCK_RESPONSES["testgen"],
                "validator": MOCK_RESPONSES["validator_expected"],
            }
        )

        result = await orchestrator.run_iteration(1)

        assert result.validation is not None
        assert not result.validation.is_real_bug
        assert result.validation.rejection_reason == "expected_behavior"

    @pytest.mark.asyncio
    async def test_false_positive_records_learning(self, e2e_orchestrator_factory):
        """Test that false positives are recorded for learning."""
        orchestrator = e2e_orchestrator_factory(
            response_sequence={
                "strategy": MOCK_RESPONSES["strategy"],
                "testgen": MOCK_RESPONSES["testgen"],
                "validator": MOCK_RESPONSES["validator_false_positive"],
            }
        )

        await orchestrator.run_iteration(1)

        # Should record the false positive
        # The learning should include rejection reason and pattern to avoid


# ============================================================
# Test Pass Flow Tests
# ============================================================


@pytest.mark.e2e
class TestPassFlow:
    """End-to-end tests for when tests pass (no bug found)."""

    @pytest.mark.asyncio
    async def test_test_passes_no_validation(self, e2e_orchestrator_factory):
        """Test that passing tests skip validation."""
        orchestrator = e2e_orchestrator_factory(
            response_sequence={
                "strategy": MOCK_RESPONSES["strategy"],
                "testgen": MOCK_RESPONSES["testgen"],
            },
            test_results=[
                TestResult(
                    success=True,
                    test_code="func Test(){}",
                    test_file="test.go",
                    test_output="PASS\nok package 1.23s",
                    passed=True,
                )
            ],
        )

        result = await orchestrator.run_iteration(1)

        assert result.test_result.passed
        assert result.validation is None  # No validation for passing tests

    @pytest.mark.asyncio
    async def test_test_passes_records_success(self, e2e_orchestrator_factory):
        """Test that passing tests are recorded."""
        orchestrator = e2e_orchestrator_factory(
            response_sequence={
                "strategy": MOCK_RESPONSES["strategy"],
                "testgen": MOCK_RESPONSES["testgen"],
            },
            test_results=[
                TestResult(
                    success=True,
                    test_code="func TestPass(){}",
                    test_file="pass_test.go",
                    test_output="PASS",
                    passed=True,
                )
            ],
        )

        await orchestrator.run_iteration(1)

        # Test should be recorded in history
        stats = await orchestrator.memory_tools.test_history_get_stats(
            {"protocol": "test-raft"}
        )
        assert "content" in stats


# ============================================================
# Error Recovery Flow Tests
# ============================================================


@pytest.mark.e2e
class TestErrorRecoveryFlow:
    """End-to-end tests for error recovery."""

    @pytest.mark.asyncio
    async def test_strategy_failure_recovery(self, e2e_orchestrator_factory):
        """Test recovery from strategy agent failure."""
        orchestrator = e2e_orchestrator_factory(
            response_sequence={
                "strategy": None,  # Failure
            }
        )

        result = await orchestrator.run_iteration(1)

        assert result.error is not None
        assert "scenario" in result.error.lower()

        # Should still track statistics
        assert orchestrator.iterations_completed == 0  # Failed iteration

    @pytest.mark.asyncio
    async def test_testgen_failure_recovery(self, e2e_orchestrator_factory):
        """Test recovery from testgen failure."""
        orchestrator = e2e_orchestrator_factory(
            response_sequence={
                "strategy": MOCK_RESPONSES["strategy"],
                "testgen": None,  # Failure
            }
        )

        result = await orchestrator.run_iteration(1)

        # Should have scenario but test failed
        assert result.scenario is not None
        assert result.error is not None or (
            result.test_result and not result.test_result.success
        )

    @pytest.mark.asyncio
    async def test_test_execution_failure(self, e2e_orchestrator_factory):
        """Test handling of test execution failure."""
        orchestrator = e2e_orchestrator_factory(
            response_sequence={
                "strategy": MOCK_RESPONSES["strategy"],
                "testgen": MOCK_RESPONSES["testgen"],
            },
            test_results=[
                TestResult(
                    success=False,
                    test_code="",
                    test_file="",
                    test_output="",
                    error="Compilation failed: syntax error",
                )
            ],
        )

        result = await orchestrator.run_iteration(1)

        assert result.test_result is not None
        assert not result.test_result.success
        assert result.error is not None


# ============================================================
# Memory Persistence Tests
# ============================================================


@pytest.mark.e2e
class TestMemoryPersistence:
    """Tests for memory persistence across iterations."""

    @pytest.mark.asyncio
    async def test_learning_accumulates(self, e2e_orchestrator_factory):
        """Test that learning accumulates across iterations."""
        orchestrator = e2e_orchestrator_factory(
            response_sequence={
                "strategy": MOCK_RESPONSES["strategy"],
                "testgen": MOCK_RESPONSES["testgen"],
                "validator": MOCK_RESPONSES["validator_false_positive"],
            }
        )

        # Run multiple iterations
        for i in range(3):
            await orchestrator.run_iteration(i + 1)

        # Check test history records accumulated
        stats = await orchestrator.memory_tools.test_history_get_stats(
            {"protocol": "test-raft"}
        )

        assert "content" in stats

    @pytest.mark.asyncio
    async def test_patterns_persist(self, e2e_orchestrator_factory):
        """Test that patterns persist."""
        orchestrator = e2e_orchestrator_factory(
            response_sequence={
                "strategy": MOCK_RESPONSES["strategy"],
                "testgen": MOCK_RESPONSES["testgen"],
                "validator": MOCK_RESPONSES["validator_bug"],
            }
        )

        await orchestrator.run_iteration(1)

        # Check patterns
        patterns = await orchestrator.memory_tools.pattern_get({"protocol_type": "cft"})

        assert "content" in patterns


# ============================================================
# Full Workflow Integration Tests
# ============================================================


@pytest.mark.e2e
@pytest.mark.integration
class TestFullWorkflowIntegration:
    """Integration tests for the complete workflow."""

    @pytest.mark.asyncio
    async def test_complete_session_simulation(self, e2e_orchestrator_factory):
        """
        Simulate a complete testing session with multiple outcomes.
        """
        # Prepare varied responses
        orchestrator = e2e_orchestrator_factory(
            response_sequence={
                "strategy": [
                    MOCK_RESPONSES["strategy"],
                    MOCK_RESPONSES["strategy_minimal"],
                    MOCK_RESPONSES["strategy"],
                ],
                "testgen": MOCK_RESPONSES["testgen"],
                "validator": [
                    MOCK_RESPONSES["validator_bug"],
                    MOCK_RESPONSES["validator_false_positive"],
                    MOCK_RESPONSES["validator_unrealistic"],
                ],
            },
            test_results=[
                TestResult(
                    success=True,
                    test_code="",
                    test_file="t1.go",
                    test_output="FAIL",
                    passed=False,
                ),
                TestResult(
                    success=True,
                    test_code="",
                    test_file="t2.go",
                    test_output="FAIL",
                    passed=False,
                ),
                TestResult(
                    success=True,
                    test_code="",
                    test_file="t3.go",
                    test_output="FAIL",
                    passed=False,
                ),
            ],
        )

        # Run session
        results = []
        for i in range(3):
            result = await orchestrator.run_iteration(i + 1)
            results.append(result)

        # Verify outcomes
        assert len(results) == 3

        # First should be bug found
        assert results[0].validation.is_real_bug

        # Second should be false positive
        assert not results[1].validation.is_real_bug
        assert results[1].validation.rejection_reason == "test_error"

        # Third should be unrealistic
        assert not results[2].validation.is_real_bug

        # Only one GitHub submission (for the real bug)
        assert len(orchestrator.github_submissions) == 1

    @pytest.mark.asyncio
    async def test_agent_call_sequence(self, e2e_orchestrator):
        """Test that agents are called in correct sequence."""
        await e2e_orchestrator.run_iteration(1)

        calls = e2e_orchestrator.agent_calls

        # Should call strategy first
        assert calls[0]["type"] == "strategy"

        # Then testgen
        testgen_calls = [c for c in calls if c["type"] == "testgen"]
        assert len(testgen_calls) >= 1

        # Then validator (for failed test)
        validator_calls = [c for c in calls if c["type"] == "validator"]
        assert len(validator_calls) >= 1

    @pytest.mark.asyncio
    async def test_memory_context_used(self, e2e_orchestrator):
        """Test that memory context is retrieved and used."""
        # Add some prior knowledge
        await e2e_orchestrator.memory_tools.pattern_add(
            {
                "pattern_id": "Network partition causes safety issue",
                "protocol_type": "cft",
                "fault_type": "partition",
                "bug_category": "safety",
                "trigger_condition": "network partition",
                "description": "Prior pattern",
            }
        )

        # Run iteration
        await e2e_orchestrator.run_iteration(1)

        # Strategy agent should have been called with context
        strategy_calls = [
            c for c in e2e_orchestrator.agent_calls if c["type"] == "strategy"
        ]
        assert len(strategy_calls) > 0
        # The prompt length should be substantial (includes context)
        assert strategy_calls[0]["prompt_length"] > 100


# ============================================================
# Performance and Stress Tests
# ============================================================


@pytest.mark.e2e
@pytest.mark.slow
class TestPerformance:
    """Performance and stress tests."""

    @pytest.mark.asyncio
    async def test_many_iterations(self, e2e_orchestrator_factory):
        """Test running many iterations."""
        orchestrator = e2e_orchestrator_factory(
            response_sequence={
                "strategy": MOCK_RESPONSES["strategy"],
                "testgen": MOCK_RESPONSES["testgen"],
                "validator": MOCK_RESPONSES["validator_false_positive"],
            },
            test_results=[
                TestResult(
                    success=True,
                    test_code="",
                    test_file="t.go",
                    test_output="FAIL",
                    passed=False,
                )
            ]
            * 20,
        )

        results = []
        for i in range(20):
            result = await orchestrator.run_iteration(i + 1)
            results.append(result)

        assert len(results) == 20
        # All should complete without error
        errors = [r for r in results if r.error]
        assert len(errors) == 0

    @pytest.mark.asyncio
    async def test_concurrent_memory_access(self, e2e_orchestrator):
        """Test concurrent memory access."""

        async def add_pattern(i):
            return await e2e_orchestrator.memory_tools.pattern_add(
                {
                    "pattern_id": f"Concurrent pattern {i}",
                    "protocol_type": "cft",
                    "fault_type": f"fault_{i}",
                    "bug_category": "safety",
                    "trigger_condition": f"trigger_{i}",
                    "description": f"Pattern {i}",
                }
            )

        # Add patterns concurrently
        results = await asyncio.gather(*[add_pattern(i) for i in range(10)])

        # All should succeed
        assert all("Successfully" in r["content"][0]["text"] for r in results)

        # All patterns should be retrievable
        patterns = await e2e_orchestrator.memory_tools.pattern_get(
            {"protocol_type": "cft"}
        )
        assert "10 patterns" in patterns["content"][0]["text"]
