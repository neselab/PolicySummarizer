#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="${1:-1.0.0}"
ARCHIVE_NAME="policysummarizer-v${VERSION}.zip"
ARCHIVE_PATH="${ROOT_DIR}/${ARCHIVE_NAME}"

cd "${ROOT_DIR}"

if [[ -n "$(git status --porcelain)" ]]; then
  echo "ERROR: Commit repository changes before building the archive." >&2
  exit 1
fi

python3 validation/check_release_readiness.py --require-doi
python3 validation/verify_retained_results.py

git archive \
  --format=zip \
  --prefix="policysummarizer-v${VERSION}/" \
  --output="${ARCHIVE_PATH}" \
  HEAD

if command -v sha256sum >/dev/null 2>&1; then
  sha256sum "${ARCHIVE_PATH}" > "${ARCHIVE_PATH}.sha256"
else
  shasum -a 256 "${ARCHIVE_PATH}" > "${ARCHIVE_PATH}.sha256"
fi

echo "Created ${ARCHIVE_PATH}"
echo "Checksum: ${ARCHIVE_PATH}.sha256"
