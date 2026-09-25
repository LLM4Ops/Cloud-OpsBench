# CloudOps Harness Refactor

A modular, Skill-free Cloud-OpsBench baseline agent.

```text
system prompt + full ReAct history
             -> LLM
             -> one CloudOps tool action
             -> observation appended to context
             -> Submit(top-3 diagnosis)
```

This baseline intentionally contains no Diagnostic Skills, symptom catalog,
`SelectSymptom`, Failure Analysis, or Harness Evolution logic.

## Structure

- `harness/`: ReAct loop, context construction, no-op hooks and system prompt.
- `runtime/`: state, parser, LLM adapter, tool executor and output contract.
- `tools/`: Cloud-OpsBench snapshot-backed tools for Boutique and TrainTicket.
- `evaluation_utils/`: official process-evaluation implementation.
- `run.py`: runs the configured system/category.
- `evaluation.py`: evaluates the trajectories selected by the same configuration.

## Configuration and execution

Fill in `configs/model_configs.yaml`. All model, path, system, category and
case-selection settings live there. Leave `diagnosis.case_name` empty to run
the full configured category, or set one numeric case id.

`model.enable_thinking` is optional and provider-specific. Leave it absent for
GPT, Gemini/Flash and endpoints that do not define this parameter. For Qwen,
set it explicitly to `true` or `false`; it is then sent through `extra_body`.

```bash
python run.py
python evaluation.py
```

No command-line arguments are required or interpreted.

## Metrics

The evaluator is the Cloud-OpsBench outcome/process evaluator and reports:

- `CA`: component/fault-object accuracy at rank 1.
- `FA`: root-cause accuracy at rank 1.
- `JRA`: joint rank-1 RCA accuracy (both component and root cause correct).
- `MC`: diagnostic milestone coverage.
- `EOC`: evidence-order consistency.
- `ECR`: evidence closure rate.
- `EE`: evidence efficiency.
- `steps`: average diagnostic action count.
- `RAR`: redundant action rate.
- `invalid_actions`: average invalid actions per case.
