"""
run_eval.py -- RAGAS-based evaluation script for the RAG pipeline.

Usage:
    python evaluation/run_eval.py

Steps:
  1. Load test_cases.json
  2. For each case call run_rag() directly (no HTTP)
  3. Build a RAGAS Dataset with question / answer / contexts / ground_truth
  4. Run evaluate() with faithfulness + answer_relevancy metrics
  5. Print a results table
  6. Assert faithfulness >= 0.85 and answer_relevancy >= 0.80
  7. Write report.md to evaluation/

Requires the backend package to be importable (run from project root or with
PYTHONPATH=backend set).
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Ensure backend is importable when run from project root
_project_root = Path(__file__).parent.parent
_backend = _project_root / "backend"
if str(_backend) not in sys.path:
    sys.path.insert(0, str(_backend))

EVAL_DIR = Path(__file__).parent
TEST_CASES_PATH = EVAL_DIR / "test_cases.json"
REPORT_PATH = EVAL_DIR / "report.md"

FAITHFULNESS_THRESHOLD = float(os.environ.get("EVAL_FAITHFULNESS_THRESHOLD", "0.85"))
RELEVANCY_THRESHOLD = float(os.environ.get("EVAL_RELEVANCY_THRESHOLD", "0.80"))


def load_test_cases() -> list[dict]:
    with open(TEST_CASES_PATH, encoding="utf-8") as f:
        return json.load(f)


async def run_single_case(case: dict) -> dict[str, Any]:
    """
    Run the RAG pipeline for one test case and return result fields.

    Returns a dict with question, answer, contexts, ground_truth.
    """
    from app.orchestrator.graph import run_rag  # type: ignore[import]

    question: str = case["question"]
    groups: list[str] = case.get("groups", [])
    ground_truth: str = case["expected_answer"]

    print(f"  Running: {question[:70]}...")
    try:
        state = await run_rag(
            question=question,
            user_id="eval-user",
            user_groups=groups,
        )
        answer = state.get("answer") or ""
        # Extract chunk texts as contexts
        contexts = [
            (c.text if hasattr(c, "text") else c.get("text", ""))
            for c in state.get("reranked_chunks", [])
        ]
    except Exception as exc:
        print(f"    ERROR: {exc}")
        answer = f"[Pipeline error: {exc}]"
        contexts = []

    return {
        "question": question,
        "answer": answer,
        "contexts": contexts or ["[no context retrieved]"],
        "ground_truth": ground_truth,
    }


async def collect_results(cases: list[dict]) -> list[dict[str, Any]]:
    results = []
    for case in cases:
        r = await run_single_case(case)
        results.append(r)
    return results


def build_ragas_dataset(results: list[dict[str, Any]]):
    """Build a RAGAS-compatible HuggingFace Dataset from result dicts."""
    from datasets import Dataset  # type: ignore[import]

    return Dataset.from_dict(
        {
            "question": [r["question"] for r in results],
            "answer": [r["answer"] for r in results],
            "contexts": [r["contexts"] for r in results],
            "ground_truth": [r["ground_truth"] for r in results],
        }
    )


def run_ragas(dataset) -> dict[str, float]:
    """Run RAGAS evaluation and return metric scores."""
    from ragas import evaluate  # type: ignore[import]
    from ragas.metrics import faithfulness, answer_relevancy  # type: ignore[import]

    result = evaluate(
        dataset,
        metrics=[faithfulness, answer_relevancy],
    )
    return dict(result)


def write_report(
    scores: dict[str, float],
    results: list[dict[str, Any]],
    passed: bool,
) -> None:
    """Write a markdown report to evaluation/report.md."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# RAG Evaluation Report",
        "",
        f"**Generated:** {ts}",
        "",
        "## Summary",
        "",
        f"| Metric | Score | Threshold | Status |",
        f"|--------|-------|-----------|--------|",
    ]

    for metric, threshold, label in [
        ("faithfulness", FAITHFULNESS_THRESHOLD, "Faithfulness"),
        ("answer_relevancy", RELEVANCY_THRESHOLD, "Answer Relevancy"),
    ]:
        score = scores.get(metric, 0.0)
        status = "PASS" if score >= threshold else "FAIL"
        lines.append(f"| {label} | {score:.4f} | {threshold:.2f} | {status} |")

    lines += [
        "",
        f"**Overall:** {'PASS' if passed else 'FAIL'}",
        "",
        "## Per-Question Results",
        "",
        "| # | Question | Answer (truncated) | Contexts |",
        "|---|----------|--------------------|----------|",
    ]

    for i, r in enumerate(results, 1):
        q = r["question"][:60].replace("|", "\\|")
        a = (r["answer"] or "")[:80].replace("|", "\\|")
        ctx_count = len(r["contexts"])
        lines.append(f"| {i} | {q} | {a}... | {ctx_count} chunks |")

    lines.append("")
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nReport written to {REPORT_PATH}")


async def main() -> None:
    print("Loading test cases...")
    cases = load_test_cases()
    print(f"Found {len(cases)} test cases.\n")

    print("Running RAG pipeline for each case...")
    results = await collect_results(cases)

    print("\nBuilding RAGAS dataset...")
    dataset = build_ragas_dataset(results)

    print("Running RAGAS evaluation (faithfulness + answer_relevancy)...")
    scores = run_ragas(dataset)

    print("\n=== RAGAS Results ===")
    for k, v in scores.items():
        print(f"  {k}: {v:.4f}")

    faith = scores.get("faithfulness", 0.0)
    relev = scores.get("answer_relevancy", 0.0)
    passed = faith >= FAITHFULNESS_THRESHOLD and relev >= RELEVANCY_THRESHOLD

    write_report(scores, results, passed)

    if not passed:
        print(
            f"\nEVALUATION FAILED: "
            f"faithfulness={faith:.4f} (need >={FAITHFULNESS_THRESHOLD}), "
            f"answer_relevancy={relev:.4f} (need >={RELEVANCY_THRESHOLD})"
        )
        sys.exit(1)

    print(f"\nEVALUATION PASSED: all thresholds met.")


if __name__ == "__main__":
    asyncio.run(main())
