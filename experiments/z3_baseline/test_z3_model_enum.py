"""Focused tests for the reproducible Z3 baseline runner."""

from __future__ import annotations

import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("z3_model_enum.py")
SPEC = importlib.util.spec_from_file_location("z3_model_enum", MODULE_PATH)
assert SPEC and SPEC.loader
z3_model_enum = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(z3_model_enum)


def test_enumerates_requested_number_of_distinct_resource_models(tmp_path: Path) -> None:
    smt_path = tmp_path / "small.smt2"
    smt_path.write_text(
        """(set-logic QF_S)
(declare-fun resource () String)
(assert (or (= resource \"a\") (= resource \"b\") (= resource \"c\")))
""",
        encoding="utf-8",
    )

    models = z3_model_enum.enumerate_resource_models(smt_path, max_models=2, seed=0)

    assert len(models) == 2
    assert len(set(models)) == 2


def test_summary_includes_perfect_matches_in_mean() -> None:
    summary = z3_model_enum.summarize_results(
        {
            "0": {"success": True, "jaccard_similarity": "1"},
            "1": {"success": True, "jaccard_similarity": "0.5"},
            "2": {"success": False, "jaccard_similarity": None, "error": "no models"},
        }
    )

    assert summary["policies_attempted"] == 3
    assert summary["policies_with_jaccard"] == 2
    assert summary["perfect_matches"] == 1
    assert summary["mean_jaccard_all_usable"] == "0.75"
    assert summary["unscored_policies"] == ["2"]


def test_best_candidate_uses_highest_jaccard() -> None:
    selected = z3_model_enum.best_candidate(
        [
            {"candidate": 1, "valid": True, "jaccard_similarity": "0.25"},
            {"candidate": 2, "valid": False, "jaccard_similarity": None},
            {"candidate": 3, "valid": True, "jaccard_similarity": "1"},
        ]
    )

    assert selected is not None
    assert selected["candidate"] == 3
