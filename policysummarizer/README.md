# PolicySummarizer System

PolicySummarizer characterizes the effective resource scope of cloud
access-control policies. It combines policy translation, SMT solving, model
counting, automata-derived regular expressions, and optional LLM-based
simplification.

## How It Works

1. **Parse the policy.** The Quacky frontend reads AWS IAM policies, Azure role
   definitions and assignments, or GCP roles and bindings.
2. **Build a logical model.** The backend translates the policy into SMT-LIB
   constraints over principal, action, resource, and supported conditions.
3. **Analyze the accepted requests.** ABC checks satisfiability, counts accepted
   requests within the selected bound, and constructs the resource automaton.
4. **Extract the formal characterization.** The automaton is converted into a
   regular expression describing the accepted resource language under the
   configured analysis bounds.
5. **Optionally simplify it.** An LLM proposes a shorter equivalent expression.
6. **Check the proposal.** ABC compares the candidate expression with the
   automata-derived expression and reports both directional differences and
   Jaccard coverage. Batch runs can return that signal to the model for another
   attempt.

The LLM never establishes equivalence. It proposes a representation; the
formal comparison measures whether that representation preserves the accepted
resource language.

## API-Free Capabilities

The following operations use Quacky and ABC and do not call an LLM:

- check whether a policy permits any requests;
- count permitted requests within a finite string/integer bound;
- compare two policies in both directions;
- identify whether one policy is more permissive, less permissive, equivalent,
  or incomparable to another;
- emit accepted resource strings;
- extract the DFA-derived resource regular expression for the configured
  bounded model;
- compare any supplied regular expression with the formal expression;
- compute directional difference counts and Jaccard coverage.

Build the image from the repository root:

```bash
docker build -t policysummarizer ./policysummarizer
```

Analyze a bundled policy and print its DFA-derived expression:

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

Generate 100 accepted resource strings:

```bash
docker run --rm \
  --workdir /app/quacky \
  --entrypoint python \
  policysummarizer \
  quacky.py \
  -p1 ../samples/iam/exp_single/iam_simplest_policy/policy.json \
  -b 100 -m 100 -m1 10 -m2 150
```

Compare a candidate regex by mounting a local file:

```bash
docker run --rm \
  -v "$PWD/candidate.regex:/data/candidate.regex:ro" \
  --workdir /app/quacky \
  --entrypoint python \
  policysummarizer \
  quacky.py \
  -p1 ../samples/iam/exp_single/iam_simplest_policy/policy.json \
  -b 100 -pr -cr /data/candidate.regex
```

## LLM-Backed Simplification

The current provider implementation uses the Anthropic API. Set the key only
at runtime:

```bash
export ANTHROPIC_API_KEY="your-key"
docker run --rm \
  -e ANTHROPIC_API_KEY \
  -p 8000:8000 \
  policysummarizer
```

Then open `http://localhost:8000` and submit a policy. The interface streams
the formal expression first, followed by the optional simplification and its
formal comparison.

The batch pipeline is implemented in
[`regex_summarizer_regex_based.py`](regex_summarizer_regex_based.py). It
supports AWS, Azure, and GCP inputs and can retry a failed simplification with
the measured over- or under-coverage signal.

Local-model support is planned through a provider-neutral, OpenAI-compatible
adapter. It is not included in this release. The formal pipeline is already
provider-independent and remains available without any model.

## Local Installation

Docker is the shortest path because it builds the pinned ABC, MONA, and Python
dependencies. For a native installation:

1. Install ABC and MONA using the revisions in [`Dockerfile`](Dockerfile).
2. Create a Python 3.12 environment.
3. Install `requirements.lock.txt`.
4. Run commands from `policysummarizer/quacky/` so legacy temporary paths are
   resolved correctly.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r policysummarizer/requirements.lock.txt
cd policysummarizer/quacky
python quacky.py -h
```

## Source Layout

| Path | Purpose |
| --- | --- |
| `quacky/` | Policy parsing, SMT translation, ABC integration, model counting, policy comparison, and regex extraction |
| `web/` | FastAPI service and static interface with streamed progress |
| `samples/` | Bundled AWS, Azure, and GCP examples |
| `regex_summarizer_regex_based.py` | Multi-cloud formal-expression simplification and repair loop |
| `regex_summarizer.py` | Sample-based regex synthesis pipeline |
| `mutation_comparator.py` | Directional comparison of original and mutated policies |
| `Dockerfile` | Pinned, multi-stage build for ABC, MONA, Quacky, and the web service |
| `docs/` | Quacky usage, tutorial, and background material |

The MIT license for PolicySummarizer is at the repository root. Quacky's
original license is retained in `quacky/LICENSE`.
