# Policy Comprehension Assessment

This experiment asks a model to explain a cloud policy, reconstructs a policy
from that explanation, and compares the original and reconstructed policies.
It measures whether an explanation preserves operational policy behavior rather
than only sounding plausible.

The driver is `cpca.py`. It supports selecting model families with `--models`,
uses the 41-policy corpus in `Dataset/`, and writes checkpoints and combined
results to the selected output directory.

```bash
python experiments/policy_comprehension/cpca.py --help
```

Fresh runs require the API credentials for the selected model providers.

`legacy/root_snapshot/` preserves the distinct pre-restructure driver.
