# Sample-Size Experiment

This experiment measures how the number of accepted resource examples affects
the coverage of a model-generated regular expression.

## Maintained Protocol

`run_protocol.py` evaluates sample sizes 100, 500, 1,000, 1,500, and 2,000. For
each policy and size it retains:

- the generated resource strings;
- every model candidate and syntax-repair attempt;
- Quacky diagnostics and directional coverage counts;
- model identifiers and token usage;
- elapsed time and aggregate scores.

Inspect the workload without an API call:

```bash
bash experiments/sample_size/run_protocol.sh --dry-run
```

Exercise one sample-generation case without an API call:

```bash
bash experiments/sample_size/run_protocol.sh \
  --enumerate-only --sample-sizes 100 --start-from 0 --end-at 0
```

Run the full LLM-backed protocol:

```bash
export ANTHROPIC_API_KEY="your-key"
bash experiments/sample_size/run_protocol.sh \
  --model "your-available-model-id" --resume
```

`Exp-3.py`, `multi-string.csv`, and the adjacent logs are the retained original
experiment implementation and outputs. `retained_regex/` stores saved regex
records from the historical sweep.

`legacy/root_snapshot/` preserves the distinct pre-restructure implementation
and run records.
