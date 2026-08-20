# Policy Reconstruction Experiment

This experiment tests whether a policy can be reconstructed from a
natural-language explanation of its behavior.

## Workflow

1. Read an AWS IAM policy from `Dataset/`.
2. Ask the configured model to explain the policy in natural language.
3. Ask the model to reconstruct an IAM policy from that explanation.
4. Translate the original and reconstructed policies with Quacky.
5. Enumerate requests accepted by one policy but not the other.
6. Summarize those directional differences and record the comparison.

`Exp-1.py` is the retained experiment driver. It uses the xAI
OpenAI-compatible endpoint and requires `GROK_API_KEY`. Its retained logs and
progress state are stored in this directory.

`legacy/root_snapshot/` preserves the distinct pre-restructure driver and run
records.

The maintained PolicySummarizer runtime is under `../../policysummarizer/`.
Input policies are under `../../Dataset/`.
