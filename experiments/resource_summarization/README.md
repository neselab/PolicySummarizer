# Resource-Sample Summarization Experiment

This experiment measures how accurately a model can infer a regular expression
from resource strings accepted by an access-control policy.

## Workflow

1. Use Quacky and ABC to generate accepted resource strings.
2. Ask the configured model to produce a regular expression from the samples.
3. Compare the candidate expression with the policy-derived language.
4. Record directional counts and Jaccard coverage.

`Exp-2.py` is the retained experiment driver. The CSV files in this directory
contain the recorded outputs. The current maintained multi-size protocol is
`../sample_size/run_protocol.py`, which runs through Docker, records complete
candidate traces, and supports resumable output directories.

`legacy/root_snapshot/` preserves the distinct pre-restructure driver and run
records.
