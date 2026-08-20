#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE_NAME="${POLICY_SUMMARIZER_IMAGE:-policysummarizer}"
EXPERIMENT_IMAGE_NAME="${POLICY_SUMMARIZER_EXPERIMENT_IMAGE:-policysummarizer-experiments}"
OUTPUT_DIR="${POLICY_SUMMARIZER_OUTPUT_DIR:-${ROOT_DIR}/run_outputs}"

usage() {
  cat <<'EOF'
PolicySummarizer validation console

Usage: bash validation/check.sh [command] [options]

Commands:
  all            Run the Docker smoke test, retained-result audit, and release check
  smoke          Build the image and analyze a bundled AWS IAM policy
  audit          Recompute statistics from retained results
  sample-check   Generate 100 accepted resource strings for one policy
  web            Launch the local web interface
  sample-sweep   Run the LLM-backed sample-size experiment
  z3-baseline    Run the Z3 + LLM baseline experiment
  experiment-image  Build the Docker environment for experiment scripts
  experiment-shell  Open a shell in the experiment Docker environment
  release-check  Check required files, metadata, and accidental credentials
  shell          Open a shell in the PolicySummarizer image
  help           Show this message

Run without a command for an interactive menu.
EOF
}

require_docker() {
  if ! command -v docker >/dev/null 2>&1; then
    echo "ERROR: Docker is required. Install Docker Desktop or Docker Engine." >&2
    exit 1
  fi
}

build_image() {
  require_docker
  if ! docker image inspect "${IMAGE_NAME}" >/dev/null 2>&1; then
    echo "Building ${IMAGE_NAME}. The first build may take 5-15 minutes."
    docker build --tag "${IMAGE_NAME}" "${ROOT_DIR}/policysummarizer"
  fi
}

run_in_image() {
  build_image
  mkdir -p "${OUTPUT_DIR}"
  docker run --rm \
    --user "$(id -u):$(id -g)" \
    --env HOME=/tmp \
    --env PYTHONDONTWRITEBYTECODE=1 \
    --volume "${ROOT_DIR}:/workspace:ro" \
    --volume "${OUTPUT_DIR}:/results" \
    --workdir /workspace \
    "${IMAGE_NAME}" "$@"
}

run_audit() {
  run_in_image python validation/verify_retained_results.py
}

run_release_check() {
  run_in_image python validation/check_release_readiness.py
}

run_all() {
  bash "${ROOT_DIR}/validation/smoke_test.sh"
  run_audit
  run_release_check
  echo
  echo "POLICYSUMMARIZER VALIDATION: PASS"
}

run_sample_check() {
  POLICY_SUMMARIZER_REPLICATION_DIR="${OUTPUT_DIR}/sample-check" \
    bash "${ROOT_DIR}/experiments/sample_size/run_protocol.sh" \
      --enumerate-only --sample-sizes 100 --start-from 0 --end-at 0 "$@"
}

run_web() {
  build_image
  echo "Open http://localhost:8000 after the server starts. Press Ctrl-C to stop."
  if [[ -n "${ANTHROPIC_API_KEY:-}" ]]; then
    echo "Anthropic-backed simplification is enabled."
  else
    echo "No API key is set. Formal analysis remains available; LLM simplification is disabled."
  fi
  docker run --rm -it \
    --publish 8000:8000 \
    --env ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-}" \
    "${IMAGE_NAME}"
}

run_sample_sweep() {
  POLICY_SUMMARIZER_REPLICATION_DIR="${OUTPUT_DIR}/sample-sweep" \
    bash "${ROOT_DIR}/experiments/sample_size/run_protocol.sh" "$@"
}

run_z3_baseline() {
  POLICY_SUMMARIZER_Z3_DIR="${OUTPUT_DIR}/z3-baseline" \
    bash "${ROOT_DIR}/experiments/z3_baseline/run.sh" "$@"
}

build_experiment_image() {
  build_image
  docker build \
    --tag "${EXPERIMENT_IMAGE_NAME}" \
    --build-arg "POLICY_SUMMARIZER_IMAGE=${IMAGE_NAME}" \
    --file "${ROOT_DIR}/experiments/Dockerfile" \
    "${ROOT_DIR}"
}

run_experiment_shell() {
  build_experiment_image
  mkdir -p "${OUTPUT_DIR}"
  docker run --rm -it \
    --user "$(id -u):$(id -g)" \
    --env HOME=/tmp \
    --volume "${ROOT_DIR}:/workspace" \
    --volume "${OUTPUT_DIR}:/results" \
    --workdir /workspace \
    "${EXPERIMENT_IMAGE_NAME}"
}

run_shell() {
  build_image
  mkdir -p "${OUTPUT_DIR}"
  docker run --rm -it \
    --user "$(id -u):$(id -g)" \
    --env HOME=/tmp \
    --volume "${ROOT_DIR}:/workspace:ro" \
    --volume "${OUTPUT_DIR}:/results" \
    --workdir /workspace \
    --entrypoint sh \
    "${IMAGE_NAME}"
}

dispatch() {
  local command="${1:-help}"
  if [[ $# -gt 0 ]]; then shift; fi
  case "${command}" in
    all) run_all "$@" ;;
    smoke) bash "${ROOT_DIR}/validation/smoke_test.sh" "$@" ;;
    audit) run_audit "$@" ;;
    sample-check) run_sample_check "$@" ;;
    web) run_web "$@" ;;
    sample-sweep) run_sample_sweep "$@" ;;
    z3-baseline) run_z3_baseline "$@" ;;
    experiment-image) build_experiment_image "$@" ;;
    experiment-shell) run_experiment_shell "$@" ;;
    release-check) run_release_check "$@" ;;
    shell) run_shell "$@" ;;
    help|-h|--help) usage ;;
    *) echo "Unknown command: ${command}" >&2; usage >&2; return 2 ;;
  esac
}

interactive_menu() {
  while true; do
    cat <<'EOF'

PolicySummarizer
1. Run all validation checks
2. Run the Docker smoke test
3. Audit retained experiment results
4. Generate samples without an API
5. Launch the web interface
6. Run the sample-size experiment
7. Run the Z3 baseline experiment
8. Check release metadata and credentials
9. Open a container shell
10. Build the experiment Docker image
11. Open an experiment container shell
0. Exit
EOF
    read -r -p "Choose an option: " choice
    case "${choice}" in
      1) dispatch all ;;
      2) dispatch smoke ;;
      3) dispatch audit ;;
      4) dispatch sample-check ;;
      5) dispatch web ;;
      6) dispatch sample-sweep ;;
      7) dispatch z3-baseline ;;
      8) dispatch release-check ;;
      9) dispatch shell ;;
      10) dispatch experiment-image ;;
      11) dispatch experiment-shell ;;
      0) return 0 ;;
      *) echo "Please choose a number from 0 to 11." ;;
    esac
  done
}

if [[ $# -eq 0 ]]; then
  interactive_menu
else
  dispatch "$@"
fi
