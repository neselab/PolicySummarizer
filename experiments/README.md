# Experiments

This directory contains the experiment code and retained outputs for
PolicySummarizer and the accompanying policy-comprehension studies. Each
experiment has a distinct research question and execution path.

## Experiment Map

| Directory | Purpose | Main entry point | Model access |
| --- | --- | --- | --- |
| `policy_summarizer/` | Retained AWS, Azure, GCP, and mutation results produced by the PolicySummarizer pipelines | Product runners in `../policysummarizer/` | Retained data: none; fresh simplification: Anthropic |
| `policy_comprehension/` | Tests whether LLM explanations preserve enough policy behavior to reconstruct the original policy | `cpca.py` | Required for fresh model responses |
| `policy_generation/` | Generates a policy from a description and measures both directional differences from the source policy | `Exp-1.py` | xAI API |
| `resource_summarization/` | Generates a regex from accepted resource samples and compares it with the policy language | `Exp-2.py` | OpenAI API |
| `sample_size/` | Measures regex quality as the number of accepted resource samples changes | `run_protocol.py` | None for enumeration; Anthropic for simplification |
| `z3_baseline/` | Enumerates satisfying resource strings with Z3, asks for multiple regex candidates, and keeps the highest-scoring candidate | `z3_model_enum.py` | None for enumeration; Anthropic for candidate generation |
| `regex_simplification/` | Studies direct simplification of automata-derived regular expressions | `simplify.py` | Anthropic |
| `fine_tuning/` | Historical scripts and records for preparing and evaluating fine-tuning datasets | scripts within the directory | Provider access depends on the script |

The documented entry points are the maintained execution paths. Files labeled
as original implementations preserve the code, model identifiers, prompts, and
outputs used during earlier experiment runs.

Where two pre-restructure copies differed, the alternate version is retained
under that experiment's `legacy/root_snapshot/` directory.

## Experiment Environment

Build the system image first, then the experiment image:

```bash
docker build -t policysummarizer ./policysummarizer
docker build -t policysummarizer-experiments -f experiments/Dockerfile .
```

Open an experiment shell with the repository mounted at `/workspace`:

```bash
docker run --rm -it \
  -v "$PWD:/workspace" \
  -w /workspace \
  policysummarizer-experiments
```

Pass only the provider keys needed by the selected experiment, for example:

```bash
docker run --rm -it \
  -e ANTHROPIC_API_KEY \
  -v "$PWD:/workspace" \
  -w /workspace \
  policysummarizer-experiments
```

## PolicySummarizer Evaluation

The primary PolicySummarizer results are stored in:

```text
experiments/policy_summarizer/
├── results_aws/       # AWS direct and sample-based results
├── regex_results/     # Azure and GCP direct simplification results
├── string_results/    # Azure and GCP sample-based results
├── results_mutation/  # Directional mutation comparisons
└── results_report.ipynb
```

Recompute the aggregate measurements from the retained JSON files:

```bash
bash validation/check.sh audit
```

## Sample-Size Protocol

The current runner evaluates 100, 500, 1,000, 1,500, and 2,000 accepted
resource strings per policy. It stores the sample set, every candidate regex,
syntax diagnostics, model metadata, token counts, elapsed time, and the final
coverage score.

Inspect the planned workload without making model calls:

```bash
bash experiments/sample_size/run_protocol.sh --dry-run
```

Exercise sample generation for one policy without an API key:

```bash
bash experiments/sample_size/run_protocol.sh \
  --enumerate-only --sample-sizes 100 --start-from 0 --end-at 0
```

Run a fresh LLM-backed sweep:

```bash
export ANTHROPIC_API_KEY="your-key"
bash experiments/sample_size/run_protocol.sh \
  --model "your-available-model-id" --resume
```

## Z3 Baseline

Exercise model enumeration without an API call:

```bash
bash experiments/z3_baseline/run.sh \
  --enumerate-only --start-from 0 --end-at 0
```

Run the best-of-five LLM baseline:

```bash
export ANTHROPIC_API_KEY="your-key"
bash experiments/z3_baseline/run.sh \
  --max-models 1000 --num-candidates 5 --syntax-repairs 1 --resume
```

## Data And Outputs

The shared input corpus is in [`../Dataset/`](../Dataset/). Fresh protocol
runs write to `run_outputs/` by default. Original experiment implementations
retain their output files inside their experiment directory so the code and
recorded tables remain adjacent.

LLM-backed runs require network access, a provider key, model access, and paid
credit. API-free enumeration, formal policy analysis, retained-result audits,
and Docker smoke tests do not make model calls.
