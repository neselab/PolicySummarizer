"""API-free tests for the five-size protocol runner."""

from __future__ import annotations

import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("run_protocol.py")
SPEC = importlib.util.spec_from_file_location("sample_size_protocol", MODULE_PATH)
assert SPEC and SPEC.loader
SWEEP = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SWEEP)


def test_default_sample_sizes_match_paper_figure() -> None:
    assert SWEEP.DEFAULT_SAMPLE_SIZES == (100, 500, 1000, 1500, 2000)


def test_sample_sizes_are_positive_and_deduplicated() -> None:
    assert SWEEP.normalize_sample_sizes([100, 500, 100, 1000]) == [100, 500, 1000]


def test_summary_counts_api_usage_and_keeps_perfect_scores() -> None:
    summary = SWEEP.summarize_budget(
        {
            "0": {
                "success": True,
                "jaccard_similarity": "1",
                "elapsed_seconds": 1.5,
                "candidates": [
                    {
                        "attempts": [
                            {"response": {"input_tokens": 10, "output_tokens": 2}}
                        ]
                    }
                ],
            },
            "1": {
                "success": True,
                "jaccard_similarity": "0.5",
                "elapsed_seconds": 2,
                "candidates": [],
            },
        }
    )
    assert summary["mean_jaccard_all_usable"] == "0.75"
    assert summary["perfect_matches"] == 1
    assert summary["api_calls"] == 1
    assert summary["input_tokens"] == 10
    assert summary["output_tokens"] == 2
    assert summary["elapsed_seconds"] == 3.5
