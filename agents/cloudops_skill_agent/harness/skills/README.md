# Diagnostic Graph Skills

The Skill-enabled harness loads the YAML files under the configured system
directory at startup.

The model first sees a compact symptom catalog. Calling the internal
`SelectSymptom` action with an exact `symptom_id` activates that Skill, and its
complete diagnostic graph is included in subsequent prompts. A later
`SelectSymptom` call replaces the active Skill.

Each system directory contains self-contained schema-version-1 YAML Skills.
The runtime validates their keys, graph edges, actions and system identifier
before any case is run.
