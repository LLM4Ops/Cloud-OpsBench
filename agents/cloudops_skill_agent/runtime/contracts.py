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
- container_memory_limit_too_low (Requires Target: APP): process killed due to low memory configuration
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
- code_busy_loop (Requires Target: APP): application code contains a CPU-intensive busy loop
- code_memory_leak (Requires Target: APP): application code leaks memory or retains data unexpectedly
- code_artificial_delay (Requires Target: APP): application code introduces artificial latency or blocking delay
- code_excessive_file_reads (Requires Target: APP): application code performs excessive file reads
- code_excessive_file_writes (Requires Target: APP): application code performs excessive file writes
- code_wrong_return (Requires Target: APP): application code returns an incorrect value or wrong response
- code_missing_parameter (Requires Target: APP): application code omits a required parameter in a call/request
- code_wrong_argument_order (Requires Target: APP): application code passes arguments in the wrong order
"""

def build_expected_output(system: str = "train-ticket") -> str:
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


expected_output = build_expected_output("train-ticket")
