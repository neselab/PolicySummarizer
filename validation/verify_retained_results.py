#!/usr/bin/env python3
"""Audit the retained, API-free result records shipped in this repository."""

from __future__ import annotations

import argparse
import csv
import io
import json
import statistics
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def load_json(relative_path: str) -> Any:
    return json.loads((ROOT / relative_path).read_text(encoding="utf-8"))


def summarize_policy_results(relative_path: str) -> dict[str, Any]:
    records = load_json(relative_path)
    scores = [
        float(record["jaccard_similarity"])
        for record in records
        if record.get("jaccard_similarity") is not None
    ]
    return {
        "records": len(records),
        "scored": len(scores),
        "missing_scores": len(records) - len(scores),
        "exact_matches": sum(score == 1.0 for score in scores),
        "exact_match_rate": sum(score == 1.0 for score in scores) / len(scores),
        "mean_jaccard": statistics.fmean(scores),
        "median_jaccard": statistics.median(scores),
        "satisfiability": dict(Counter(str(record.get("satisfiability")) for record in records)),
    }


def summarize_mutations() -> dict[str, Any]:
    records = load_json(
        "experiments/policy_summarizer/results_mutation/mutation_results.json"
    )
    verdicts = Counter(record.get("verdict") for record in records)

    directions = {}
    for label, sat_field, score_field in (
        ("original_not_mutant", "p1_not_p2_sat", "p1_not_p2_jaccard"),
        ("mutant_not_original", "not_p1_p2_sat", "not_p1_p2_jaccard"),
    ):
        satisfiable = [record for record in records if record.get(sat_field) == "sat"]
        scores = [
            float(record[score_field])
            for record in satisfiable
            if record.get(score_field) is not None
        ]
        directions[label] = {
            "satisfiable": len(satisfiable),
            "scored": len(scores),
            "mean_jaccard": statistics.fmean(scores),
            "median_jaccard": statistics.median(scores),
            "exact_matches": sum(score == 1.0 for score in scores),
            "zero_matches": sum(score == 0.0 for score in scores),
        }

    return {
        "records": len(records),
        "more_permissive": verdicts["Policy 1 is less permissive than Policy 2."],
        "less_permissive": verdicts["Policy 1 is more permissive than Policy 2."],
        "incomparable": verdicts["Policy 1 and Policy 2 do not subsume each other."],
        "equivalent": verdicts["Policy 1 and Policy 2 are equivalent."],
        "timeouts": sum(record.get("verdict") is None for record in records),
        "directions": directions,
    }


def summarize_user_study() -> dict[str, Any]:
    archive_path = ROOT / "Dataset" / "user_study" / "policy_summarizer_user_study.zip"
    with zipfile.ZipFile(archive_path) as archive:
        with archive.open("user-study.zip/qualitative_data.csv") as raw:
            rows = list(csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8")))
    participant_ids = [row["participantId"] for row in rows]
    return {
        "qualitative_rows": len(rows),
        "unique_participants": len(set(participant_ids)),
    }


def summarize_cpca() -> dict[str, Any]:
    records = load_json(
        "experiments/policy_comprehension/experiment_results/experiment_0_results.json"
    )
    return {
        "records": len(records),
        "models": dict(Counter(record.get("llm_model") for record in records)),
        "completed": sum(bool(record.get("results")) for record in records),
        "errors": sum(bool(record.get("error")) for record in records),
    }


def collect() -> dict[str, Any]:
    policy_files = {
        "aws_direct": "experiments/policy_summarizer/results_aws/results_aws_regex_based.json",
        "aws_sample": "experiments/policy_summarizer/results_aws/results_aws.json",
        "azure_direct": "experiments/policy_summarizer/regex_results/results_azure.json",
        "azure_sample": "experiments/policy_summarizer/string_results/results_azure.json",
        "gcp_direct": "experiments/policy_summarizer/regex_results/results_gcp.json",
        "gcp_sample": "experiments/policy_summarizer/string_results/results_gcp.json",
    }
    return {
        "policy_summarization": {
            name: summarize_policy_results(path) for name, path in policy_files.items()
        },
        "mutation_comparison": summarize_mutations(),
        "user_study": summarize_user_study(),
        "cpca": summarize_cpca(),
    }


def validate(summary: dict[str, Any]) -> None:
    policies = summary["policy_summarization"]
    assert policies["aws_direct"]["records"] == 587
    assert policies["aws_direct"]["scored"] == 546
    assert policies["aws_direct"]["exact_matches"] == 497
    assert policies["aws_sample"]["exact_matches"] == 392
    assert policies["azure_direct"]["records"] == 100
    assert policies["azure_direct"]["exact_matches"] == 98
    assert policies["azure_sample"]["exact_matches"] == 93
    assert policies["gcp_direct"]["records"] == 100
    assert policies["gcp_direct"]["exact_matches"] == 94
    assert policies["gcp_sample"]["exact_matches"] == 92

    mutations = summary["mutation_comparison"]
    assert mutations["records"] == 546
    assert (
        mutations["more_permissive"],
        mutations["less_permissive"],
        mutations["incomparable"],
        mutations["equivalent"],
        mutations["timeouts"],
    ) == (302, 48, 44, 126, 26)
    assert mutations["directions"]["original_not_mutant"]["satisfiable"] == 92
    assert mutations["directions"]["mutant_not_original"]["satisfiable"] == 346

    assert summary["user_study"]["unique_participants"] == 41
    assert summary["cpca"]["records"] == 41


def print_human(summary: dict[str, Any]) -> None:
    print("Retained policy-summarization results")
    print("condition       records scored exact exact-rate mean-J median-J")
    for name, result in summary["policy_summarization"].items():
        print(
            f"{name:15} {result['records']:7d} {result['scored']:6d} "
            f"{result['exact_matches']:5d} {result['exact_match_rate']:10.4f} "
            f"{result['mean_jaccard']:6.4f} {result['median_jaccard']:8.4f}"
        )

    mutations = summary["mutation_comparison"]
    print("\nMutation comparison")
    print(
        "records={records} more={more_permissive} less={less_permissive} "
        "incomparable={incomparable} equal={equivalent} timeouts={timeouts}".format(
            **mutations
        )
    )
    for name, result in mutations["directions"].items():
        print(
            f"{name}: sat={result['satisfiable']} scored={result['scored']} "
            f"mean-J={result['mean_jaccard']:.4f} median-J={result['median_jaccard']:.4f} "
            f"exact={result['exact_matches']} zero={result['zero_matches']}"
        )

    print("\nRetained supporting records")
    print(
        f"user-study unique participants: "
        f"{summary['user_study']['unique_participants']}"
    )
    print(
        f"Retained CPCA records: {summary['cpca']['records']} total, "
        f"{summary['cpca']['completed']} completed, {summary['cpca']['errors']} errors"
    )
    print("\nRETAINED RESULT AUDIT: PASS")
    print("PASS confirms the released files and statistics shown above.")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = parser.parse_args()

    summary = collect()
    validate(summary)
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print_human(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
