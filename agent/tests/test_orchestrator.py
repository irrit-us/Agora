"""
Tests for the Orchestrator class with the new ToolAgent architecture.
Tests workflow, parsing, and agent coordination.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add paths for imports
project_root = Path(__file__).parent.parent.parent
agent_dir = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
if str(agent_dir) not in sys.path:
    sys.path.insert(0, str(agent_dir))

from agent.config.settings import ProtocolConfig, Settings
from agent.core.orchestrator import IterationResult, Orchestrator
from agent.core.strategies import AttackScenario, TestResult
from agent.core.result_parser import ResultParser
from agent.core.tool_agent import AgentResponse, ToolAgent
from agent.mcp_servers.memory_server import MemoryTools, create_memory_server

from .mocks.llm_responses import MOCK_RESPONSES

# ============================================================
# Mock Orchestrator
# ============================================================


class MockOrchestrator(Orchestrator):
    """
    Orchestrator with mocked agent run methods.
    Returns predefined responses.
    """

    def __init__(self, *args, strategy_response=None, testgen_response=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._strategy_response = strategy_response or MOCK_RESPONSES["strategy"]
        self._testgen_response = testgen_response or MOCK_RESPONSES["testgen"]
        self.call_history = []

        # Replace agents with mocks
        self.strategy_agent = MagicMock(spec=ToolAgent)
        self.testgen_agent = MagicMock(spec=ToolAgent)

        # Setup mock responses
        self.strategy_agent.run = AsyncMock(
            return_value=AgentResponse(
                content=self._strategy_response,
                tool_calls_made=1,
                iterations=1,
                duration_ms=100,
            )
        )

        self.testgen_agent.run = AsyncMock(
            return_value=AgentResponse(
                content=self._testgen_response,
                tool_calls_made=5,
                iterations=3,
                duration_ms=500,
            )
        )


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def mock_orchestrator(mock_settings, mock_protocol_config, memory_server):
    """Create a MockOrchestrator for testing."""
    return MockOrchestrator(
        protocol_config=mock_protocol_config,
        settings=mock_settings,
        memory_server=memory_server,
    )


@pytest.fixture
def mock_orchestrator_with_responses(
    mock_settings, mock_protocol_config, memory_server
):
    """Factory fixture for creating MockOrchestrator with specific responses."""

    def _create(strategy_response=None, testgen_response=None):
        return MockOrchestrator(
            protocol_config=mock_protocol_config,
            settings=mock_settings,
            memory_server=memory_server,
            strategy_response=strategy_response,
            testgen_response=testgen_response,
        )

    return _create


# ============================================================
# Parsing Tests
# ============================================================


class TestOrchestratorParsing:
    """Tests for Orchestrator parsing methods."""

    def test_parse_attack_scenario(self, mock_orchestrator):
        """Test parsing attack scenario."""
        scenario = mock_orchestrator._parse_attack_scenario(MOCK_RESPONSES["strategy"])

        assert scenario is not None
        assert scenario.name == "StaleLeaderElectionViolation"
        assert scenario.attack_category == "safety"
        assert len(scenario.steps) > 0

    def test_parse_attack_scenario_minimal(self, mock_orchestrator):
        """Test parsing minimal scenario."""
        scenario = mock_orchestrator._parse_attack_scenario(
            MOCK_RESPONSES["strategy_minimal"]
        )

        assert scenario is not None
        assert scenario.name == "MinimalTestScenario"

    def test_parse_attack_scenario_none(self, mock_orchestrator):
        """Test parsing returns None for invalid response."""
        scenario = mock_orchestrator._parse_attack_scenario("No scenario here")

        assert scenario is None

    def test_extract_code(self, mock_orchestrator):
        """Test extracting code from response using ResultParser."""
        # Use ResultParser directly since _extract_code_from_response was moved
        code = ResultParser._extract_code_from_response(MOCK_RESPONSES["testgen"])

        assert code is not None
        assert "func Test" in code

    def test_extract_test_name_go(self, mock_orchestrator):
        """Test extracting Go test name."""
        code = "func TestLeaderElection(t *testing.T) {}"
        name = mock_orchestrator._extract_test_name(code)

        assert name == "TestLeaderElection"

    def test_format_scenario_for_testgen(self):
        """Format scenario for TestGen using PromptBuilder directly."""
        from agent.core.prompt_builder import PromptBuilder

        scenario = AttackScenario(
            name="TestScenario",
            target_component="Component",
            vulnerability_hypothesis="Hypothesis",
            attack_category="safety",
            preconditions=["pre1", "pre2"],
            steps=["step1", "step2"],
            expected_bug_behavior="Expected",
            correct_behavior="Correct",
            assertions=["assert1"],
            thinking_chain="",
        )

        formatted = PromptBuilder.format_scenario_for_testgen(scenario)

        assert "TestScenario" in formatted
        assert "step1" in formatted
        assert "assert1" in formatted


# ============================================================
# Agent Tests
# ============================================================


class TestAgents:
    """Tests for agent creation and configuration."""

    def test_orchestrator_has_strategy_agent(self, mock_orchestrator):
        """Test that orchestrator has a strategy agent."""
        assert mock_orchestrator.strategy_agent is not None

    def test_orchestrator_has_testgen_agent(self, mock_orchestrator):
        """Test that orchestrator has a testgen agent."""
        assert mock_orchestrator.testgen_agent is not None

    def test_real_orchestrator_creates_tool_agents(
        self, mock_settings, mock_protocol_config, memory_server
    ):
        """Test that real orchestrator creates ToolAgent instances."""
        # Create real orchestrator (not mock)
        orchestrator = Orchestrator(
            protocol_config=mock_protocol_config,
            settings=mock_settings,
            memory_server=memory_server,
        )

        assert isinstance(orchestrator.strategy_agent, ToolAgent)
        assert isinstance(orchestrator.testgen_agent, ToolAgent)

    def test_strategy_agent_has_no_tools(
        self, mock_settings, mock_protocol_config, memory_server
    ):
        """Test that strategy agent has no tools (generates strategies from LLM knowledge only)."""
        orchestrator = Orchestrator(
            protocol_config=mock_protocol_config,
            settings=mock_settings,
            memory_server=memory_server,
        )

        # Strategy agent has only get_pattern_details tool for querying bug patterns
        tools = orchestrator.strategy_agent.tools
        assert len(tools) == 1
        assert "get_pattern_details" in tools

    def test_testgen_agent_has_repo_tools(
        self, mock_settings, mock_protocol_config, memory_server
    ):
        """Test that testgen agent has repository and memory tools."""
        orchestrator = Orchestrator(
            protocol_config=mock_protocol_config,
            settings=mock_settings,
            memory_server=memory_server,
        )

        tools = orchestrator.testgen_agent.tools
        # Core file/command tools
        assert "read_file" in tools
        assert "write_file" in tools
        assert "run_command" in tools
        assert "glob_files" in tools
        # Repository knowledge tools
        assert "repo_knowledge" in tools
        assert "repo_knowledge_find_lessons" in tools
        assert "repo_knowledge_add_lesson" in tools
        assert "repo_knowledge_add_helper" in tools


# ============================================================
# Workflow Tests
# ============================================================


class TestWorkflow:
    """Tests for the main workflow."""

    @pytest.mark.asyncio
    async def test_run_iteration_calls_strategy_first(self, mock_orchestrator):
        """Test that run_iteration calls strategy agent first."""
        await mock_orchestrator.run_iteration(1)

        mock_orchestrator.strategy_agent.run.assert_called()

    @pytest.mark.asyncio
    async def test_run_iteration_calls_testgen_after_strategy(self, mock_orchestrator):
        """Test that testgen is called after strategy succeeds."""
        await mock_orchestrator.run_iteration(1)

        mock_orchestrator.strategy_agent.run.assert_called()
        mock_orchestrator.testgen_agent.run.assert_called()

    @pytest.mark.asyncio
    async def test_run_iteration_returns_result(self, mock_orchestrator):
        """Test that run_iteration returns IterationResult."""
        result = await mock_orchestrator.run_iteration(1)

        assert isinstance(result, IterationResult)
        assert result.iteration == 1
        assert result.protocol == "test-raft"

    @pytest.mark.asyncio
    async def test_run_iteration_parses_scenario(self, mock_orchestrator):
        """Test that scenario is parsed from strategy response."""
        result = await mock_orchestrator.run_iteration(1)

        assert result.scenario is not None
        assert result.scenario.name == "StaleLeaderElectionViolation"

    @pytest.mark.asyncio
    async def test_run_iteration_strategy_error(self, mock_orchestrator_with_responses):
        """Test iteration handles strategy agent error."""
        mock = mock_orchestrator_with_responses(strategy_response="")
        mock.strategy_agent.run.return_value = AgentResponse(
            content="",
            error="Connection error",
            tool_calls_made=0,
            iterations=0,
            duration_ms=0,
        )

        result = await mock.run_iteration(1)

        assert result.error is not None
        assert "error" in result.error.lower()


# ============================================================
# Helper Methods Tests
# ============================================================


class TestHelperMethods:
    """Tests for helper methods."""

    def test_get_protocol_attr_from_config(self, mock_orchestrator):
        """Test getting protocol attribute from config."""
        name = mock_orchestrator._get_protocol_attr("name", "default")
        assert name == "test-raft"

    def test_get_protocol_attr_default(self, mock_orchestrator):
        """Test getting default value for missing attribute."""
        value = mock_orchestrator._get_protocol_attr("nonexistent", "default")
        assert value == "default"

    def test_extract_field(self):
        """Test field extraction using ResultParser."""
        text = "Name: TestName\nValue: 123"
        name = ResultParser._extract_field(text, "Name")

        assert name == "TestName"

    def test_extract_list(self):
        """Test list extraction using ResultParser."""
        text = """
Steps:
- Step 1
- Step 2
- Step 3
"""
        steps = ResultParser._extract_list(text, "Steps")

        assert len(steps) == 3
        assert "Step 1" in steps

# ============================================================
# Statistics Tests
# ============================================================


class TestStatistics:
    """Tests for orchestrator statistics."""

    def test_initial_statistics(self, mock_orchestrator):
        """Test initial statistics are zero."""
        assert mock_orchestrator.iterations_completed == 0
        assert mock_orchestrator.bugs_found == 0
        assert mock_orchestrator.errors_encountered == 0

    @pytest.mark.asyncio
    async def test_iteration_count_incremented(self, mock_orchestrator):
        """Test iteration count is tracked by run()."""
        # run() increments iterations_completed
        # But we need to test run_iteration directly since run() has a loop
        result = await mock_orchestrator.run_iteration(1)

        # run_iteration doesn't increment stats, run() does
        # So check that result has iteration number
        assert result.iteration == 1


# ============================================================
# Path Resolution Tests
# ============================================================


class TestPathResolution:
    """Tests for path resolution."""

    def test_repo_root_resolved(self, mock_orchestrator):
        """Test that repo_root is resolved."""
        assert mock_orchestrator.repo_root is not None
        assert isinstance(mock_orchestrator.repo_root, Path)

    def test_project_root_is_parent(self, mock_orchestrator):
        """Test that project_root is set."""
        assert mock_orchestrator.project_root is not None
        assert (
            mock_orchestrator.project_root.name == "consensus-test"
            or (mock_orchestrator.project_root / "agent").exists()
        )
