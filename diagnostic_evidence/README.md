# Diagnostic Evidence Graph

This package implements process-level ground-truth annotation for Cloud-OpsBench.

Core ideas:

- A milestone is a diagnostic fact, not a command.
- Each milestone has one or more admissible tool uses with evidence patterns.
- Dependency edges encode evidence sufficiency, not command order.
- Extra exploratory calls receive no milestone credit but do not cause a process failure.

Useful entry points:

- `load_annotations(path)` reads JSON annotations.
- `load_golden_trajectory(path)` reads a golden path as action/observation steps.
- `load_tool_cache(path)` converts a full cache into steps for matching.
- `build_tool_cache_index(path)` creates a compact observation index for annotation work.
- `enumerate_q_candidates(annotation, steps)` scans a tool cache with the same evidence patterns used by scoring.
- `evaluate_trajectory(annotation, steps)` returns established milestones and dependency status.

Q enumeration:

```bash
python3 -m diagnostic_evidence.cli enumerate-q \
  --annotations process-label/boutique/infrastructure/2/milestone.json \
  --tool-cache benchmark/boutique/infrastructure/2/tool_cache.json \
  --mode strict
```

Use `--mode evidence-only` during annotation to find possible equivalent tool calls across the full cache. Use `--mode strict` to verify that the current annotated `admissible_tool_uses` are present and match their `evidence_patterns`.
