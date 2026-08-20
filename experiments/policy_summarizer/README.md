# PolicySummarizer Evaluation Outputs

This directory contains the retained outputs from applying PolicySummarizer to
AWS IAM, Azure RBAC, GCP IAM, and mutated-policy inputs.

| Path | Contents |
| --- | --- |
| `results_aws/` | AWS direct and sample-based characterization records |
| `regex_results/` | Azure and GCP automata-expression simplification records |
| `string_results/` | Azure and GCP sample-based synthesis records |
| `results_mutation/` | Directional comparisons between original and mutated policies |
| `results_report.ipynb` | Analysis notebook for retained results |

Recompute the aggregate measurements represented by these files with:

```bash
bash validation/check.sh audit
```

Fresh PolicySummarizer runs use the product pipelines documented in
[`../../policysummarizer/README.md`](../../policysummarizer/README.md).
