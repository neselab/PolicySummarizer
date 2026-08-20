# Regex Simplification

This experiment starts from Quacky's DFA-derived resource expression, asks a
language model for a shorter expression, and measures the proposed expression
against the formal language using directional differences and Jaccard coverage.

`simplify.py` is the original experiment driver. The adjacent CSV and text
files retain the measured outputs and intermediate expressions.

`legacy/root_snapshot/` preserves the distinct pre-restructure driver and run
records.
