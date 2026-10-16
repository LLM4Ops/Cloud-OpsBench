from __future__ import annotations

from pathlib import Path

from runtime.core import CaseState, StepRecord
from runtime.contracts import SYSTEM_VALID_SERVICES, SYSTEM_VALID_NAMESPACES, root_cause_list_str, VALID_NODES


class DoubleAgentContextBuilder:
    """Build the complete text prompt while retaining the full ReAct history."""

    def __init__(self, *, tools_description: str, system: str):
        self.tools_description = tools_description
        self.system = system
        self.diagnostic_prompt = Path(__file__).with_name("diagnostic.md").read_text(
            encoding="utf-8"
        ).strip()
        self.verifier_prompt = Path(__file__).with_name("verifier.md").read_text(
            encoding="utf-8"
        ).strip()


    def build_diagnostic(self, state: CaseState, verifier_answer: str) -> str:
        sections = [
            self.diagnostic_prompt,
            "## Available Tools\nYou may use exactly one tool per step.\n"
            + self.tools_description,
            "## Final Diagnosis Output Requirement\n"
            "When you decide to finish, call `Submit`. Its Action Input must "
            "strictly follow this specification.\n"
            + self._build_expected_output(self.system).strip(),
            self._history(state),
            self._build_verifier_agent_section(verifier_answer),
            "## Current Case\n"
            f"Question: {state.question}\n"
            f"Current Step: {state.current_step + 1}\n"
            f"Budget Steps: {state.max_steps}",
        ]
        return "\n\n".join(section for section in sections if section.strip())

    def _build_verifier_agent_section(self, verifier_answer: str) -> str:
        if not verifier_answer:
            return ""

        return "A Verifier Agent analysed your last steps and replied:\n" \
        f"{verifier_answer}\n\n"

    
    
    def _build_expected_output(self, system: str = "train-ticket") -> str:
        system_key = system if system in SYSTEM_VALID_SERVICES else "train-ticket"
        valid_services = SYSTEM_VALID_SERVICES[system_key]
        valid_namespaces = SYSTEM_VALID_NAMESPACES[system_key]

        return f"""
A final diagnostic report submitted through the explicit `Submit` action.
The `Submit` Action Input MUST be the strict JSON object below.

### DIAGNOSTIC TASK ###
Based on the analyzed evidence, your **primary goal (Main Task)** is to identify the **most likely diagnosis** of the incident, which strictly consists of identifying both the **root cause** and the **victim object**.

**Main Task (Core Diagnosis):**
1. **The Root Cause**: Specify exactly what went wrong.
2. **The Victim Object**: Identify where that fault actually resides. The victim object must be one of: node / app / namespace.
Here, `APP` refers to an affected **application-level business service unit** from the system-specific resource list below.
**Constraint:** The object's type must match the `(Requires Target: ...)` tag defined next to your chosen root cause.

Important:
- A valid diagnosis is centered on jointly identifying **both the root cause and the victim object**.

### OBJECT SEMANTICS ###
This abstraction is used because, in our benchmarked microservice systems, the Kubernetes Service / Deployment / Pod instances associated with the same business service are tightly coupled and usually correspond to the same application-level fault subject.
Therefore, `app/<name>` should be interpreted as the affected business service unit, without requiring the diagnosis to further distinguish whether the fault is manifested directly on the Pod, Deployment, or Kubernetes Service object.

### FINALIZATION RULE ###
Once you have sufficient evidence for a specific root cause and victim object (the Main Task) that together explain the reported symptom, you should finalize the diagnosis.
The fault object and root cause should reflect your best evidence-based judgment at the time of finalization.

### RANKING STRATEGY ###
- Return **Top-3 predictions** to preserve the benchmark output format; the primary benchmark metrics use Rank 1.
- **Rank 1** must be your most confident conclusion supported by the strongest evidence.
- **Rank 2 and Rank 3** should be plausible alternatives or next-best explanations based on the evidence already collected.
- Do NOT perform extra low-information-gain tool calls merely to improve Rank 2 or Rank 3.
- If Rank 1 is already strongly supported, finalize rather than repeatedly confirming the same evidence.

### CONSTRAINT LISTS (Select strictly from these lists) ###

**[List A: Valid Root Causes]**
{root_cause_list_str}

**[List B: Valid Resource Names]**
- Nodes: {VALID_NODES}
- APP: {valid_services}
- Namespaces: {valid_namespaces}

### OUTPUT FORMAT ###
Construct the JSON using the values selected above.
For `fault_object`, combine the `Kind` (determined by you: node/app/namespace) with the `Name` selected from List B.
Format: `Kind/Name` (e.g., `node/worker-01`).

- `top_3_predictions`: a list of 3 diagnosis results.
- Rank 2 and Rank 3 are alternative hypotheses, not evidence that requires separate exhaustive validation.

{{
"key_evidence_summary": "... (Concise summary of the key evidence supporting the diagnosis)",
"top_3_predictions": [
    {{
    "rank": 1,
    "fault_object": "... (Kind + Name from List B)",
    "root_cause": "... (Select from List A)"
    }},
    {{
    "rank": 2,
    "fault_object": "... (Kind + Name from List B)",
    "root_cause": "... (Select from List A)"
    }},
    {{
    "rank": 3,
    "fault_object": "... (Kind + Name from List B)",
    "root_cause": "... (Select from List A)"
    }}
]
}}
"""


    def build_verifier(self, state: CaseState, diagnostic_answer: str) -> str:
        sections = [
            self.verifier_prompt,
            # "## Available Tools\nYou may use exactly one tool per step.\n"
            # + self.tools_description,
            "## Output Requirement\n"
            "Your output must strictly follow this specification.\n"
            + self._build_expected_output_verifier(self.system).strip(),
            self._history(state),
            self._build_proposed_diagnosis_section(diagnostic_answer),
            "## Current Case\n"
            f"Question: {state.question}\n"
            f"Current Step: {state.current_step + 1}\n"
            f"Budget Steps: {state.max_steps}",
        ]
        return "\n\n".join(section for section in sections if section.strip())

    def _build_proposed_diagnosis_section(self, diagnostic_answer: str) -> str:
        if not diagnostic_answer:
            return ""
        return (
            "## Proposed Diagnosis (under review)\n"
            "This is the diagnosis you are reviewing right now - it is NOT yet part of the evidence trail above:\n"
            f"{diagnostic_answer}"
        )

    
    def _build_expected_output_verifier(self, system: str = "train-ticket") -> str:
        system_key = system if system in SYSTEM_VALID_SERVICES else "train-ticket"
        valid_services = SYSTEM_VALID_SERVICES[system_key]
        valid_namespaces = SYSTEM_VALID_NAMESPACES[system_key]

        return f"""
You do NOT produce a diagnosis yourself. You produce a VERDICT on the diagnosis another engineer already proposed.

### WHAT YOU ARE REVIEWING ###
The proposing engineer's evidence trail and their proposed diagnosis both appear above, under "## Previous Steps" - the proposal is the most recent "Final Output" entry there. It is a JSON object shaped like this:

{{
  "key_evidence_summary": "...",
  "top_3_predictions": [
    {{"rank": 1, "fault_object": "Kind/Name", "root_cause": "..."}},
    {{"rank": 2, "fault_object": "Kind/Name", "root_cause": "..."}},
    {{"rank": 3, "fault_object": "Kind/Name", "root_cause": "..."}}
  ]
}}

For reference while you check it, here are the same constraint lists the proposing engineer had to follow:

**[List A: Valid Root Causes]**
{root_cause_list_str}

**[List B: Valid Resource Names]**
- Nodes: {VALID_NODES}
- APP: {valid_services}
- Namespaces: {valid_namespaces}

### YOUR OUTPUT FORMAT ###
You do not call diagnostic tools. You have exactly two possible verdicts, and you MUST express your verdict using this exact format (same shape as a tool call):

Thought: <your review reasoning, a few concise sentences>
Action: <Agree or Disagree>
Action Input: <JSON object>

- If the diagnosis is fully and correctly supported by the evidence trail:
Action: Agree
Action Input: {{}}

- If it is NOT (unsupported Rank-1 claim, invalid root_cause/fault_object, a better-supported alternative was ignored, malformed fault_object/root_cause, wrong Requires-Target Kind, etc.):
Action: Disagree
Action Input: {{"reason": "<specific, actionable explanation the proposing engineer can act on - cite which evidence entry supports your objection, or state what is missing>"}}

Do NOT output a `top_3_predictions` JSON yourself. Do NOT output anything other than the Thought/Action/Action Input block above.
"""

    
    @staticmethod
    def _history(state: CaseState) -> str:
        if not state.history:
            return "## Previous Steps\nNone yet."
        return "## Previous Steps\n\n" + "\n\n".join(
            DoubleAgentContextBuilder._format_step(step) for step in state.history
        )

    @staticmethod
    def _format_step(step: StepRecord) -> str:
        parts = [f"Step {step.step_id}"]
        if step.thought:
            parts.append(f"Thought: {step.thought}")
        if step.action_type in {"tool", "submit"}:
            parts.append(f"Action: {step.action_name}")
            parts.append(f"Action Input: {step.action_input}")
        if step.observation is not None:
            parts.append(f"Observation: {step.observation}")
        if step.error:
            parts.append(f"Error: {step.error}")
        return "\n".join(parts)


