"""
Experiment Metrics Tracker - Structured, crash-safe experiment data recording.

Records per-API-call token usage, per-iteration statistics, and per-session
summaries into a JSON file that is atomically flushed to disk after every
state change, so data is never lost on interruption.

Output path:
    agent/data/test_history/{protocol}/metrics/session_{timestamp}.json
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ============================================================
# Data Classes
# ============================================================


@dataclass
class APICallRecord:
    """A single LLM API call."""

    timestamp: str = ""
    agent_type: str = ""  # strategy / testgen / similarity / exploitation / report
    model: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cached_tokens: int = 0
    reasoning_tokens: int = 0
    cost: float = 0.0
    duration_ms: int = 0
    success: bool = True
    error: str | None = None
    generation_id: str | None = None


@dataclass
class IterationMetrics:
    """Metrics for one orchestrator iteration."""

    iteration: int = 0
    start_time: str = ""
    end_time: str | None = None
    duration_ms: int = 0
    status: str = "running"  # running / success / error / interrupted
    scenario_name: str | None = None
    test_cases_generated: int = 0
    bugs_found: int = 0
    api_calls: list[APICallRecord] = field(default_factory=list)
    token_usage: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass
class SessionMetrics:
    """Top-level metrics for one experiment session."""

    session_id: str = ""
    start_time: str = ""
    end_time: str | None = None
    protocol: str = ""
    model: str = ""
    status: str = "running"  # running / completed / interrupted / error

    iterations: list[IterationMetrics] = field(default_factory=list)

    total_duration_ms: int = 0
    total_api_calls: int = 0
    total_tokens: dict[str, Any] = field(default_factory=lambda: {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "cached_tokens": 0,
        "reasoning_tokens": 0,
    })
    total_test_cases: int = 0
    total_bugs_found: int = 0
    total_cost: float = 0.0


# ============================================================
# MetricsTracker
# ============================================================


class MetricsTracker:
    """
    Crash-safe experiment metrics recorder.

    Every mutation flushes the full state to disk via atomic rename,
    so a kill -9 or power failure never leaves a corrupt file.
    """

    def __init__(
        self,
        protocol: str,
        model: str,
        base_path: Path | None = None,
    ):
        if base_path is None:
            base_path = Path(__file__).parent.parent / "data" / "test_history"
        self._base_path = Path(base_path)

        now = datetime.now()
        session_id = now.strftime("%Y%m%d_%H%M%S_") + f"{now.microsecond // 1000:03d}"

        self._metrics = SessionMetrics(
            session_id=session_id,
            start_time=now.isoformat(),
            protocol=protocol,
            model=model,
        )

        self._current_iteration: IterationMetrics | None = None
        self._start_timestamp: float = now.timestamp()

        # Ensure output directory
        self._metrics_dir = self._base_path / protocol / "metrics"
        self._metrics_dir.mkdir(parents=True, exist_ok=True)
        self._file_path = self._metrics_dir / f"session_{session_id}.json"

        self._flush()
        logger.info(f"[MetricsTracker] Session {session_id} -> {self._file_path}")

    # ---- properties ----

    @property
    def file_path(self) -> Path:
        return self._file_path

    @property
    def session_id(self) -> str:
        return self._metrics.session_id

    # ---- iteration lifecycle ----

    def start_iteration(self, iteration: int) -> None:
        it = IterationMetrics(
            iteration=iteration,
            start_time=datetime.now().isoformat(),
            status="running",
        )
        self._current_iteration = it
        self._metrics.iterations.append(it)
        self._flush()

    def end_iteration(
        self,
        *,
        status: str = "success",
        duration_ms: int = 0,
        scenario_name: str | None = None,
        bugs_found: int = 0,
        token_usage: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        it = self._current_iteration
        if it is None:
            return
        it.end_time = datetime.now().isoformat()
        it.duration_ms = duration_ms
        it.status = status
        if scenario_name:
            it.scenario_name = scenario_name
        it.bugs_found = bugs_found
        if token_usage:
            it.token_usage = token_usage
        it.error = error

        # Update session totals
        self._metrics.total_bugs_found += bugs_found

        self._current_iteration = None
        self._flush()

    # ---- api call recording ----

    def record_api_call(
        self,
        agent_type: str,
        model: str,
        usage: dict[str, Any],
        duration_ms: int = 0,
        success: bool = True,
        error: str | None = None,
        generation_id: str | None = None,
    ) -> None:
        """Record a single LLM API call. Flushes to disk immediately."""
        prompt_details = usage.get("prompt_tokens_details") or {}
        completion_details = usage.get("completion_tokens_details") or {}

        rec = APICallRecord(
            timestamp=datetime.now().isoformat(),
            agent_type=agent_type,
            model=model,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            cached_tokens=prompt_details.get("cached_tokens", 0),
            reasoning_tokens=completion_details.get("reasoning_tokens", 0),
            cost=usage.get("cost", 0.0) or 0.0,
            duration_ms=duration_ms,
            success=success,
            error=error,
            generation_id=generation_id,
        )

        # Attach to current iteration if one is open
        if self._current_iteration is not None:
            self._current_iteration.api_calls.append(rec)

        # Update session totals
        self._metrics.total_api_calls += 1
        self._metrics.total_cost += rec.cost
        totals = self._metrics.total_tokens
        totals["prompt_tokens"] += rec.prompt_tokens
        totals["completion_tokens"] += rec.completion_tokens
        totals["total_tokens"] += rec.total_tokens
        totals["cached_tokens"] += rec.cached_tokens
        totals["reasoning_tokens"] += rec.reasoning_tokens

        self._flush()

    # ---- test case recording ----

    def record_test_case(self, count: int = 1) -> None:
        """Record that test case(s) were generated."""
        if self._current_iteration is not None:
            self._current_iteration.test_cases_generated += count
        self._metrics.total_test_cases += count
        self._flush()

    # ---- finalize ----

    def finalize(self, status: str = "completed") -> None:
        """Mark session as finished (or interrupted). Always safe to call."""
        # If there is an in-flight iteration, mark it too
        if self._current_iteration is not None:
            self._current_iteration.status = "interrupted"
            self._current_iteration.end_time = datetime.now().isoformat()
            self._current_iteration = None

        now = datetime.now()
        self._metrics.status = status
        self._metrics.end_time = now.isoformat()
        self._metrics.total_duration_ms = int(
            (now.timestamp() - self._start_timestamp) * 1000
        )
        self._flush()
        logger.info(
            f"[MetricsTracker] Session {self._metrics.session_id} finalized "
            f"({status}) -> {self._file_path}"
        )

    # ---- persistence ----

    def _flush(self) -> None:
        """Atomically write current state to disk."""
        data = _session_to_dict(self._metrics)
        try:
            # Write to temp file in the same directory, then atomic rename
            fd, tmp_path = tempfile.mkstemp(
                dir=self._metrics_dir, suffix=".tmp", prefix=".metrics_"
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                os.replace(tmp_path, self._file_path)
            except BaseException:
                # Clean up temp file on any error
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
        except OSError as exc:
            logger.warning(f"[MetricsTracker] flush failed: {exc}")

    # ---- loading (static) ----

    @staticmethod
    def load(path: Path) -> SessionMetrics:
        """Load a previously saved session metrics JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return _dict_to_session(data)

    @staticmethod
    def list_sessions(
        protocol: str,
        base_path: Path | None = None,
    ) -> list[Path]:
        """List all session metrics files for a protocol, newest first."""
        if base_path is None:
            base_path = Path(__file__).parent.parent / "data" / "test_history"
        metrics_dir = base_path / protocol / "metrics"
        if not metrics_dir.exists():
            return []
        files = sorted(metrics_dir.glob("session_*.json"), reverse=True)
        return files


# ============================================================
# Serialization helpers
# ============================================================


def _session_to_dict(s: SessionMetrics) -> dict[str, Any]:
    """Convert SessionMetrics to a JSON-serializable dict."""
    d = asdict(s)
    # asdict already handles nested dataclasses
    return d


def _dict_to_session(d: dict[str, Any]) -> SessionMetrics:
    """Reconstruct SessionMetrics from a dict (loaded from JSON)."""
    iterations = []
    for it_data in d.get("iterations", []):
        api_calls = [APICallRecord(**ac) for ac in it_data.pop("api_calls", [])]
        iterations.append(IterationMetrics(**it_data, api_calls=api_calls))

    d_copy = {k: v for k, v in d.items() if k != "iterations"}
    return SessionMetrics(**d_copy, iterations=iterations)
