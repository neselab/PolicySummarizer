# PolicySummarizer

PolicySummarizer produces compact, formally checked characterizations of cloud
access-control policies. It translates AWS IAM, Azure RBAC, and GCP IAM policy
artifacts into logical constraints, derives the accepted request language, and
uses automata-based analysis to expose the policy's effective resource scope.
An optional language-model stage rewrites the automata-derived expression into
a shorter form, which is checked against the original bounded language before
it is accepted.

The repository accompanies the paper **Neurosymbolic Characterization for
Reliable Access Control Policy Analysis**.

## System Pipeline

```text
Cloud policy
    -> policy parser and SMT translation
    -> ABC satisfiability and model counting
    -> DFA/RDFA resource characterization
    -> automata-derived regular expression for the bounded model
    -> optional LLM simplification
    -> ABC equivalence/coverage check
    -> accepted summary or another repair attempt
```

The formal stages do not require an LLM. They can determine satisfiability,
count permitted requests within a bound, compare two policies, generate
accepted resource strings, and extract the exact DFA-derived regular
expression for the configured bounded model. The LLM is used only to make that
expression shorter and easier to read; its output is measured against the
formal characterization.

## Repository Map

| Path | Contents |
| --- | --- |
| [`policysummarizer/`](policysummarizer/) | Runnable system, Quacky/ABC integration, web interface, Docker image, samples, and technical documentation |
| [`experiments/`](experiments/) | Experiment drivers, protocols, retained outputs, and per-experiment documentation |
| [`Dataset/`](Dataset/) | AWS policy corpus, mutations, multi-cloud inputs, and user-study materials |
| [`validation/`](validation/) | Docker smoke test, retained-result recomputation, metadata checks, and archive tooling |
| [`README.txt`](README.txt) | ISSRE artifact metadata and the compact execution procedure |

## Quick Start

Build the self-contained image:

```bash
docker build -t policysummarizer ./policysummarizer
```

Run formal analysis on a bundled AWS IAM policy without an API key:

```bash
docker run --rm \
  --workdir /app/quacky \
  --entrypoint python \
  policysummarizer \
  quacky.py \
  -p1 ../samples/iam/exp_single/iam_simplest_policy/policy.json \
  -b 100 \
  -pr
```

The command reports satisfiability, the bounded request count, and the
DFA-derived resource expression.

Launch the web interface:

```bash
docker run --rm -p 8000:8000 policysummarizer
```

Open `http://localhost:8000`. Formal analysis works without an API key. To
enable LLM simplification, pass an Anthropic key at runtime:

```bash
docker run --rm \
  -e ANTHROPIC_API_KEY="your-key" \
  -p 8000:8000 \
  policysummarizer
```

See [`policysummarizer/README.md`](policysummarizer/README.md) for the system
architecture, API-free capabilities, LLM-backed workflow, and local setup.

## Experiments And Validation

[`experiments/README.md`](experiments/README.md) explains the purpose, inputs,
outputs, and API requirements of each experiment.

The system and experiments use separate Docker images. The system image stays
focused on PolicySummarizer. The experiment image adds the analysis, plotting,
and multi-provider packages used by the study scripts:

```bash
docker build -t policysummarizer ./policysummarizer
docker build -t policysummarizer-experiments -f experiments/Dockerfile .
```

Run the complete local validation path:

```bash
bash validation/check.sh all
```

Or open the interactive console:

```bash
bash validation/check.sh
```

The validation path builds the Docker image, analyzes a bundled policy, and
recomputes aggregate statistics from the retained result files.

## Execution Modes

| Mode | API key | Output |
| --- | --- | --- |
| Formal analysis | No | Satisfiability, request counts, policy differences, DFA/RDFA expression, and accepted samples |
| Candidate-regex comparison | No | Directional set differences and Jaccard coverage against the formal expression |
| LLM simplification | Yes | Shorter candidate expression followed by formal comparison and repair feedback |
| Retained-result audit | No | Recomputed aggregate measurements from saved experiment records |
| Fresh LLM experiments | Yes | New stochastic runs with model, token, timing, and candidate traces |

## License And Citation

The repository is released under the [MIT License](LICENSE). The bundled
Quacky source retains its original license in
[`policysummarizer/quacky/LICENSE`](policysummarizer/quacky/LICENSE).
Citation metadata is provided in [`CITATION.cff`](CITATION.cff).
