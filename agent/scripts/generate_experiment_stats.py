#!/usr/bin/env python3
"""
Generate experiment statistics tables from metrics JSON files.

Reads session metrics for go-ethereum and avalanchego across three models
(GPT 5.2, Claude Sonnet 4.5, Gemini 3.1 Pro) and outputs a formatted
Markdown comparison table.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
HISTORY_DIR = REPO_ROOT / "agent" / "data" / "test_history"

SESSIONS = {
    "go-ethereum": {
        "GPT 5.2": "session_20260327_223400_132.json",
        "Claude Sonnet 4.5": "session_20260328_133256_055.json",
        "Gemini 3.1 Pro": "session_20260328_105651_100.json",
    },
    "avalanchego": {
        "GPT 5.2": "session_20260327_223344_762.json",
        "Claude Sonnet 4.5": "session_20260328_133250_552.json",
        "Gemini 3.1 Pro": "session_20260328_105746_546.json",
    },
}

MODEL_ORDER = ["GPT 5.2", "Claude Sonnet 4.5", "Gemini 3.1 Pro"]


def extract_metrics(filepath: Path) -> dict:
    with open(filepath) as f:
        data = json.load(f)

    start = datetime.fromisoformat(data["start_time"])
    end = datetime.fromisoformat(data["end_time"])
    duration_h = (end - start).total_seconds() / 3600

    iterations = data.get("iterations", [])
    total_bugs = sum(it.get("bugs_found", 0) for it in iterations)

    total_test_cases = sum(it.get("test_cases_generated", 0) for it in iterations)
    total_api_calls = 0
    total_tokens = 0
    total_cost = 0.0

    for it in iterations:
        for call in it.get("api_calls", []):
            total_api_calls += 1
            total_tokens += call.get("total_tokens", 0)
            total_cost += call.get("cost", 0.0)

    return {
        "model": data["model"],
        "status": data["status"],
        "duration_h": duration_h,
        "iterations": len(iterations),
        "bugs": total_bugs,
        "test_cases": total_test_cases,
        "api_calls": total_api_calls,
        "total_tokens": total_tokens,
        "total_cost": total_cost,
        "tokens_per_bug": total_tokens / total_bugs if total_bugs else None,
        "api_calls_per_bug": total_api_calls / total_bugs if total_bugs else None,
    }


def fmt_int(n: int) -> str:
    return f"{n:,}"


def fmt_float(n: float | None, precision: int = 1) -> str:
    if n is None:
        return "N/A"
    return f"{n:,.{precision}f}"


def fmt_dollar(n: float) -> str:
    return f"${n:,.2f}"


def render_table(repo: str, metrics_by_model: dict[str, dict]) -> str:
    rows = [
        ("(a) Bug 数量", lambda m: fmt_int(m["bugs"])),
        ("(b) 生成 Test Case 数", lambda m: fmt_int(m["test_cases"])),
        ("(c) Tokens/Bug", lambda m: fmt_float(m["tokens_per_bug"], 0)),
        ("(d) API 调用次数", lambda m: fmt_int(m["api_calls"])),
        ("(e) 总花费", lambda m: fmt_dollar(m["total_cost"])),
        ("(f) 总 Token 数", lambda m: fmt_int(m["total_tokens"])),
        ("(g) API 调用/Bug", lambda m: fmt_float(m["api_calls_per_bug"])),
        ("(h) Token/Bug", lambda m: fmt_float(m["tokens_per_bug"], 0)),
    ]

    header_cols = ["指标"] + MODEL_ORDER
    sep_cols = ["------"] + ["---:"] * len(MODEL_ORDER)

    lines = [f"### {repo}\n"]
    lines.append("| " + " | ".join(header_cols) + " |")
    lines.append("| " + " | ".join(sep_cols) + " |")

    for label, fn in rows:
        vals = [fn(metrics_by_model[model]) for model in MODEL_ORDER]
        lines.append("| " + " | ".join([label] + vals) + " |")

    return "\n".join(lines)


def main():
    all_tables: list[str] = []

    for repo in ["go-ethereum", "avalanchego"]:
        metrics_by_model: dict[str, dict] = {}
        for model_name, session_file in SESSIONS[repo].items():
            filepath = HISTORY_DIR / repo / "metrics" / session_file
            if not filepath.exists():
                print(f"WARNING: {filepath} not found, skipping", file=sys.stderr)
                continue
            metrics_by_model[model_name] = extract_metrics(filepath)

        all_tables.append(render_table(repo, metrics_by_model))

    output = "# 实验数据统计\n\n" + "\n\n".join(all_tables) + "\n"

    out_path = REPO_ROOT / "experiment_stats.md"
    out_path.write_text(output, encoding="utf-8")
    print(f"Written to {out_path}")


if __name__ == "__main__":
    main()
