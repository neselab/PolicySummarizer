# Release Checklist

Use this checklist when creating a versioned PolicySummarizer archive.

1. Run `bash validation/check.sh all` from a clean checkout.
2. Run `python3 validation/check_release_readiness.py`.
3. Confirm that `README.md`, `README.txt`, `CITATION.cff`, and `LICENSE` contain
   the intended release metadata.
4. Commit the release tree and create a version tag.
5. Run `bash validation/build_release_archive.sh <version>`.
6. Verify the generated ZIP and checksum.
7. Upload the ZIP to the archival record.
8. Add the archival DOI to `README.txt` and `CITATION.cff`.
9. Run `python3 validation/check_release_readiness.py --require-doi`.

ISSRE 2026 artifact instructions:
https://cyprusconferences.org/issre2026/cfp-artifacts/
