#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE_NAME="${POLICY_SUMMARIZER_IMAGE:-policysummarizer-ae}"

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: Docker is required for this smoke test." >&2
  exit 1
fi

echo "[1/2] Building ${IMAGE_NAME} from policysummarizer/Dockerfile"
docker build --tag "${IMAGE_NAME}" "${ROOT_DIR}/policysummarizer"

echo "[2/2] Running Quacky on the bundled satisfiable IAM policy"
output="$({
  docker run --rm \
    --env PYTHONWARNINGS=ignore::SyntaxWarning \
    --workdir /app/quacky \
    --entrypoint python \
    "${IMAGE_NAME}" \
    quacky.py \
    -p1 ../samples/iam/exp_single/iam_simplest_policy/policy.json \
    -b 100
} 2>&1)"
printf '%s\n' "${output}"

grep -Fq "Policy 1" <<<"${output}"
grep -Fqi "satisfiability: sat" <<<"${output}"
grep -Fq "lg(requests):" <<<"${output}"

echo
echo "POLICYSUMMARIZER SMOKE TEST: PASS"
