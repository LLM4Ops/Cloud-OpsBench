# Skill-enabled CloudOps Harness

A modular Cloud-OpsBench agent with explicit symptom selection and
on-demand Diagnostic Graph Skills.

```text
system prompt + symptom catalog + full ReAct history
             -> LLM
             -> CloudOps tool or SelectSymptom
             -> selected Skill injected into subsequent prompts
             -> Submit(top-3 diagnosis)
```

The harness and Skill files are imported from the CloudOps Harness experiment.
The outcome/process evaluator and its top-3 diagnosis contract remain the
implementation from `codex/refactor-cloudops-agent`.

## Structure

- `harness/`: Skill-enabled ReAct loop, context construction and system prompt.
- `harness/skills/`: symptom catalogs and Diagnostic Graph Skills.
- `runtime/`: state, Skill loader, parser, LLM adapter, tool executor and output contract.
- `tools/`: Cloud-OpsBench snapshot-backed tools for Boutique and TrainTicket.
- `evaluation_utils/`: official process-evaluation implementation.
- `run.py`: runs the configured system/category.
- `evaluation.py`: evaluates the trajectories selected by the same configuration.

`SelectSymptom` is an internal harness action. It records the selected symptom
in the trajectory but is not counted as a CloudOps tool call by the process
evaluator. A selected Skill is loaded into the next model prompt.

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
