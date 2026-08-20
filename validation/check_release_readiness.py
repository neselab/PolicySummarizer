#!/usr/bin/env python3
"""Check repository metadata and hygiene before creating a release archive."""

from __future__ import annotations

import argparse
import re
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_FILES = (
    "README.txt",
    "README.md",
    "LICENSE",
    "CITATION.cff",
    "policysummarizer/Dockerfile",
    "policysummarizer/README.md",
    "experiments/README.md",
    "validation/check.sh",
    "validation/smoke_test.sh",
    "validation/verify_retained_results.py",
    "experiments/sample_size/run_protocol.sh",
    "experiments/sample_size/run_protocol.py",
)
REQUIRED_HEADINGS = tuple(f"{number}. " for number in range(1, 9))
SECRET_PATTERNS = {
    "Anthropic API key": re.compile(rb"sk-ant-[A-Za-z0-9_-]{20,}"),
    "OpenAI API key": re.compile(rb"sk-(?:proj-)?[A-Za-z0-9_-]{20,}"),
    "JSONBin key": re.compile(rb"\$2[aby]\$\d{2}\$[./A-Za-z0-9]{40,}"),
    "GitHub token": re.compile(rb"gh[pousr]_[A-Za-z0-9]{20,}"),
}
TEXT_SUFFIXES = {
    ".cff",
    ".csv",
    ".env",
    ".html",
    ".json",
    ".md",
    ".py",
    ".sh",
    ".tex",
    ".txt",
    ".yaml",
    ".yml",
}


def scan_bytes(label: str, data: bytes, failures: list[str]) -> None:
    for secret_name, pattern in SECRET_PATTERNS.items():
        if pattern.search(data):
            failures.append(f"possible {secret_name} in {label}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--require-doi",
        action="store_true",
        help="fail unless README.txt and CITATION.cff contain a DOI",
    )
    args = parser.parse_args()

    failures: list[str] = []
    warnings: list[str] = []
    for relative in REQUIRED_FILES:
        if not (ROOT / relative).is_file():
            failures.append(f"missing required file: {relative}")

    readme_path = ROOT / "README.txt"
    readme = readme_path.read_text(encoding="utf-8") if readme_path.is_file() else ""
    for heading in REQUIRED_HEADINGS:
        if not any(line.startswith(heading) for line in readme.splitlines()):
            failures.append(f"README.txt is missing section {heading.strip()}")
    if "[INSERT" in readme or "TODO" in readme:
        failures.append("README.txt contains unfinished placeholder text")

    citation = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
    has_doi = bool(re.search(r"\b10\.\d{4,9}/[-._;()/:A-Za-z0-9]+", readme + citation))
    if args.require_doi and not has_doi:
        failures.append("final release metadata does not contain a DOI")
    elif not has_doi:
        warnings.append("release DOI has not been minted yet")

    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts:
            continue
        relative = path.relative_to(ROOT)
        if path.name.startswith(".env") and path.name != ".env.example":
            failures.append(f"environment file must not be archived: {relative}")
        if path.suffix.lower() in TEXT_SUFFIXES:
            scan_bytes(str(relative), path.read_bytes(), failures)
        elif path.suffix.lower() == ".zip":
            try:
                with zipfile.ZipFile(path) as archive:
                    for member in archive.infolist():
                        if member.is_dir():
                            continue
                        if Path(member.filename).suffix.lower() in TEXT_SUFFIXES:
                            scan_bytes(
                                f"{relative}:{member.filename}",
                                archive.read(member),
                                failures,
                            )
            except zipfile.BadZipFile:
                failures.append(f"invalid zip archive: {relative}")

    for warning in warnings:
        print(f"WARNING: {warning}")
    if failures:
        for failure in sorted(set(failures)):
            print(f"FAIL: {failure}")
        return 1
    print("RELEASE CHECK: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
