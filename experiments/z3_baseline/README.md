# Z3 Enumeration Baseline

This experiment enumerates distinct satisfying resource strings with Z3,
prompts a language model for multiple candidate regular expressions, repairs
invalid regex syntax once, and retains the highest-coverage candidate.

## Maintained Protocol

Run one API-free enumeration check:

```bash
bash experiments/z3_baseline/run.sh \
  --enumerate-only --start-from 0 --end-at 0
```

Run the best-of-five model-backed protocol:

```bash
export ANTHROPIC_API_KEY="your-key"
bash experiments/z3_baseline/run.sh \
  --max-models 1000 --num-candidates 5 --syntax-repairs 1 --resume
```

`z3_model_enum.py` and `run.sh` are the maintained implementation.
`legacy/` contains the original workstation-specific scripts and intermediate
files retained with the experiment record.
