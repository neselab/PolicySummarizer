#!/usr/bin/env python3
"""Run the five-size PolicySummarizer sample-generalization protocol.

This runner covers the 100, 500, 1,000, 1,500, and 2,000 sample conditions
shown in the paper. It deliberately stores each generated sample set, every
LLM candidate, parser diagnostics, model metadata, and a coverage-aware
summary. A rerun with a different model snapshot is a protocol replication,
not an exact replay of historical stochastic responses.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import inspect
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
Z3_RUNNER_PATH = ROOT / "experiments" / "z3_baseline" / "z3_model_enum.py"
DEFAULT_DATASET_DIR = ROOT / "Dataset"
DEFAULT_QUACKY_PATH = ROOT / "policysummarizer" / "quacky" / "quacky.py"
DEFAULT_OUTPUT_DIR = ROOT / "run_outputs" / "policysummarizer-sample-sweep"
DEFAULT_SAMPLE_SIZES = (100, 500, 1000, 1500, 2000)
DEFAULT_MODEL = "claude-sonnet-4-20250514"
PROTOCOL_VERSION = "policysummarizer-five-size-sweep-v1"


def load_z3_runner() -> Any:
    spec = importlib.util.spec_from_file_location("z3_model_enum", Z3_RUNNER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {Z3_RUNNER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


Z3_RUNNER = load_z3_runner()


def normalize_sample_sizes(values: list[int]) -> list[int]:
    """Reject invalid sizes and remove duplicates while preserving order."""
    if not values or any(value <= 0 for value in values):
        raise ValueError("Sample sizes must be positive integers")
    return list(dict.fromkeys(values))


def generate_dfa_samples(
    policy_path: Path,
    quacky_path: Path,
    *,
    sample_size: int,
    bound: int,
    min_length: int,
    max_length: int,
    timeout: int,
) -> tuple[list[str], dict[str, Any]]:
    """Ask Quacky/ABC for strings accepted by the policy DFA."""
    samples_path = quacky_path.parent / "P1_not_P2.models"
    samples_path.unlink(missing_ok=True)
    result = Z3_RUNNER.run_command(
        [
            sys.executable,
            str(quacky_path),
            "-p1",
            str(policy_path),
            "-b",
            str(bound),
            "-m",
            str(sample_size),
            "-m1",
            str(min_length),
            "-m2",
            str(max_length),
        ],
        cwd=quacky_path.parent,
        timeout=timeout,
    )
    trace = {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }
    if result.returncode != 0 or not samples_path.is_file():
        diagnostics = (result.stdout + "\n" + result.stderr).strip()
        raise Z3_RUNNER.ExperimentError(
            f"Sample generation failed for {policy_path.name} at n={sample_size} "
            f"(exit {result.returncode}).\n{diagnostics[-4000:]}"
        )

    samples = [
        line.strip()
        for line in samples_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    samples_path.unlink(missing_ok=True)
    if not samples:
        raise Z3_RUNNER.ExperimentError(
            f"Quacky produced no samples for {policy_path.name} at n={sample_size}"
        )
    return samples, trace


def summarize_budget(results: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Add cost-auditable call/token totals to the ordinary score summary."""
    summary = Z3_RUNNER.summarize_results(results)
    calls = 0
    input_tokens = 0
    output_tokens = 0
    elapsed_seconds = 0.0
    for result in results.values():
        elapsed_seconds += float(result.get("elapsed_seconds") or 0)
        for candidate in result.get("candidates", []):
            for attempt in candidate.get("attempts", []):
                response = attempt.get("response") or {}
                calls += 1
                input_tokens += int(response.get("input_tokens") or 0)
                output_tokens += int(response.get("output_tokens") or 0)
    summary.update(
        {
            "api_calls": calls,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "elapsed_seconds": round(elapsed_seconds, 3),
        }
    )
    return summary


def write_budget_results(
    output_dir: Path,
    results: dict[str, dict[str, Any]],
    run_config: dict[str, Any],
) -> dict[str, Any]:
    summary = summarize_budget(results)
    payload = {"run_config": run_config, "summary": summary, "policies": results}
    temporary = output_dir / "run_manifest.json.tmp"
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(output_dir / "run_manifest.json")
    (output_dir / "all_results.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8"
    )
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    return summary


def load_existing_results(output_dir: Path) -> dict[str, dict[str, Any]]:
    path = output_dir / "all_results.json"
    if not path.is_file():
        return {}
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise Z3_RUNNER.ExperimentError(f"Expected a JSON object in {path}")
    return loaded


def comparable_config(config: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "protocol_version",
        "sample_size",
        "model",
        "num_candidates",
        "syntax_repairs",
        "bound",
        "min_length",
        "max_length",
        "timeout",
        "enumerate_only",
    )
    return {key: config.get(key) for key in keys}


def validate_resume(output_dir: Path, config: dict[str, Any]) -> None:
    manifest_path = output_dir / "run_manifest.json"
    if not manifest_path.is_file():
        raise Z3_RUNNER.ExperimentError(
            f"Cannot safely resume {output_dir}: run_manifest.json is missing"
        )
    previous = json.loads(manifest_path.read_text(encoding="utf-8")).get(
        "run_config", {}
    )
    if comparable_config(previous) != comparable_config(config):
        raise Z3_RUNNER.ExperimentError(
            f"Resume configuration does not match {manifest_path}; use a new output directory"
        )


def current_git_commit() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def prepare_quacky_runtime(quacky_path: Path, output_dir: Path) -> Path:
    """Copy Quacky into a writable run directory for its legacy temp files."""
    runtime_dir = output_dir / "_quacky_runtime"
    runtime_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(quacky_path.parent, runtime_dir, dirs_exist_ok=True)
    runtime_quacky = runtime_dir / quacky_path.name
    if not runtime_quacky.is_file():
        raise Z3_RUNNER.ExperimentError(
            f"Quacky runtime copy is missing {runtime_quacky}"
        )
    return runtime_quacky


def process_policy(
    policy_path: Path,
    *,
    output_dir: Path,
    quacky_path: Path,
    client: Any | None,
    sample_size: int,
    model: str,
    num_candidates: int,
    syntax_repairs: int,
    bound: int,
    min_length: int,
    max_length: int,
    timeout: int,
    enumerate_only: bool,
) -> dict[str, Any]:
    started = time.monotonic()
    result: dict[str, Any] = {
        "policy_number": policy_path.stem,
        "policy_path": str(policy_path),
        "requested_samples": sample_size,
        "samples_count": 0,
        "model": None if enumerate_only else model,
        "success": False,
        "status": "started",
        "error": None,
        "candidates": [],
        "selected_candidate": None,
        "jaccard_similarity": None,
        "elapsed_seconds": None,
    }
    try:
        samples, generation_trace = generate_dfa_samples(
            policy_path,
            quacky_path,
            sample_size=sample_size,
            bound=bound,
            min_length=min_length,
            max_length=max_length,
            timeout=timeout,
        )
        samples_path = output_dir / f"policy_{policy_path.stem}_samples.txt"
        samples_path.write_text("\n".join(samples) + "\n", encoding="utf-8")
        result.update(
            samples_count=len(samples),
            samples_path=str(samples_path),
            sample_generation=generation_trace,
            status="samples_generated",
        )
        if enumerate_only:
            result.update(success=True, status="enumeration_complete")
            return result
        if client is None:
            raise Z3_RUNNER.ExperimentError("Anthropic client is required")

        candidates = [
            Z3_RUNNER.generate_and_score_candidate(
                candidate_index=index,
                samples=samples,
                policy_path=policy_path,
                output_dir=output_dir,
                quacky_path=quacky_path,
                client=client,
                model=model,
                bound=bound,
                timeout=timeout,
                syntax_repairs=syntax_repairs,
            )
            for index in range(1, num_candidates + 1)
        ]
        result["candidates"] = candidates
        selected = Z3_RUNNER.best_candidate(candidates)
        if selected is None:
            result.update(
                status="no_valid_regex",
                error="No candidate produced a parsable Jaccard result",
            )
            return result
        selected_path = output_dir / f"policy_{policy_path.stem}_regex.txt"
        selected_path.write_text(selected["regex"], encoding="utf-8")
        result.update(
            success=True,
            status="complete",
            selected_candidate=selected["candidate"],
            regex=selected["regex"],
            regex_path=str(selected_path),
            jaccard_similarity=selected["jaccard_similarity"],
        )
        return result
    except Exception as exc:
        result.update(status="error", error=f"{type(exc).__name__}: {exc}")
        return result
    finally:
        result["elapsed_seconds"] = round(time.monotonic() - started, 3)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-dir", type=Path, default=DEFAULT_DATASET_DIR)
    parser.add_argument("--quacky-path", type=Path, default=DEFAULT_QUACKY_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--sample-sizes",
        type=int,
        nargs="+",
        default=list(DEFAULT_SAMPLE_SIZES),
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--num-candidates", type=int, default=5)
    parser.add_argument("--syntax-repairs", type=int, default=1)
    parser.add_argument("--bound", type=int, default=100)
    parser.add_argument("--min-length", type=int, default=10)
    parser.add_argument("--max-length", type=int, default=500)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--start-from", type=int, default=0)
    parser.add_argument("--end-at", type=int, default=40)
    parser.add_argument("--enumerate-only", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    sample_sizes = normalize_sample_sizes(args.sample_sizes)
    if args.num_candidates <= 0 or args.syntax_repairs < 0:
        raise Z3_RUNNER.ExperimentError(
            "Candidate count must be positive and repairs cannot be negative"
        )
    if not args.dataset_dir.is_dir() or not args.quacky_path.is_file():
        raise Z3_RUNNER.ExperimentError("Dataset directory or Quacky path is missing")
    policies = Z3_RUNNER.numeric_policy_files(
        args.dataset_dir, args.start_from, args.end_at
    )
    if not policies:
        raise Z3_RUNNER.ExperimentError("No numeric policy files matched the range")

    dry_config = {
        "sample_sizes": sample_sizes,
        "policies": len(policies),
        "model": None if args.enumerate_only else args.model,
        "num_candidates": 0 if args.enumerate_only else args.num_candidates,
        "maximum_initial_api_calls": (
            0 if args.enumerate_only else len(policies) * len(sample_sizes) * args.num_candidates
        ),
        "output_dir": str(args.output_dir),
    }
    if args.dry_run:
        print(json.dumps(dry_config, indent=2))
        return 0
    if shutil.which("abc") is None:
        raise Z3_RUNNER.ExperimentError(
            "ABC solver executable not found on PATH. Use the documented Docker command."
        )

    source_quacky_path = args.quacky_path.resolve()
    runtime_quacky_path = prepare_quacky_runtime(args.quacky_path, args.output_dir)

    client = None if args.enumerate_only else Z3_RUNNER.build_client()
    source_hash = hashlib.sha256(
        (
            inspect.getsource(Z3_RUNNER.initial_regex_prompt)
            + inspect.getsource(Z3_RUNNER.syntax_repair_prompt)
        ).encode("utf-8")
    ).hexdigest()
    sweep_summaries: dict[str, Any] = {}

    for sample_size in sample_sizes:
        budget_dir = args.output_dir / f"samples-{sample_size}"
        budget_dir.mkdir(parents=True, exist_ok=True)
        results = load_existing_results(budget_dir)
        if results and not args.resume:
            raise Z3_RUNNER.ExperimentError(
                f"{budget_dir} already contains results; use --resume or another output directory"
            )
        config = {
            "protocol_version": PROTOCOL_VERSION,
            "started_at_utc": datetime.now(timezone.utc).isoformat(),
            "git_commit": current_git_commit(),
            "dataset_dir": str(args.dataset_dir.resolve()),
            "quacky_source_path": str(source_quacky_path),
            "quacky_runtime_path": str(runtime_quacky_path.resolve()),
            "sample_size": sample_size,
            "model": None if args.enumerate_only else args.model,
            "num_candidates": 0 if args.enumerate_only else args.num_candidates,
            "syntax_repairs": 0 if args.enumerate_only else args.syntax_repairs,
            "bound": args.bound,
            "min_length": args.min_length,
            "max_length": args.max_length,
            "timeout": args.timeout,
            "enumerate_only": args.enumerate_only,
            "prompt_templates_sha256": source_hash,
        }
        if args.resume and results:
            validate_resume(budget_dir, config)

        print(f"\n=== Sample size {sample_size}: {len(policies)} policies ===")
        for index, policy_path in enumerate(policies, start=1):
            previous = results.get(policy_path.stem)
            if args.resume and previous and previous.get("success"):
                print(f"[{index}/{len(policies)}] policy {policy_path.stem}: SKIP")
                continue
            result = process_policy(
                policy_path,
                output_dir=budget_dir,
                quacky_path=runtime_quacky_path,
                client=client,
                sample_size=sample_size,
                model=args.model,
                num_candidates=args.num_candidates,
                syntax_repairs=args.syntax_repairs,
                bound=args.bound,
                min_length=args.min_length,
                max_length=args.max_length,
                timeout=args.timeout,
                enumerate_only=args.enumerate_only,
            )
            results[policy_path.stem] = result
            write_budget_results(budget_dir, results, config)
            status = "PASS" if result["success"] else "FAIL"
            print(f"[{index}/{len(policies)}] policy {policy_path.stem}: {status}")
        sweep_summaries[str(sample_size)] = write_budget_results(
            budget_dir, results, config
        )

    sweep_payload = {
        "protocol_version": PROTOCOL_VERSION,
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "sample_sizes": sample_sizes,
        "model": None if args.enumerate_only else args.model,
        "summaries": sweep_summaries,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "sweep_summary.json").write_text(
        json.dumps(sweep_payload, indent=2), encoding="utf-8"
    )
    print(json.dumps(sweep_payload, indent=2))
    return 0 if all(
        summary["policies_successful"] == len(policies)
        for summary in sweep_summaries.values()
    ) else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, Z3_RUNNER.ExperimentError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)
