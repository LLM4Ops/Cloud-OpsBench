# CloudOps Agents

Each subdirectory is a complete, standalone agent implementation. Agent
variants must keep their own configuration, harness, runtime, tools,
requirements, and evaluator; they must not import from or link to another
agent directory.

- `cloudops_agent/`: Skill-free ReAct baseline.
- `cloudops_skill_agent/`: ReAct agent with explicit symptom selection and
  on-demand Diagnostic Graph Skills.

Use a separate `diagnosis.save_root` for each agent when comparing variants.
