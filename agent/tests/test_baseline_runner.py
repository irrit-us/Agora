"""
Tests for Baseline Agent CLI runner.

Tests the command-line interface and result handling:
- Argument parsing
- Result saving
- Configuration loading
- Error handling
"""

import json
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

# Add paths for imports
project_root = Path(__file__).parent.parent.parent
agent_dir = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
if str(agent_dir) not in sys.path:
    sys.path.insert(0, str(agent_dir))

from agent.baseline.react_agent import AnalysisResult, BugReport
from agent.baseline.runner import (
    DEFAULT_MAX_ITERATIONS,
    DEFAULT_OUTPUT_DIR,
    EXIT_ERROR,
    EXIT_NO_BUGS,
    EXIT_SUCCESS,
    REPO_PATHS,
    get_project_root,
    get_repo_path,
    parse_args,
    print_result,
    save_result,
    setup_logging,
)


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def sample_result():
    """Create a sample AnalysisResult for testing."""
    return AnalysisResult(
        repo_name="raft",
        model="anthropic/claude-sonnet-4",
        iterations=5,
        tool_calls=10,
        duration_ms=5000,
        tokens_used=1500,
        final_response="Analysis complete",
    )


@pytest.fixture
def sample_result_with_bugs():
    """Create a sample AnalysisResult with bugs."""
    result = AnalysisResult(
        repo_name="raft",
        model="anthropic/claude-sonnet-4",
        iterations=10,
        tool_calls=25,
        duration_ms=15000,
    )
    result.bugs_found = [
        BugReport(
            file="raft.go",
            line=145,
            bug_type="safety",
            severity="critical",
            description="Missing log check in vote handler",
            root_cause="No comparison of log indices",
            trigger_condition="Network partition during election",
            impact="Data loss possible",
        ),
        BugReport(
            file="log.go",
            line=89,
            bug_type="liveness",
            severity="medium",
            description="Potential deadlock in log compaction",
            root_cause="Mutex ordering issue",
            trigger_condition="Concurrent snapshot and append",
            impact="Node becomes unresponsive",
        ),
    ]
    result.files_analyzed = ["raft.go", "log.go", "storage.go"]
    return result


@pytest.fixture
def sample_result_with_error():
    """Create a sample AnalysisResult with error."""
    result = AnalysisResult(
        repo_name="raft",
        model="test-model",
        iterations=2,
        tool_calls=3,
        duration_ms=2000,
    )
    result.error = "HTTP 500: Internal server error"
    return result


@pytest.fixture
def temp_output_dir(tmp_path):
    """Create a temporary output directory."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    return output_dir


# ============================================================
# REPO_PATHS Tests
# ============================================================


class TestRepoPaths:
    """Tests for the REPO_PATHS constant."""

    def test_repo_paths_is_dict(self):
        """Test that REPO_PATHS is a dictionary."""
        assert isinstance(REPO_PATHS, dict)

    def test_repo_paths_has_known_repos(self):
        """Test that known repositories are present."""
        expected = ["raft", "sui", "hotstuff", "efficient-epaxos"]
        for repo in expected:
            assert repo in REPO_PATHS

    def test_repo_paths_values_are_strings(self):
        """Test that all paths are strings."""
        for name, path in REPO_PATHS.items():
            assert isinstance(path, str)


# ============================================================
# get_project_root Tests
# ============================================================


class TestGetProjectRoot:
    """Tests for get_project_root function."""

    def test_returns_path(self):
        """Test that function returns a Path."""
        root = get_project_root()
        assert isinstance(root, Path)

    def test_returns_absolute_path(self):
        """Test that returned path is absolute."""
        root = get_project_root()
        assert root.is_absolute()

    def test_path_is_resolved(self):
        """Test that path is resolved (no ..)."""
        root = get_project_root()
        assert ".." not in str(root)


# ============================================================
# get_repo_path Tests
# ============================================================


class TestGetRepoPath:
    """Tests for get_repo_path function."""

    def test_unknown_repo_raises_error(self):
        """Test that unknown repo raises ValueError."""
        with pytest.raises(ValueError, match="Unknown repository"):
            get_repo_path("nonexistent-repo")

    def test_error_message_includes_available(self):
        """Test that error message includes available repos."""
        try:
            get_repo_path("nonexistent-repo")
        except ValueError as e:
            assert "raft" in str(e)


# ============================================================
# setup_logging Tests
# ============================================================


class TestSetupLogging:
    """Tests for setup_logging function."""

    def test_setup_logging_default(self):
        """Test default logging setup."""
        # Should not raise
        setup_logging(verbose=False)

    def test_setup_logging_verbose(self):
        """Test verbose logging setup."""
        # Should not raise
        setup_logging(verbose=True)


# ============================================================
# save_result Tests
# ============================================================


class TestSaveResult:
    """Tests for save_result function."""

    def test_save_result_creates_file(self, sample_result, temp_output_dir):
        """Test that save_result creates a file."""
        output_path = save_result(sample_result, temp_output_dir)

        assert output_path.exists()
        assert output_path.suffix == ".json"

    def test_save_result_filename_format(self, sample_result, temp_output_dir):
        """Test that filename has correct format."""
        output_path = save_result(sample_result, temp_output_dir)

        filename = output_path.name
        assert filename.startswith("baseline_raft_")
        assert "anthropic_claude-sonnet-4" in filename
        assert filename.endswith(".json")

    def test_save_result_content(self, sample_result, temp_output_dir):
        """Test that saved content is correct."""
        output_path = save_result(sample_result, temp_output_dir)

        with open(output_path) as f:
            data = json.load(f)

        assert data["repo_name"] == "raft"
        assert data["model"] == "anthropic/claude-sonnet-4"
        assert data["iterations"] == 5
        assert data["tool_calls"] == 10
        assert "timestamp" in data
        assert "version" in data

    def test_save_result_with_bugs(self, sample_result_with_bugs, temp_output_dir):
        """Test saving result with bugs."""
        output_path = save_result(sample_result_with_bugs, temp_output_dir)

        with open(output_path) as f:
            data = json.load(f)

        assert len(data["bugs_found"]) == 2
        assert data["bugs_found"][0]["file"] == "raft.go"
        assert data["bugs_found"][0]["type"] == "safety"

    def test_save_result_creates_directory(self, sample_result, tmp_path):
        """Test that save_result creates output directory if needed."""
        output_dir = tmp_path / "new" / "nested" / "dir"
        output_path = save_result(sample_result, output_dir)

        assert output_path.exists()
        assert output_dir.exists()

    def test_save_result_with_error(self, sample_result_with_error, temp_output_dir):
        """Test saving result with error."""
        output_path = save_result(sample_result_with_error, temp_output_dir)

        with open(output_path) as f:
            data = json.load(f)

        assert data["error"] == "HTTP 500: Internal server error"

    def test_save_result_unicode_safe(self, temp_output_dir):
        """Test that save handles unicode content."""
        result = AnalysisResult(
            repo_name="test",
            model="test-model",
            final_response="测试中文 日本語 🎉",
        )

        output_path = save_result(result, temp_output_dir)

        with open(output_path, encoding="utf-8") as f:
            data = json.load(f)

        # Should be saved and loadable without error
        assert data["repo_name"] == "test"
        assert data.get("bugs_found") is not None  # Should be empty list, not None


# ============================================================
# print_result Tests
# ============================================================


class TestPrintResult:
    """Tests for print_result function."""

    def test_print_result_basic(self, sample_result, capsys):
        """Test basic result printing."""
        print_result(sample_result)

        captured = capsys.readouterr()
        assert "raft" in captured.out
        assert "5" in captured.out  # iterations
        assert "10" in captured.out  # tool calls

    def test_print_result_with_bugs(self, sample_result_with_bugs, capsys):
        """Test printing result with bugs."""
        print_result(sample_result_with_bugs)

        captured = capsys.readouterr()
        assert "Bugs Found: 2" in captured.out
        assert "raft.go" in captured.out
        assert "safety" in captured.out
        assert "critical" in captured.out

    def test_print_result_with_error(self, sample_result_with_error, capsys):
        """Test printing result with error."""
        print_result(sample_result_with_error)

        captured = capsys.readouterr()
        assert "Error" in captured.out
        assert "500" in captured.out

    def test_print_result_duration_formatted(self, sample_result, capsys):
        """Test that duration is formatted as seconds."""
        print_result(sample_result)

        captured = capsys.readouterr()
        assert "5.0s" in captured.out  # 5000ms = 5.0s

    def test_print_result_no_bugs_shows_final_response(self, capsys):
        """Test that no bugs shows final response."""
        result = AnalysisResult(
            repo_name="test",
            model="test-model",
            final_response="No issues found in the code.",
        )

        print_result(result)

        captured = capsys.readouterr()
        assert "No issues found" in captured.out

    def test_print_result_long_description_truncated(self, capsys):
        """Test that long bug descriptions are truncated."""
        result = AnalysisResult(repo_name="test", model="test")
        result.bugs_found = [
            BugReport(
                file="test.go",
                line=1,
                bug_type="test",
                severity="low",
                description="A" * 500,  # Very long description
                root_cause="",
                trigger_condition="",
                impact="",
            )
        ]

        print_result(result)

        captured = capsys.readouterr()
        assert "..." in captured.out  # Should be truncated


# ============================================================
# parse_args Tests
# ============================================================


class TestParseArgs:
    """Tests for argument parsing."""

    def test_parse_required_repo(self):
        """Test that --repo is required."""
        with pytest.raises(SystemExit):
            with patch("sys.argv", ["runner"]):
                parse_args()

    def test_parse_repo_argument(self):
        """Test parsing repo argument."""
        with patch("sys.argv", ["runner", "--repo", "raft"]):
            args = parse_args()

        assert args.repo == "raft"

    def test_parse_repo_choices(self):
        """Test that repo must be a valid choice."""
        with pytest.raises(SystemExit):
            with patch("sys.argv", ["runner", "--repo", "invalid-repo"]):
                parse_args()

    def test_parse_target_files(self):
        """Test parsing target files."""
        with patch("sys.argv", ["runner", "--repo", "raft", "--target", "a.go", "b.go"]):
            args = parse_args()

        assert args.target == ["a.go", "b.go"]

    def test_parse_target_optional(self):
        """Test that target is optional."""
        with patch("sys.argv", ["runner", "--repo", "raft"]):
            args = parse_args()

        assert args.target is None

    def test_parse_model_argument(self):
        """Test parsing model argument."""
        with patch("sys.argv", ["runner", "--repo", "raft", "--model", "test-model"]):
            args = parse_args()

        assert args.model == "test-model"

    def test_parse_max_iterations(self):
        """Test parsing max iterations."""
        with patch("sys.argv", ["runner", "--repo", "raft", "--max-iterations", "50"]):
            args = parse_args()

        assert args.max_iterations == 50

    def test_parse_max_iterations_default(self):
        """Test default max iterations."""
        with patch("sys.argv", ["runner", "--repo", "raft"]):
            args = parse_args()

        assert args.max_iterations == DEFAULT_MAX_ITERATIONS

    def test_parse_output_dir(self):
        """Test parsing output directory."""
        with patch("sys.argv", ["runner", "--repo", "raft", "--output-dir", "/tmp/out"]):
            args = parse_args()

        assert args.output_dir == Path("/tmp/out")

    def test_parse_verbose_flag(self):
        """Test parsing verbose flag."""
        with patch("sys.argv", ["runner", "--repo", "raft", "-v"]):
            args = parse_args()

        assert args.verbose is True

    def test_parse_verbose_long(self):
        """Test parsing verbose flag long form."""
        with patch("sys.argv", ["runner", "--repo", "raft", "--verbose"]):
            args = parse_args()

        assert args.verbose is True

    def test_parse_verbose_default(self):
        """Test default verbose is False."""
        with patch("sys.argv", ["runner", "--repo", "raft"]):
            args = parse_args()

        assert args.verbose is False


# ============================================================
# Constants Tests
# ============================================================


class TestConstants:
    """Tests for module constants."""

    def test_default_max_iterations(self):
        """Test DEFAULT_MAX_ITERATIONS value."""
        assert DEFAULT_MAX_ITERATIONS == 30

    def test_exit_codes(self):
        """Test exit code values."""
        assert EXIT_SUCCESS == 0
        assert EXIT_NO_BUGS == 1
        assert EXIT_ERROR == 2

    def test_default_output_dir(self):
        """Test DEFAULT_OUTPUT_DIR value."""
        assert "baseline_results" in DEFAULT_OUTPUT_DIR


# ============================================================
# Integration Tests
# ============================================================


class TestRunnerIntegration:
    """Integration tests for the runner module."""

    def test_save_and_reload_result(self, sample_result_with_bugs, temp_output_dir):
        """Test saving and reloading a result."""
        # Save
        output_path = save_result(sample_result_with_bugs, temp_output_dir)

        # Reload
        with open(output_path) as f:
            data = json.load(f)

        # Verify all data preserved
        assert data["repo_name"] == sample_result_with_bugs.repo_name
        assert data["model"] == sample_result_with_bugs.model
        assert data["iterations"] == sample_result_with_bugs.iterations
        assert len(data["bugs_found"]) == len(sample_result_with_bugs.bugs_found)
        assert len(data["files_analyzed"]) == len(sample_result_with_bugs.files_analyzed)

    def test_multiple_results_unique_filenames(self, sample_result, temp_output_dir):
        """Test that multiple results get unique filenames."""
        path1 = save_result(sample_result, temp_output_dir)
        time.sleep(1.1)  # Ensure different timestamp (need > 1 second for different timestamp)
        path2 = save_result(sample_result, temp_output_dir)

        assert path1 != path2
        assert path1.exists()
        assert path2.exists()

    def test_result_with_special_model_name(self, temp_output_dir):
        """Test result with special characters in model name."""
        result = AnalysisResult(
            repo_name="test",
            model="org/model:v1.2.3 beta",
        )

        output_path = save_result(result, temp_output_dir)

        # Should create valid filename
        assert output_path.exists()
        # No special characters in filename
        assert "/" not in output_path.name
        assert ":" not in output_path.name
        assert " " not in output_path.name
