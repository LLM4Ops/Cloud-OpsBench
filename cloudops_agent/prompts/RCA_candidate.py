VALID_NODES = ["master", "worker-01", "worker-02", "worker-03"]

SYSTEM_VALID_SERVICES = {
    "boutique": [
        "frontend",
        "cartservice",
        "productcatalogservice",
        "currencyservice",
        "paymentservice",
        "shippingservice",
        "emailservice",
        "checkoutservice",
        "recommendationservice",
        "adservice",
        "redis-cart",
    ],
    "train-ticket": [
        "ts-assurance-service",
        "ts-auth-service",
        "ts-avatar-service",
        "ts-basic-service",
        "ts-cancel-service",
        "ts-config-service",
        "ts-consign-price-service",
        "ts-consign-service",
        "ts-contacts-service",
        "ts-delivery-service",
        "ts-execute-service",
        "ts-food-delivery-service",
        "ts-food-service",
        "ts-gateway-service",
        "ts-inside-payment-service",
        "ts-news-service",
        "ts-notification-service",
        "ts-order-other-service",
        "ts-order-service",
        "ts-payment-service",
        "ts-preserve-other-service",
        "ts-preserve-service",
        "ts-price-service",
        "ts-rebook-service",
        "ts-route-plan-service",
        "ts-route-service",
        "ts-seat-service",
        "ts-security-service",
        "ts-station-food-service",
        "ts-station-service",
        "ts-ticket-office-service",
        "ts-train-food-service",
        "ts-train-service",
        "ts-travel-plan-service",
        "ts-travel-service",
        "ts-travel2-service",
        "ts-ui-dashboard",
        "ts-user-service",
        "ts-verification-code-service",
        "ts-voucher-service",
        "ts-wait-order-service",
        "tsdb-mysql",
    ],
}

SYSTEM_VALID_NAMESPACES = {
    "boutique": ["boutique"],
    "train-ticket": ["train-ticket"],
}

root_cause_list_str = """
- namespace_cpu_quota_exceeded (Requires Target: NAMESPACE): CPU resource quota exceeded
- namespace_memory_quota_exceeded (Requires Target: NAMESPACE): memory resource quota exceeded
- namespace_pod_quota_exceeded (Requires Target: NAMESPACE): Pod count quota exceeded
- namespace_service_quota_exceeded (Requires Target: NAMESPACE): Service count quota exceeded
- namespace_storage_quota_exceeded (Requires Target: NAMESPACE): storage resource quota exceeded
- missing_service_account (Requires Target: APP): missing ServiceAccount
- node_cordon_mismatch (Requires Target: APP): Pod cannot be scheduled because the node is cordoned
- node_affinity_mismatch (Requires Target: APP): node affinity configuration mismatch
- node_selector_mismatch (Requires Target: APP): node selector mismatch
- pod_anti_affinity_conflict (Requires Target: APP): Pod anti-affinity rule conflict
- taint_toleration_mismatch (Requires Target: APP): taint and toleration mismatch
- cpu_capacity_mismatch (Requires Target: APP): insufficient node CPU capacity
- memory_capacity_mismatch (Requires Target: APP): insufficient node memory capacity
- node_network_delay (Requires Target: NODE): excessive node network latency
- node_network_packet_loss (Requires Target: NODE): node network packet loss
- containerd_unavailable (Requires Target: NODE): containerd unavailable
- kubelet_unavailable (Requires Target: NODE): kubelet unavailable
- kube_proxy_unavailable (Requires Target: NODE): kube-proxy unavailable
- kube_scheduler_unavailable (Requires Target: NODE): kube-scheduler unavailable
- image_registry_dns_failure (Requires Target: APP): image registry DNS resolution failure
- incorrect_image_reference (Requires Target: APP): incorrect image reference
- missing_image_pull_secret (Requires Target: APP): missing image pull secret
- pvc_selector_mismatch (Requires Target: APP): PVC selector mismatch
- pvc_storage_class_mismatch (Requires Target: APP): PVC storage class mismatch
- pvc_access_mode_mismatch (Requires Target: APP): PVC access mode mismatch
- pvc_capacity_mismatch (Requires Target: APP): PVC capacity mismatch
- pv_binding_occupied (Requires Target: APP): PV binding already occupied
- volume_mount_permission_denied (Requires Target: APP): volume mount permission denied
- oom_killed (Requires Target: APP): process killed due to out-of-memory
- liveness_probe_incorrect_protocol (Requires Target: APP): incorrect liveness probe protocol
- liveness_probe_incorrect_port (Requires Target: APP): incorrect liveness probe port
- liveness_probe_incorrect_timing (Requires Target: APP): incorrect liveness probe timing configuration
- readiness_probe_incorrect_protocol (Requires Target: APP): incorrect readiness probe protocol
- readiness_probe_incorrect_port (Requires Target: APP): incorrect readiness probe port
- service_selector_mismatch (Requires Target: APP): Service selector mismatch
- service_port_mapping_mismatch (Requires Target: APP): incorrect Service port mapping
- service_protocol_mismatch (Requires Target: APP): incorrect Service protocol configuration
- service_env_var_address_mismatch (Requires Target: APP): incorrect service address environment variable configuration
- pod_cpu_overload (Requires Target: APP): excessive Pod CPU load
- pod_network_delay (Requires Target: APP): excessive Pod network latency
- service_sidecar_port_conflict (Requires Target: APP): sidecar port conflict
- service_dns_resolution_failure (Requires Target: APP): service DNS resolution failure
- mysql_invalid_credentials (Requires Target: APP): invalid MySQL credentials
- mysql_invalid_port (Requires Target: APP): incorrect MySQL port
- missing_secret_binding (Requires Target: APP): missing Secret binding
- db_connection_exhaustion (Requires Target: APP): database connections exhausted
- db_readonly_mode (Requires Target: APP): database in read-only mode
- gateway_misrouted (Requires Target: APP): incorrect gateway routing
- deployment_zero_replicas (Requires Target: APP): Deployment replica count is 0
"""

taxonomy_definitions = {
    "Admission_Fault": "Refers to failures caused by the Admission Controller rejecting the request (e.g., due to policy or resourcequota constraints) after it is received by the API Server but before it is persisted to etcd",
    "Scheduling_Fault": "Refers to failures where a Pod has passed admission and is written to etcd, but the kube-scheduler cannot assign a suitable node, causing it to remain in a Pending state for a long time.",
    "Infrastructure_Fault": "Refers to failures arising from the underlying cluster resources or critical Kubernetes system components, which occur independently of user business applications and configurations.",
    "Startup_Fault": "Refers to failures where the Pod has been successfully scheduled to a node but fails during image pulling or container initialization, preventing the Pod from entering the Running state.",
    "Runtime_Fault": "Refers to scenarios where the application container has successfully started and entered the Running state, but exits abnormally or behaves erratically due to internal errors or external dependency failures, or Kubernetes health probes.",
    "Service_Routing_Fault": "Refers to connectivity or discovery failures caused by misconfigurations of Kubernetes networking resources that disrupt traffic routing between Pods or external clients, excluding outages caused by system-level infrastructure.",
    "Performance_Fault": "Refers to scenarios where the application functions functionally but performance metrics degrade significantly (e.g., high latency, low throughput, resource bottlenecks), failing to meet SLOs."
}


def build_expected_output(system: str = "train-ticket") -> str:
    system_key = system if system in SYSTEM_VALID_SERVICES else "train-ticket"
    valid_services = SYSTEM_VALID_SERVICES[system_key]
    valid_namespaces = SYSTEM_VALID_NAMESPACES[system_key]

    return f"""
A final diagnostic report in **strict JSON format**.
Your response MUST NOT contain any text before or after the JSON block.

### DIAGNOSTIC TASK ###
Based on the analyzed evidence, your **primary goal (Main Task)** is to identify the **most likely diagnosis** of the incident, which strictly consists of identifying both the **root cause** and the **victim object**.

**Main Task (Core Diagnosis):**
1. **The Root Cause**: Specify exactly what went wrong.
2. **The Victim Object**: Identify where that fault actually resides. The victim object must be one of: node / app / namespace.
   Here, `APP` refers to the affected **application-level business service unit** (e.g., `adservice`, `cartservice`, `frontend`).
   **Constraint:** The object's type must match the `(Requires Target: ...)` tag defined next to your chosen root cause.

**Auxiliary Task (Supplementary Label):**
3. **The Category (Taxonomy)**: Map the fault to exactly ONE category based on the **Origin Phase** (where the error originated), NOT just the observed symptom. This is an auxiliary field and is NOT the central objective of your diagnosis.

Important:
- A valid diagnosis is centered on jointly identifying **both the root cause and the victim object**.
- The taxonomy is a secondary, higher-level categorization and should simply be inferred from the best available evidence once the root cause and victim object are sufficiently established.
- Do NOT delay finalization merely to repeatedly verify or deduce the taxonomy if the core targets (root cause and victim object) already have strong evidence support.

### OBJECT SEMANTICS ###
This abstraction is used because, in our benchmarked microservice systems, the Kubernetes Service / Deployment / Pod instances associated with the same business service are tightly coupled and usually correspond to the same application-level fault subject.
Therefore, `app/<name>` should be interpreted as the affected business service unit, without requiring the diagnosis to further distinguish whether the fault is manifested directly on the Pod, Deployment, or Kubernetes Service object.

### FINALIZATION RULE ###
Once you have sufficient evidence for a specific root cause and victim object (the Main Task) that together explain the reported symptom, you should finalize the diagnosis.
You do not need exhaustive verification of every structured field, especially the auxiliary taxonomy field, before outputting the JSON result.
The taxonomy and fault object should reflect your best evidence-based judgment at the time of finalization.

### RANKING STRATEGY ###
- We evaluate performance based on **Top-3 predictions** of the core diagnosis (root cause + victim object).
- **Rank 1** must be your most confident conclusion supported by the strongest evidence.
- **Rank 2 and Rank 3** should be plausible alternatives or next-best explanations based on the evidence already collected.
- Do NOT perform extra low-information-gain tool calls merely to improve Rank 2, Rank 3, or the auxiliary taxonomy field.
- If Rank 1 is already strongly supported, finalize rather than repeatedly confirming the same evidence.

### CONSTRAINT LISTS (Select strictly from these lists) ###

**[List A: Valid Taxonomies]**
{taxonomy_definitions}

**[List B: Valid Root Causes]**
{root_cause_list_str}

**[List C: Valid Resource Names]**
- Nodes: {VALID_NODES}
- APP: {valid_services}
- Namespaces: {valid_namespaces}

### OUTPUT FORMAT ###
Construct the JSON using the values selected above.
For `fault_object`, combine the `Kind` (determined by you: node/app/namespace) with the `Name` selected from List C.
Format: `Kind/Name` (e.g., `node/worker-01`).

- `top_3_predictions`: a list of 3 diagnosis results.
- Rank 2 and Rank 3 are alternative hypotheses, not evidence that requires separate exhaustive validation.

```json
{{
  "key_evidence_summary": "... (Concise summary of the key evidence supporting the diagnosis)",
  "top_3_predictions": [
    {{
      "rank": 1,
      "fault_taxonomy": "... (Select from List A)",
      "fault_object": "... (Kind + Name from List C)",
      "root_cause": "... (Select from List B)"
    }},
    {{
      "rank": 2,
      "fault_taxonomy": "... (Select from List A)",
      "fault_object": "... (Kind + Name from List C)",
      "root_cause": "... (Select from List B)"
    }},
    {{
      "rank": 3,
      "fault_taxonomy": "... (Select from List A)",
      "fault_object": "... (Kind + Name from List C)",
      "root_cause": "... (Select from List B)"
    }}
  ]
}}
```
"""


expected_output = build_expected_output("train-ticket")

agent_prompt = """
You are a professional Kubernetes operations engineer with extensive experience in systematic troubleshooting. 
**Your Goal:** Diagnose the root cause of the reported issue based on factual evidence collected from the system.

**Instructions:**
1. You have access to a set of diagnostic tools. You must independently decide which tools to use and the execution order based on your findings.
2. Do NOT guess or assume the system state. Every conclusion must be backed by concrete output from a tool.
3. If a tool returns no anomalies, discard that hypothesis and pivot to a different investigation path. Do not speculate without proof.
4. Provide a clear reasoning chain that connects the initial symptom to the final root cause, supported by the evidence you collected.

**Important Constraints:**
- This benchmark scenario contains **one and only one primary fault**.
- Find the root cause with the minimum number of steps.
- Limit your internal reasoning to a few concise sentences. Then, IMMEDIATELY output the tool execution.
- Focus ONLY on deciding the immediate next step based on current evidence.

**CRITICAL SYNTAX RULES:**
1. **Empty Parameters:** If a tool (like `GetClusterConfiguration` or `GetAlerts`) does not require any parameters, you **MUST** provide an empty JSON dictionary as the input.
  * **CORRECT:**
  Action: GetClusterConfiguration
  Action Input: {}

2. The "Action Input" field is mandatory for every tool call.

IMPORTANT: When classifying the fault stage in your final response, you MUST strictly follow the definition in [List A: Valid Taxonomies].

Begin your investigation now.
"""
