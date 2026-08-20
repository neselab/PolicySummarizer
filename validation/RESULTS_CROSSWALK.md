# Results and Evidence Map

This document maps reported quantitative results to the retained records and
the scripts that recompute them.

Run the API-free audit from the repository root:

```bash
python3 validation/verify_retained_results.py
```

## Policy Summarization

| Result | Retained evidence | Verification |
| --- | --- | --- |
| 587 AWS, 100 Azure, and 100 GCP policy records | `experiments/policy_summarizer/results_aws/`, `experiments/policy_summarizer/regex_results/`, and `experiments/policy_summarizer/string_results/` | Recomputed from JSON records |
| 41 unsatisfiable AWS policies and 546 scored policies | AWS result records | Recomputed from satisfiability and Jaccard fields |
| Direct exact-match rates of 91.0% AWS, 99.0% Azure, and 94.9% GCP | 497/546, 98/99, and 94/99 exact Jaccard matches | Recomputed from JSON records |
| Sample-based exact-match rates of 71.8% AWS, 93.0% Azure, and 92.0% GCP | 392/546, 93/100, and 92/100 exact Jaccard matches | Recomputed from JSON records |
| Mutation outcomes: 302 more permissive, 48 less permissive, 44 incomparable, 126 equal, and 26 timeouts | `experiments/policy_summarizer/results_mutation/mutation_results.json` | Recomputed from verdict fields |
| Directional Jaccard means of 0.967 and 0.894, both with median 1.0 | Mutation result records | Recomputed from directional score fields |
| Sample-size sweep at 100, 500, 1,000, 1,500, and 2,000 samples | `experiments/sample_size/` | Protocol runner records inputs, generated samples, candidates, repairs, timings, and token usage |
| Z3 enumeration baseline | `experiments/z3_baseline/` | Best-of-five enumeration protocol with retained model and score traces |

The retained policy records distinguish exact-match rate from arithmetic mean
Jaccard similarity. `validation/verify_retained_results.py` prints both.

## Policy Comprehension

`experiments/policy_comprehension/cpca.py` contains the prompts and execution
workflow. Reconstructed policies, raw responses, and the consolidated
`experiments/policy_comprehension/experiment_results/experiment_0_results.json`
file are retained with 41 records: 38 completed calls and 3 API errors.

## User Study

`Dataset/user_study/policy_summarizer_user_study.zip` contains the study
interface, consent flow, questions, policy materials, and coded response data.
The retained response file contains 41 unique participant identifiers.

## Audit Scope

The audit recomputes statistics already represented in retained files. It does
not invoke a language model. Fresh stochastic runs use the protocol scripts in
`experiments/sample_size/` and `experiments/z3_baseline/` and require an API
key for the configured provider.
