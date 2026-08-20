#!/usr/bin/env python3
"""Reproduce the Z3 + LLM policy-summarization baseline.

For each original policy, this runner:

1. asks Quacky to emit an SMT-LIB encoding;
2. enumerates up to ``--max-models`` satisfying resource strings with Z3;
3. asks Claude to infer regex candidates from those strings;
4. repairs candidates only when Quacky cannot parse/evaluate them;
5. selects the candidate with the highest measured Jaccard similarity; and
6. persists all inputs, candidates, diagnostics, and aggregate statistics.

The default configuration matches the ISSRE paper protocol: 1,000 Z3 models,
Claude 4 Sonnet, five candidates, and one syntax-repair attempt. Paths are
repository-relative so the experiment does not depend on the original WSL
checkout.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal, getcontext
from pathlib import Path
from typing import Any

import anthropic
from dotenv import load_dotenv
from z3 import Solver, String, sat

try:
    from tqdm import tqdm
except ImportError:  # The artifact Docker image does not need tqdm for correctness.
    class _PlainProgress:
        @staticmethod
        def write(message: str) -> None:
            print(message)

        def __new__(cls, iterable: Any, **_: Any) -> Any:
            return iterable

    tqdm = _PlainProgress


getcontext().prec = 100

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
DEFAULT_DATASET_DIR = REPO_ROOT / "Dataset"
DEFAULT_QUACKY_PATH = REPO_ROOT / "artifacts" / "src" / "quacky.py"
DEFAULT_OUTPUT_DIR = SCRIPT_DIR / "results-1000"
DEFAULT_MODEL = "claude-sonnet-4-20250514"
PROTOCOL_VERSION = "z3-llm-baseline-v1"

JACCARD_NUMERATOR_RE = re.compile(r"jaccard_numerator\s+:\s+(\d+)")
JACCARD_DENOMINATOR_RE = re.compile(r"jaccard_denominator\s+:\s+(\d+)")
BASELINE_COUNT_RE = re.compile(r"Baseline Regex Count\s+:\s+(\d+)")
SYNTHESIZED_COUNT_RE = re.compile(r"Synthesized Regex Count\s+:\s+(\d+)")


class ExperimentError(RuntimeError):
    """A reproducibility or experiment-execution error."""


def run_command(command: list[str], *, cwd: Path, timeout: int) -> subprocess.CompletedProcess[str]:
    """Run a command and retain both output streams for the artifact trace."""
    try:
        return subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise ExperimentError(f"Command timed out after {timeout}s: {' '.join(command)}") from exc


def generate_smt_file(policy_path: Path, quacky_path: Path, *, timeout: int) -> Path:
    """Generate a fresh SMT-LIB file without unnecessarily invoking ABC."""
    if not policy_path.is_file():
        raise ExperimentError(f"Policy file not found: {policy_path}")
    if not quacky_path.is_file():
        raise ExperimentError(f"Quacky entry point not found: {quacky_path}")

    quacky_dir = quacky_path.parent
    translator_path = quacky_dir / "translator.py"
    if not translator_path.is_file():
        raise ExperimentError(f"Quacky translator not found: {translator_path}")
    smt_path = quacky_dir / "output_1.smt2"
    smt_path.unlink(missing_ok=True)

    result = run_command(
        [
            sys.executable,
            str(translator_path),
            "--smt-lib",
            "-p1",
            str(policy_path),
        ],
        cwd=quacky_dir,
        timeout=timeout,
    )
    if result.returncode != 0 or not smt_path.is_file():
        diagnostics = (result.stdout + "\n" + result.stderr).strip()
        raise ExperimentError(
            f"Quacky translator failed to generate SMT for {policy_path.name} "
            f"(exit {result.returncode}).\n{diagnostics[-4000:]}"
        )
    return smt_path


def enumerate_resource_models(smt_path: Path, *, max_models: int, seed: int) -> list[str]:
    """Enumerate distinct satisfying values of the SMT ``resource`` string."""
    solver = Solver()
    solver.set(random_seed=seed)
    try:
        solver.from_file(str(smt_path))
    except Exception as exc:
        raise ExperimentError(f"Z3 could not parse {smt_path}: {exc}") from exc

    if solver.check() != sat:
        return []

    resource = String("resource")
    models: list[str] = []
    seen: set[str] = set()

    while len(models) < max_models:
        model = solver.model()
        value = model.eval(resource, model_completion=True)
        rendered = str(value)
        if rendered in seen:
            raise ExperimentError("Z3 repeated a blocked resource model; enumeration cannot progress")
        seen.add(rendered)
        models.append(rendered)
        solver.add(resource != value)
        if solver.check() != sat:
            break

    return models


def initial_regex_prompt(samples: list[str]) -> str:
    """Use the sample-to-regex prompt structure from PolicySummarizer."""
    return f"""You are an expert in regular expressions and cloud security policies.

I will provide you with sample strings representing cloud resource paths. Generate a regex that matches these strings and similar ones.

SAMPLE STRINGS:
{chr(10).join(samples)}

Analyze the samples and generate a regex pattern that matches all of them. Look for common patterns and variable parts.

IMPORTANT: Respond with ONLY the regex on a single line. No explanation, no markdown, no backticks, no anchors (^ or $).
Give the output as a raw regex. Do not assume this regex will be used in Python or any standard regex engine. Output a plain, raw regex pattern as would be used with grep or sed."""


def syntax_repair_prompt(samples: list[str], previous_regex: str, diagnostics: str) -> str:
    """Ask for syntax repair without revealing semantic ground-truth counts."""
    return f"""You are an expert in regular expressions and cloud security policies.

The regex below could not be parsed or evaluated by the policy analysis tool. Correct only the regex syntax while preserving the intended pattern represented by the sample strings.

SAMPLE STRINGS:
{chr(10).join(samples)}

PREVIOUS REGEX:
{previous_regex}

PARSER DIAGNOSTIC:
{diagnostics[-2000:]}

IMPORTANT: Respond with ONLY the corrected regex on a single line. No explanation, no markdown, no backticks, no anchors (^ or $)."""


def extract_text_response(response: Any) -> str:
    """Extract and normalize the first text block from an Anthropic response."""
    for block in response.content:
        if getattr(block, "type", None) == "text":
            text = block.text.strip()
            if text.startswith("```"):
                text = re.sub(r"^```(?:regex)?\s*", "", text)
                text = re.sub(r"\s*```$", "", text)
            text = text.strip()
            if text.startswith("^"):
                text = text[1:]
            if text.endswith("$") and not text.endswith(r"\$"):
                text = text[:-1]
            return text.strip()
    raise ExperimentError("Claude returned no text regex")


def call_claude_with_trace(
    client: anthropic.Anthropic, *, model: str, prompt: str
) -> tuple[str, dict[str, Any]]:
    """Generate one regex and retain non-secret API metadata for the run trace."""
    response = client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    usage = getattr(response, "usage", None)
    trace = {
        "response_id": getattr(response, "id", None),
        "model": getattr(response, "model", model),
        "stop_reason": getattr(response, "stop_reason", None),
        "input_tokens": getattr(usage, "input_tokens", None),
        "output_tokens": getattr(usage, "output_tokens", None),
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
    }
    return extract_text_response(response), trace


def call_claude(client: anthropic.Anthropic, *, model: str, prompt: str) -> str:
    """Generate one regex candidate with the paper's Claude model family."""
    regex, _ = call_claude_with_trace(client, model=model, prompt=prompt)
    return regex


def evaluate_regex(
    policy_path: Path,
    regex_path: Path,
    quacky_path: Path,
    *,
    bound: int,
    timeout: int,
) -> dict[str, Any]:
    """Evaluate a regex against the policy and parse Quacky's Jaccard output."""
    result = run_command(
        [
            sys.executable,
            str(quacky_path),
            "-p1",
            str(policy_path),
            "-b",
            str(bound),
            "-cr",
            str(regex_path),
        ],
        cwd=quacky_path.parent,
        timeout=timeout,
    )
    diagnostics = (result.stdout + "\n" + result.stderr).strip()
    numerator_match = JACCARD_NUMERATOR_RE.search(diagnostics)
    denominator_match = JACCARD_DENOMINATOR_RE.search(diagnostics)

    evaluation: dict[str, Any] = {
        "returncode": result.returncode,
        "diagnostics": diagnostics,
        "valid": False,
        "jaccard_numerator": None,
        "jaccard_denominator": None,
        "jaccard_similarity": None,
        "baseline_regex_count": None,
        "synthesized_regex_count": None,
    }
    if not numerator_match or not denominator_match:
        return evaluation

    numerator = Decimal(numerator_match.group(1))
    denominator = Decimal(denominator_match.group(1))
    if denominator <= 0:
        return evaluation

    baseline_match = BASELINE_COUNT_RE.search(diagnostics)
    synthesized_match = SYNTHESIZED_COUNT_RE.search(diagnostics)
    evaluation.update(
        {
            "valid": True,
            "jaccard_numerator": str(numerator),
            "jaccard_denominator": str(denominator),
            "jaccard_similarity": str(numerator / denominator),
            "baseline_regex_count": baseline_match.group(1) if baseline_match else None,
            "synthesized_regex_count": synthesized_match.group(1) if synthesized_match else None,
        }
    )
    return evaluation


def generate_and_score_candidate(
    *,
    candidate_index: int,
    samples: list[str],
    policy_path: Path,
    output_dir: Path,
    quacky_path: Path,
    client: anthropic.Anthropic,
    model: str,
    bound: int,
    timeout: int,
    syntax_repairs: int,
) -> dict[str, Any]:
    """Generate one independent candidate and repair syntax when necessary."""
    attempts: list[dict[str, Any]] = []
    prompt = initial_regex_prompt(samples)

    for repair_index in range(syntax_repairs + 1):
        regex, response_trace = call_claude_with_trace(
            client, model=model, prompt=prompt
        )
        regex_path = output_dir / f"policy_{policy_path.stem}_candidate_{candidate_index}_attempt_{repair_index}.txt"
        regex_path.write_text(regex, encoding="utf-8")
        evaluation = evaluate_regex(
            policy_path,
            regex_path,
            quacky_path,
            bound=bound,
            timeout=timeout,
        )
        attempts.append(
            {
                "attempt": repair_index + 1,
                "regex": regex,
                "regex_path": str(regex_path),
                "response": response_trace,
                "evaluation": evaluation,
            }
        )
        if evaluation["valid"]:
            break
        if repair_index < syntax_repairs:
            prompt = syntax_repair_prompt(samples, regex, evaluation["diagnostics"])

    final = attempts[-1]
    return {
        "candidate": candidate_index,
        "attempts": attempts,
        "valid": final["evaluation"]["valid"],
        "regex": final["regex"],
        "regex_path": final["regex_path"],
        "jaccard_similarity": final["evaluation"]["jaccard_similarity"],
    }


def best_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Select the highest-Jaccard valid candidate, retaining ties by generation order."""
    valid = [candidate for candidate in candidates if candidate["valid"]]
    if not valid:
        return None
    return max(valid, key=lambda candidate: Decimal(candidate["jaccard_similarity"]))


def process_policy(
    policy_path: Path,
    *,
    output_dir: Path,
    quacky_path: Path,
    client: anthropic.Anthropic | None,
    max_models: int,
    model: str,
    num_candidates: int,
    syntax_repairs: int,
    bound: int,
    timeout: int,
    seed: int,
    enumerate_only: bool,
) -> dict[str, Any]:
    """Run the complete baseline pipeline for one policy."""
    started = time.monotonic()
    policy_number = policy_path.stem
    result: dict[str, Any] = {
        "policy_number": policy_number,
        "policy_path": str(policy_path),
        "requested_models": max_models,
        "models_count": 0,
        "model": None if enumerate_only else model,
        "num_candidates": 0 if enumerate_only else num_candidates,
        "syntax_repairs": 0 if enumerate_only else syntax_repairs,
        "success": False,
        "status": "started",
        "error": None,
        "candidates": [],
        "selected_candidate": None,
        "jaccard_similarity": None,
        "elapsed_seconds": None,
    }

    try:
        smt_path = generate_smt_file(policy_path, quacky_path, timeout=timeout)
        saved_smt_path = output_dir / f"policy_{policy_number}.smt2"
        shutil.copy2(smt_path, saved_smt_path)
        result["smt_path"] = str(saved_smt_path)

        models = enumerate_resource_models(smt_path, max_models=max_models, seed=seed)
        if not models:
            result.update(status="no_satisfying_resource_models", error="No satisfying resource models found")
            return result

        models_path = output_dir / f"policy_{policy_number}_models.txt"
        models_path.write_text("\n".join(models) + "\n", encoding="utf-8")
        result.update(models_count=len(models), models_path=str(models_path), status="models_enumerated")

        if enumerate_only:
            result.update(success=True, status="enumeration_complete")
            return result
        if client is None:
            raise ExperimentError("Anthropic client is required for regex generation")

        candidates = []
        for candidate_index in range(1, num_candidates + 1):
            candidates.append(
                generate_and_score_candidate(
                    candidate_index=candidate_index,
                    samples=models,
                    policy_path=policy_path,
                    output_dir=output_dir,
                    quacky_path=quacky_path,
                    client=client,
                    model=model,
                    bound=bound,
                    timeout=timeout,
                    syntax_repairs=syntax_repairs,
                )
            )
        result["candidates"] = candidates
        selected = best_candidate(candidates)
        if selected is None:
            result.update(status="no_valid_regex", error="No candidate produced a parsable Jaccard result")
            return result

        selected_path = output_dir / f"policy_{policy_number}_regex.txt"
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


def summarize_results(results: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Compute coverage-aware statistics without excluding perfect matches."""
    scored: list[tuple[str, Decimal]] = []
    for policy_number, result in results.items():
        value = result.get("jaccard_similarity")
        if value is not None:
            scored.append((policy_number, Decimal(str(value))))

    similarities = [value for _, value in scored]
    mean = sum(similarities, Decimal(0)) / len(similarities) if similarities else None
    ordered = sorted(similarities)
    if not ordered:
        median = None
    elif len(ordered) % 2:
        median = ordered[len(ordered) // 2]
    else:
        midpoint = len(ordered) // 2
        median = (ordered[midpoint - 1] + ordered[midpoint]) / 2

    return {
        "policies_attempted": len(results),
        "policies_successful": sum(bool(result.get("success")) for result in results.values()),
        "policies_with_jaccard": len(scored),
        "perfect_matches": sum(value == 1 for value in similarities),
        "mean_jaccard_all_usable": str(mean) if mean is not None else None,
        "median_jaccard_all_usable": str(median) if median is not None else None,
        "unscored_policies": sorted(
            [policy_number for policy_number in results if policy_number not in {number for number, _ in scored}],
            key=int,
        ),
        "failed_policies": {
            policy_number: result.get("error") or result.get("status")
            for policy_number, result in sorted(results.items(), key=lambda item: int(item[0]))
            if not result.get("success")
        },
    }


def write_results(output_dir: Path, results: dict[str, dict[str, Any]], run_config: dict[str, Any]) -> None:
    """Persist policy-level results and an aggregate manifest atomically."""
    summary = summarize_results(results)
    payload = {"run_config": run_config, "summary": summary, "policies": results}
    temporary_path = output_dir / "run_manifest.json.tmp"
    temporary_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary_path.replace(output_dir / "run_manifest.json")
    (output_dir / "all_results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")


def load_existing_results(output_dir: Path) -> dict[str, dict[str, Any]]:
    results_path = output_dir / "all_results.json"
    if not results_path.is_file():
        return {}
    loaded = json.loads(results_path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ExperimentError(f"Expected an object in {results_path}")
    return loaded


def validate_resume_config(output_dir: Path, current_config: dict[str, Any]) -> None:
    """Prevent a resumed run from mixing incompatible experiment protocols."""
    manifest_path = output_dir / "run_manifest.json"
    if not manifest_path.is_file():
        raise ExperimentError(
            f"Cannot safely resume {output_dir}: run_manifest.json is missing. "
            "Choose a fresh output directory."
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    previous_config = manifest.get("run_config")
    if not isinstance(previous_config, dict):
        raise ExperimentError(
            f"Cannot safely resume {output_dir}: run_manifest.json has no run_config object"
        )

    comparable_keys = (
        "protocol_version",
        "max_models",
        "model",
        "num_candidates",
        "syntax_repairs",
        "bound",
        "timeout",
        "z3_seed",
        "enumerate_only",
    )
    mismatches = [
        f"{key}: previous={previous_config.get(key)!r}, current={current_config.get(key)!r}"
        for key in comparable_keys
        if previous_config.get(key) != current_config.get(key)
    ]
    if mismatches:
        raise ExperimentError(
            "Resume configuration does not match the existing run:\n  "
            + "\n  ".join(mismatches)
            + "\nChoose a fresh output directory for a different protocol."
        )


def prepare_quacky_runtime(quacky_path: Path, output_dir: Path) -> Path:
    """Copy Quacky to a writable directory for its legacy temporary files."""
    runtime_dir = output_dir / "_quacky_runtime"
    runtime_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(quacky_path.parent, runtime_dir, dirs_exist_ok=True)
    runtime_quacky = runtime_dir / quacky_path.name
    if not runtime_quacky.is_file():
        raise ExperimentError(f"Quacky runtime copy is missing {runtime_quacky}")
    return runtime_quacky


def build_client() -> anthropic.Anthropic:
    load_dotenv(REPO_ROOT / ".env")
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ExperimentError("ANTHROPIC_API_KEY is required unless --enumerate-only is used")
    return anthropic.Anthropic(api_key=api_key)


def numeric_policy_files(dataset_dir: Path, start_from: int, end_at: int | None) -> list[Path]:
    policies = [path for path in dataset_dir.glob("*.json") if path.stem.isdigit()]
    policies.sort(key=lambda path: int(path.stem))
    return [
        path
        for path in policies
        if int(path.stem) >= start_from and (end_at is None or int(path.stem) <= end_at)
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-dir", type=Path, default=DEFAULT_DATASET_DIR)
    parser.add_argument("--quacky-path", type=Path, default=DEFAULT_QUACKY_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--max-models", type=int, default=1000)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--num-candidates", type=int, default=5)
    parser.add_argument("--syntax-repairs", type=int, default=1)
    parser.add_argument("--bound", type=int, default=100)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--z3-seed", type=int, default=0)
    parser.add_argument("--start-from", type=int, default=0)
    parser.add_argument("--end-at", type=int)
    parser.add_argument("--enumerate-only", action="store_true")
    parser.add_argument("--resume", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.max_models <= 0 or args.num_candidates <= 0 or args.syntax_repairs < 0:
        raise ExperimentError("Model, candidate, and repair counts must be positive (repairs may be zero)")
    if not args.dataset_dir.is_dir():
        raise ExperimentError(f"Dataset directory not found: {args.dataset_dir}")
    if not args.quacky_path.is_file():
        raise ExperimentError(f"Quacky entry point not found: {args.quacky_path}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    existing_results = load_existing_results(args.output_dir)
    if existing_results and not args.resume:
        raise ExperimentError(
            f"{args.output_dir}/all_results.json already exists; use --resume or choose a fresh output directory"
        )

    if not args.enumerate_only and shutil.which("abc") is None:
        raise ExperimentError(
            "ABC solver executable not found on PATH. Install ABC as documented in README.md "
            "and verify that `abc --help` runs before starting the full experiment."
        )
    source_quacky_path = args.quacky_path.resolve()
    runtime_quacky_path = (
        args.quacky_path
        if args.enumerate_only
        else prepare_quacky_runtime(args.quacky_path, args.output_dir)
    )
    client = None if args.enumerate_only else build_client()
    run_config = {
        "protocol_version": PROTOCOL_VERSION,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_dir": str(args.dataset_dir.resolve()),
        "quacky_source_path": str(source_quacky_path),
        "quacky_runtime_path": str(runtime_quacky_path.resolve()),
        "output_dir": str(args.output_dir.resolve()),
        "max_models": args.max_models,
        "model": None if args.enumerate_only else args.model,
        "num_candidates": 0 if args.enumerate_only else args.num_candidates,
        "syntax_repairs": 0 if args.enumerate_only else args.syntax_repairs,
        "bound": args.bound,
        "timeout": args.timeout,
        "z3_seed": args.z3_seed,
        "enumerate_only": args.enumerate_only,
    }
    if args.resume and existing_results:
        validate_resume_config(args.output_dir, run_config)
    policies = numeric_policy_files(args.dataset_dir, args.start_from, args.end_at)
    if not policies:
        raise ExperimentError("No numeric policy JSON files matched the requested range")

    results = existing_results
    for policy_path in tqdm(policies, desc="Z3 baseline policies"):
        previous = results.get(policy_path.stem)
        if args.resume and previous and previous.get("success"):
            continue
        result = process_policy(
            policy_path,
            output_dir=args.output_dir,
            quacky_path=runtime_quacky_path,
            client=client,
            max_models=args.max_models,
            model=args.model,
            num_candidates=args.num_candidates,
            syntax_repairs=args.syntax_repairs,
            bound=args.bound,
            timeout=args.timeout,
            seed=args.z3_seed,
            enumerate_only=args.enumerate_only,
        )
        results[policy_path.stem] = result
        write_results(args.output_dir, results, run_config)
        status = "PASS" if result["success"] else "FAIL"
        tqdm.write(f"policy {policy_path.stem}: {status} ({result['status']})")

    summary = summarize_results(results)
    print(json.dumps(summary, indent=2))
    return 0 if summary["policies_successful"] == len(policies) else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ExperimentError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)
