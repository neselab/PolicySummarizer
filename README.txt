1. TARGET CATEGORY
==================

Code and Dataset


2. TARGET BADGE
===============

Reviewed and Available


3. INFO
=======

Paper:
Neurosymbolic Characterization for Reliable Access Control Policy Analysis

Authors:
- Adarsh Vatsa, Stevens Institute of Technology, avatsa@stevens.edu
- Bethel Hall, Stevens Institute of Technology
- William Eiers, Stevens Institute of Technology, weiers@stevens.edu

Source repository:
https://github.com/neselab/PolicySummarizer

Live interface:
https://policysummarizer.xyz/

Artifact DOI:
https://doi.org/10.5281/zenodo.22022124


4. EXPECTED BEHAVIOUR
=====================

PolicySummarizer translates cloud access-control policies into logical
constraints and uses Quacky with ABC to characterize the accepted request
space. The formal pipeline reports satisfiability, bounded request counts,
policy differences, accepted resource strings, and an automata-derived resource
regular expression. The optional LLM stage proposes a shorter expression, which
is compared with the formal expression before it is recorded.

The main validation command builds the Docker image, analyzes a bundled AWS IAM
policy, and recomputes statistics from the retained result files. A successful
run ends with:

POLICYSUMMARIZER VALIDATION: PASS


5. ARTIFACT DESCRIPTION
=======================

- policysummarizer/
  Runnable system: Dockerfile, Quacky source, ABC integration, batch pipelines,
  web interface, bundled examples, and technical documentation.
- experiments/
  Experiment drivers, protocols, retained outputs, and experiment-specific
  documentation.
- Dataset/
  Original and mutated AWS policies, PolicySummarizer multi-cloud inputs, and
  the Experiment 4 Z3 baseline outputs and user-study archive.
- validation/
  Docker smoke test, retained-result recomputation, source/metadata checks,
  result crosswalk, and release archive tooling.
- CITATION.cff
  Software and paper citation metadata.

The repository is licensed under MIT. The bundled Quacky source retains its
original license in policysummarizer/quacky/LICENSE.


6. ENVIRONMENT SETUP
====================

Recommended host environment:
- Linux, macOS, or Windows
- Docker Engine or Docker Desktop 24 or newer
- 4 CPU cores
- 8 GB RAM
- 15 GB free disk space
- Internet access for the first image build

Clone the repository:

  git clone https://github.com/neselab/PolicySummarizer.git
  cd PolicySummarizer

Docker builds pinned ABC, MONA, and Python dependencies. No host Python, ABC,
MONA, or API key is needed for formal analysis and retained-result validation.

Fresh LLM-backed runs require network access, an Anthropic account,
ANTHROPIC_API_KEY, available model access, and sufficient API credit and
rate-limit quota.


7. GETTING STARTED
==================

Run all local checks:

  bash validation/check.sh all

The first Docker build normally takes 5-15 minutes. The command performs:
1. A Docker build from policysummarizer/Dockerfile.
2. Formal analysis of a bundled satisfiable AWS IAM policy.
3. Recalculation of aggregate statistics from retained experiment records.
4. A scan for required files, incomplete metadata, and accidental credentials.

Open the interactive console with:

  bash validation/check.sh

Launch the web interface with:

  bash validation/check.sh web

Then open http://localhost:8000.

Build the broader experiment environment with:

  bash validation/check.sh experiment-image

Open a shell in that environment with:

  bash validation/check.sh experiment-shell


8. REPRODUCIBILITY NOTES
========================

Recompute retained measurements:

  bash validation/check.sh audit

Generate accepted resource samples for one policy without an API key:

  bash validation/check.sh sample-check

Inspect the full sample-size workload without making model calls:

  bash validation/check.sh sample-sweep --dry-run

Run a fresh LLM-backed sample-size experiment:

  export ANTHROPIC_API_KEY="your-key"
  bash validation/check.sh sample-sweep \
    --model "your-available-model-id" --resume

Run the Z3 + LLM baseline:

  export ANTHROPIC_API_KEY="your-key"
  bash validation/check.sh z3-baseline \
    --model "your-available-model-id" --resume

Fresh LLM runs store model identifiers, candidates, parser diagnostics, token
usage, elapsed time, and aggregate scores under run_outputs/. Model responses
are stochastic and depend on the model version available to the account.

The mapping from reported measurements to retained files and recomputation code
is in validation/RESULTS_CROSSWALK.md.
