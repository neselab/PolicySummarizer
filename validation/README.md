# Validation And Release Tools

This directory contains technical checks for the repository and release
archive.

```bash
bash validation/check.sh
```

The console exposes:

- a Docker build and policy-analysis smoke test;
- recomputation of aggregate measurements from retained results;
- an API-free sample-generation check;
- the local web interface;
- the sample-size and Z3 experiment runners;
- the Docker environment for the broader experiment scripts;
- metadata and credential scanning;
- release archive generation.

Run all local checks non-interactively:

```bash
bash validation/check.sh all
```

Build or enter the experiment environment separately:

```bash
bash validation/check.sh experiment-image
bash validation/check.sh experiment-shell
```

`RESULTS_CROSSWALK.md` maps reported measurements to retained files and
recomputation code. `RELEASE_CHECKLIST.md` records the final archive steps.
