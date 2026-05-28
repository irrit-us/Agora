"""
Tests for Baseline Agent prompts module.

Tests the prompt generation functions and core files mapping.
"""

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

from agent.baseline.prompts import (
    BASELINE_SYSTEM_PROMPT,
    REPO_CORE_FILES,
    get_analysis_prompt,
    get_core_files,
)


# ============================================================
# BASELINE_SYSTEM_PROMPT Tests
# ============================================================


class TestBaselineSystemPrompt:
    """Tests for the system prompt constant."""

    def test_system_prompt_is_string(self):
        """Test that system prompt is a non-empty string."""
        assert isinstance(BASELINE_SYSTEM_PROMPT, str)
        assert len(BASELINE_SYSTEM_PROMPT) > 100

    def test_system_prompt_contains_role_description(self):
        """Test that system prompt describes the agent's role."""
        assert "bug hunter" in BASELINE_SYSTEM_PROMPT.lower()
        assert "consensus" in BASELINE_SYSTEM_PROMPT.lower()

    def test_system_prompt_mentions_tools(self):
        """Test that system prompt mentions available tools."""
        assert "list_files" in BASELINE_SYSTEM_PROMPT
        assert "read_file" in BASELINE_SYSTEM_PROMPT
        assert "search_code" in BASELINE_SYSTEM_PROMPT

    def test_system_prompt_has_react_pattern(self):
        """Test that system prompt describes ReAct pattern."""
        prompt_lower = BASELINE_SYSTEM_PROMPT.lower()
        assert "thought" in prompt_lower
        assert "action" in prompt_lower
        assert "observation" in prompt_lower

    def test_system_prompt_has_output_format(self):
        """Test that system prompt includes output format."""
        assert "<bug_report>" in BASELINE_SYSTEM_PROMPT
        assert "</bug_report>" in BASELINE_SYSTEM_PROMPT
        assert "<analysis_complete>" in BASELINE_SYSTEM_PROMPT


# ============================================================
# REPO_CORE_FILES Tests
# ============================================================


class TestRepoCoreFiles:
    """Tests for the core files mapping constant."""

    def test_core_files_is_dict(self):
        """Test that REPO_CORE_FILES is a dictionary."""
        assert isinstance(REPO_CORE_FILES, dict)

    def test_core_files_has_known_repos(self):
        """Test that known repositories are in the mapping."""
        expected_repos = ["raft", "sui", "hotstuff", "efficient-epaxos"]
        for repo in expected_repos:
            assert repo in REPO_CORE_FILES, f"Missing repo: {repo}"

    def test_core_files_are_lists(self):
        """Test that each repo has a list of files."""
        for repo, files in REPO_CORE_FILES.items():
            assert isinstance(files, list), f"{repo} should have a list"
            assert len(files) > 0, f"{repo} should have at least one file"

    def test_raft_core_files(self):
        """Test raft repository core files."""
        raft_files = REPO_CORE_FILES.get("raft", [])
        assert "raft.go" in raft_files
        assert "log.go" in raft_files

    def test_sui_core_files(self):
        """Test sui repository core files."""
        sui_files = REPO_CORE_FILES.get("sui", [])
        assert any("dag_state" in f for f in sui_files)
        assert any("linearizer" in f for f in sui_files)

    def test_hotstuff_core_files(self):
        """Test hotstuff repository core files."""
        hotstuff_files = REPO_CORE_FILES.get("hotstuff", [])
        assert any("chainedhotstuff" in f for f in hotstuff_files)

    def test_epaxos_core_files(self):
        """Test efficient-epaxos repository core files."""
        epaxos_files = REPO_CORE_FILES.get("efficient-epaxos", [])
        assert any("epaxos.go" in f for f in epaxos_files)


# ============================================================
# get_core_files Tests
# ============================================================


class TestGetCoreFiles:
    """Tests for the get_core_files function."""

    def test_get_core_files_known_repo(self):
        """Test getting core files for a known repository."""
        files = get_core_files("raft")
        assert isinstance(files, list)
        assert len(files) > 0
        assert "raft.go" in files

    def test_get_core_files_unknown_repo(self):
        """Test getting core files for an unknown repository."""
        files = get_core_files("unknown-repo")
        assert isinstance(files, list)
        assert len(files) == 0

    def test_get_core_files_empty_string(self):
        """Test getting core files with empty string."""
        files = get_core_files("")
        assert isinstance(files, list)
        assert len(files) == 0

    @pytest.mark.parametrize(
        "repo_name",
        ["raft", "sui", "hotstuff", "efficient-epaxos"],
    )
    def test_get_core_files_all_repos(self, repo_name):
        """Test getting core files for all known repositories."""
        files = get_core_files(repo_name)
        assert isinstance(files, list)
        assert len(files) > 0

    def test_get_core_files_returns_same_as_dict(self):
        """Test that get_core_files returns the same as dict access."""
        for repo in REPO_CORE_FILES:
            assert get_core_files(repo) == REPO_CORE_FILES[repo]


# ============================================================
# get_analysis_prompt Tests
# ============================================================


class TestGetAnalysisPrompt:
    """Tests for the get_analysis_prompt function."""

    def test_analysis_prompt_basic(self):
        """Test basic analysis prompt generation."""
        prompt = get_analysis_prompt("raft")
        assert isinstance(prompt, str)
        assert len(prompt) > 50

    def test_analysis_prompt_contains_repo_hint(self):
        """Test that prompt contains repository-specific hints."""
        prompt = get_analysis_prompt("raft")
        # Should contain raft-specific hints
        assert "raft" in prompt.lower() or "Raft" in prompt

    def test_analysis_prompt_with_target_files(self):
        """Test prompt generation with specific target files."""
        target_files = ["raft.go", "log.go"]
        prompt = get_analysis_prompt("raft", target_files)

        assert "raft.go" in prompt
        assert "log.go" in prompt
        assert "Focus" in prompt or "focus" in prompt

    def test_analysis_prompt_without_target_files(self):
        """Test prompt generation without target files."""
        prompt = get_analysis_prompt("raft", None)

        # Should suggest exploration
        assert "list_files" in prompt or "explore" in prompt.lower()

    def test_analysis_prompt_empty_target_files(self):
        """Test prompt generation with empty target files list."""
        prompt = get_analysis_prompt("raft", [])

        # Empty list should be treated like None - suggest exploration
        assert "list_files" in prompt or "explore" in prompt.lower()

    @pytest.mark.parametrize(
        "repo_name,expected_keyword",
        [
            ("raft", "raft"),
            ("sui", "sui"),
            ("hotstuff", "hotstuff"),
            ("efficient-epaxos", "epaxos"),
        ],
    )
    def test_analysis_prompt_repo_specific(self, repo_name, expected_keyword):
        """Test that each repo gets its specific hints."""
        prompt = get_analysis_prompt(repo_name)
        assert expected_keyword.lower() in prompt.lower()

    def test_analysis_prompt_unknown_repo(self):
        """Test prompt generation for unknown repository."""
        prompt = get_analysis_prompt("unknown-repo")

        # Should still return a valid prompt
        assert isinstance(prompt, str)
        assert len(prompt) > 20
        # Should mention the repo name
        assert "unknown-repo" in prompt

    def test_analysis_prompt_has_task_section(self):
        """Test that prompt includes task section."""
        prompt = get_analysis_prompt("raft")

        # Should have a task/objective section
        assert "Task" in prompt or "task" in prompt

    def test_analysis_prompt_single_target_file(self):
        """Test prompt with a single target file."""
        target_files = ["raft.go"]
        prompt = get_analysis_prompt("raft", target_files)

        assert "raft.go" in prompt

    def test_analysis_prompt_many_target_files(self):
        """Test prompt with many target files."""
        target_files = ["file1.go", "file2.go", "file3.go", "file4.go", "file5.go"]
        prompt = get_analysis_prompt("raft", target_files)

        for f in target_files:
            assert f in prompt


# ============================================================
# Integration Tests
# ============================================================


class TestPromptsIntegration:
    """Integration tests for prompts module."""

    def test_system_and_analysis_prompts_compatible(self):
        """Test that system and analysis prompts work together."""
        system = BASELINE_SYSTEM_PROMPT
        analysis = get_analysis_prompt("raft", ["raft.go"])

        # Together they should form a coherent instruction set
        combined_length = len(system) + len(analysis)
        assert combined_length > 500  # Should be substantial

        # Both should be non-empty
        assert len(system) > 0
        assert len(analysis) > 0

    def test_core_files_work_with_prompt(self):
        """Test that core files can be passed to analysis prompt."""
        for repo in REPO_CORE_FILES:
            core_files = get_core_files(repo)
            prompt = get_analysis_prompt(repo, core_files)

            # All core files should be mentioned
            for f in core_files:
                # Extract just the filename for matching
                filename = Path(f).name
                assert filename in prompt or f in prompt

    def test_prompt_format_consistency(self):
        """Test that all prompts follow consistent formatting."""
        for repo in REPO_CORE_FILES:
            prompt = get_analysis_prompt(repo)

            # Should not have excessive whitespace
            assert "\n\n\n\n" not in prompt  # No quadruple newlines
            assert "  " not in prompt or prompt.count("  ") < 50  # Limited double spaces
