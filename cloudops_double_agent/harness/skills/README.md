# Optional Skills Extension

This directory is reserved for optional diagnostic skills.

The current CloudOps agent is a **Skill-free ReAct baseline**. Its runtime does
not scan, load, select, or inject files from this directory, so adding this
directory does not change the agent's current behavior.

Projects that want to add skills should define their own:

- skill format and validation rules;
- skill loader;
- skill selection or routing mechanism;
- context-injection policy;

Simply placing a file in this directory does not enable it at runtime.
