import os
import json
import random
from typing import List, Dict, Any


# provide 3 prompt engineering:
# get_icl_prompt(case_path)
# get_rag_prompt()
# get_cot_prompt()

rag_context="""
## I. Pod Failure Category

### Item 1: Pod Stuck in Pending State (Scheduling & Resource Allocation Abnormality)
【Failure Scenario】 The Pod remains in Pending state for a long time after creation and is not scheduled to any Node.
【Core Symptoms】 `kubectl get pods` shows STATUS as Pending, with no Node assignment information.
【In-depth Troubleshooting Path】

1. Resource Scheduling Bottleneck
   Mechanism: The Scheduler cannot find a node that meets the Pod's resources.requests (CPU/Memory).
   Diagnostic Command: Run `kubectl describe pod <pod-name>` to check for FailedScheduling in Events.
   Extended Check: Verify if there are ResourceQuota (namespace-level quota) restrictions, not just physical cluster resources.
   Solution: Scale up cluster nodes, reduce Pod resource requests, or adjust ResourceQuota/LimitRange.

2. PVC Binding Latency
   Mechanism: The Pod defines a PVC, but the corresponding PV is not ready or the CSI driver fails to mount it.
   Diagnosis: Check if Events show FailedScheduling with reasons such as "volume node affinity conflict" or "PersistentVolumeClaim is not bound".
   Solution: Fix StorageClass configuration or PVC/PV binding relationships.

3. Advanced Scheduling Constraints
   Mechanism: The Pod has strict nodeSelector, nodeAffinity, or tolerations configured, resulting in no matching nodes.
   Diagnosis: Compare the Pod's Spec with the Node's Labels/Taints.
   Solution: Remove conflicting Taints or correct affinity rules.

4. Control Plane Failure
   Mechanism: The Scheduler component itself is down or not elected as Leader.
   Diagnosis: Check the status of the kube-scheduler component; Check cluster node status and verify whether any node is in NotReady state.

---

### Item 2: Image Pull Abnormality (ImagePullBackOff / ErrImagePull)
【Failure Scenario】 After the Pod is assigned to a node, container creation fails and the state stays at ImagePullBackOff.
【Core Symptoms】 Kubelet fails to pull the specified image via CRI (Container Runtime Interface).
【In-depth Troubleshooting Path】

1. Image Identifier Verification
   Mechanism: The image name (Repository/Image) or tag is misspelled, or the image does not exist in the repository.
   Diagnosis: Check detailed error information in Events (e.g., ErrImagePull). Use `GetAppYAMLTool` to carefully verify the spelling of the image field.
   Solution: Correct the image field in the Deployment.

2. Authentication & Authorization
   Mechanism: Attempting to pull an image from a Private Registry without providing ImagePullSecrets, or the Secret has an incorrect scope.
   Diagnosis: Check Events for errors such as "repository not found" or "denied: access forbidden".
   Solution: Create a Docker Registry Secret and mount it to the ServiceAccount or Pod Spec.

3. CRI & Networking
   Mechanism: The node cannot resolve the repository domain name (DNS issue), or the container runtime configuration is incorrect.
   Diagnosis: Check Kubelet logs; Check the status of the CRI; test connectivity from the node to the image repository.

---

### Item 3: Container Runtime Crash (CrashLoopBackOff / RunContainerError)
【Failure Scenario】 The Pod is in Running state but restarts frequently, or falls into a CrashLoopBackOff loop.
【Core Symptoms】 The RestartCount metric keeps increasing, and the application cannot stay online.
【In-depth Troubleshooting Path】

1. Exit Code Analysis
   - Code 1/255: Application logic error or missing configuration. Check application logs with `kubectl logs`.
   - Code 137 (OOMKilled): Container memory usage exceeds Limits. Check dmesg or monitoring data, and adjust resources.limits.memory.
   - Code 128 (RunContainerError): Usually related to volume mount failures (e.g., missing ConfigMap/Secret or insufficient permissions).

2. Entrypoint/CMD Configuration
   Mechanism: The Dockerfile does not specify CMD, or the command parameter overridden by Kubernetes is incorrect, causing the process to exit immediately.
   Diagnosis: Since the Dockerfile cannot be viewed directly, use `GetAppYAMLTool` to check if the command and args fields in the Pod Spec are empty or misconfigured (e.g., misspelled). Combine with "command not found" errors in logs for judgment.

3. Liveness/Readiness Probe Misconfiguration
   Mechanism: The liveness/readiness probe port, path, or timeout is set to values that don’t match what the application actually exposes or how long it takes to start; liveness failures make the kubelet restart the container over and over, giving CrashLoopBackOff, while readiness failures leave the Pod Running but 0/1 READY, so traffic is dropped. 
   Diagnosis: `kubectl describe pod` read the Events for “refused/timeout/500”, and compare the probe’s port, path and initialDelaySeconds with the application’s real listen port and startup logs.

---

## II. Service Discovery & Network Connectivity Failure Category

### Item 4: Service Traffic Forwarding Failure (Service Discovery Failure)
【Failure Scenario】 ClusterIP or NodePort is inaccessible; DNS resolution is normal but connections time out or are refused.
【Core Symptoms】 `kubectl describe service` shows Endpoints as <none> or traffic blackhole.
【In-depth Troubleshooting Path】

1. Label Selector Mismatch
   Mechanism: The spec.selector defined by the Service does not fully match the Pod's metadata.labels (case-sensitive).
   Diagnosis: Compare the Service Selector with Pod Labels, and check if the Endpoints list is empty.
   Solution: Correct the label matching relationship to ensure the Endpoints Controller can associate the Pod.

2. TargetPort Mapping Error
   Mechanism: The Service's targetPort does not correctly point to the Pod's containerPort (note the difference between Service Port and Target Port).
   Diagnosis: Use `CheckServiceConnectivityTool` to verify Service port connectivity.
   Solution: Ensure targetPort is consistent with the actual port exposed by the container.

3. Configuration Verification
   use `GetAppYAMLTool` to check if the ports, selector or type fields in the Service Spec are empty or misconfigured (e.g., misspelled).

4. Controller & Proxy Failure
   Mechanism: The Pod has an IP but is not registered with the Service (possibly a Controller Manager failure); if Endpoints are normal but inaccessible, Kube-Proxy (iptables/IPVS) rules may be abnormal.
   Diagnosis: Check the status of kube-proxy on nodes.

---

### Item 5: Entry Point Heuristic with Normal Global Status
【Failure Scenario】 `kubectl get pods` shows all green (Running/Ready), but the business is still inaccessible or the page reports errors.
【Core Symptoms】 No obvious crashed containers, and it is unclear where to start troubleshooting.
【In-depth Troubleshooting Path】

1. Frontend/Ingress Log Analysis
   Mechanism: Frontend services (Frontend/Gateway) are the entry point for user traffic and the convergence point of all backend errors. Their logs usually contain key clues such as "which backend service returned 500" or "connection timeout to which IP".
   Diagnostic Action:
   Check frontend services and read the logs of the entry service.
   Judgment Logic: If logs show connect errors for a specific service, shift the diagnostic target to that service immediately. This is an efficient strategy to **"reduce the search space"** and avoid blind traversal of all services.

2. Connectivity Verification
   Mechanism: After locating the target downstream service via logs, verify if the issue is network-level inaccessibility.
   Diagnostic Action: Use `CheckServiceConnectivityTool` to test connectivity to the target service's ClusterIP from the Pod where the entry service is located (if the tool supports source/destination specification) or directly.

---

## III. Performance Propagation & Full-Link Diagnosis Category

### Item 6: Microservice Cascading Failure & Topology Analysis
【Failure Scenario】 The overall system response slows down or reports errors; multiple services seem to have issues, but all Pods are in Running state.
【Core Symptoms】 Failures propagate in the call chain, and errors from upstream services often cover up the real root cause of downstream services.
【In-depth Troubleshooting Path】

1. Downstream Priority Rule (The "Follow-the-Chain" Hint)
   Action: tracing the dependency chain downwards. Do not stop at the first service reporting a timeout.
   Reasoning: If Service A calls Service B, and Service A is slow, the bottleneck is almost always in Service B (or the database B connects to). The root cause lies at the end of the propagation chain.

2. Maximal Deviation Principle (The "Worst-Metric" Hint)
   Observation: Multiple services show degraded metrics, making it hard to pick one.
   Action: Compare the magnitude of deterioration across all suspicious services.
   Reasoning: The service with the most significant performance drop (e.g., highest latency spike, 100% CPU saturation) is the most probable Root Cause. 
"""

cot_context="""
    1. What is the current lifecycle status of the Pod (e.g., Pending, CrashLoopBackOff, Running...)?
    2. What is the specific error message found in the Events or Logs that explains the failure? 
    3. Does the deployment configuration (YAML) contain any specific errors that caused the issue (e.g., incorrect name, typos...)?
    4. If the configuration appears correct, are there any cluster-level issues (e.g., Node NotReady, Cluster component failure...) or resourcequota limit?
    """

# for performance fault
# cot_context="""
# 1. Which specific metrics are showing significant degradation by GetAlerts?
# 2. Which service in the call chain is the primary source of the anomaly based on the magnitude of the degradation?
# 3. Is the performance decline caused by the service's own internal resource bottlenecks or by waiting for downstream dependencies?
# """
def get_rag_prompt():
    agent_prompt=f"""
    "You are a professional Kubernetes operations engineer with extensive experience in systematic troubleshooting. 
    **Your Goal:** Diagnose the root cause of the reported issue based on factual evidence collected from the system.

    **Instructions:**
    1. You have access to a set of diagnostic tools. You must independently decide which tools to use and the execution order based on your findings.
    2. Do NOT guess or assume the system state. Every conclusion must be backed by concrete output from a tool.
    3. If a tool returns no anomalies, discard that hypothesis and pivot to a different investigation path. Do not speculate without proof.
    4. Provide a clear reasoning chain that connects the initial symptom to the final root cause, supported by the evidence you collected.

    Please consider:
    {rag_context}

    **Important:**
    ### 1. Diagnostic Principles
    - Even when all cluster services appear 'Running', it doesn't guarantee full health. You must dive deeper and collect internal failure evidence.
    - Our scenario has one and only one fault. If you find multiple abnormal problems, please report only the most serious one.

    ### 2. Reasoning Style
    - Limit your internal reasoning to few concise sentences. Then, IMMEDIATELY output the tool execution.
    - Do not formulate long-term plans. Focus ONLY on the immediate next step.
    - Find the root cause with the minimum number of steps.

    ### 3. Output Format
    - Before all the diagnostic steps are completed, only the tool call format is allowed, the final answer format is absolutely prohibited.
    - The final answer format is allowed only after you have clearly found the root cause of all abnormal Pods through multiple rounds of tool calls.
    - The two formats cannot be nested, and the tool call results cannot be placed in Final Answer.

    **CRITICAL SYNTAX RULES:**
   1. **Empty Parameters:** If a tool (like `GetClusterConfiguration` or `GetAlerts`) does not require any parameters, you **MUST** provide an empty JSON dictionary as the input.
      * **CORRECT:**
      Action: GetClusterConfiguration
      Action Input: {{}}

   2. The "Action Input" field is mandatory for every tool call.

   IMPORTANT: When classifying the fault stage, you MUST strictly follow this definition in [List A: Valid Taxonomies]
   
   Begin your investigation now.
    """
    return agent_prompt

def get_cot_prompt():
    agent_prompt=f"""
    "You are a professional Kubernetes operations engineer with extensive experience in systematic troubleshooting. 
    **Your Goal:** Diagnose the root cause of the reported issue based on factual evidence collected from the system.

    **Instructions:**
    1. You have access to a set of diagnostic tools. You must independently decide which tools to use and the execution order based on your findings.
    2. Do NOT guess or assume the system state. Every conclusion must be backed by concrete output from a tool.
    3. If a tool returns no anomalies, discard that hypothesis and pivot to a different investigation path. Do not speculate without proof.
    4. Provide a clear reasoning chain that connects the initial symptom to the final root cause, supported by the evidence you collected.

    You should **reason step-by-step** about the way to find the root cause of a fault using provided tools.
    Please consider:
    {cot_context}

    **Important:**
    ### 1. Diagnostic Principles
    - Even when all cluster services appear 'Running', it doesn't guarantee full health. You must dive deeper and collect internal failure evidence.
    - Our scenario has one and only one fault. If you find multiple abnormal problems, please report only the most serious one.

    ### 2. Reasoning Style
    - Limit your internal reasoning to few concise sentences. Then, IMMEDIATELY output the tool execution.
    - Do not formulate long-term plans. Focus ONLY on the immediate next step.
    - Find the root cause with the minimum number of steps.

    ### 3. Output Format
    - Before all the diagnostic steps are completed, only the tool call format is allowed, the final answer format is absolutely prohibited.
    - The final answer format is allowed only after you have clearly found the root cause of all abnormal Pods through multiple rounds of tool calls.
    - The two formats cannot be nested, and the tool call results cannot be placed in Final Answer.

    **CRITICAL SYNTAX RULES:**
   1. **Empty Parameters:** If a tool (like `GetClusterConfiguration` or `GetAlerts`) does not require any parameters, you **MUST** provide an empty JSON dictionary as the input.
      * **CORRECT:**
      Action: GetClusterConfiguration
      Action Input: {{}}

   2. The "Action Input" field is mandatory for every tool call.

   IMPORTANT: When classifying the fault stage, you MUST strictly follow this definition in [List A: Valid Taxonomies]
   
   Begin your investigation now.
    """
    return agent_prompt



def load_case_from_folders(demo_folder: str, fault_folder: str) -> Dict[str, Any]:
    """
    Load diagnostic trace from demo_folder/path1.json and result from fault_folder/metadata.json.
    Assumes both folders share the same base name (e.g., 'case_001').
    """
    with open(os.path.join(demo_folder, "path1.json"), "r", encoding="utf-8") as f:
        trace = json.load(f)["diagnostic_trace"]
    with open(os.path.join(fault_folder, "metadata.json"), "r", encoding="utf-8") as f:
        result = json.load(f)["result"]
    case_name = os.path.basename(demo_folder)
    return {
        "folder_name": case_name,
        "diagnostic_trace": trace,
        "fault_result": result
    }

def get_icl_prompt(demo_path: str, fault_path: str, sample_count: int = 3) -> str:
    """
    Randomly sample ICL cases by pairing subdirectories with the same name from demo_path and fault_path.
    
    Args:
        demo_path: Directory containing subfolders with path1.json (diagnostic traces)
        fault_path: Directory containing subfolders with metadata.json (fault results)
        sample_count: Number of cases to sample
    
    Returns:
        Formatted ICL prompt string for LLM
    """
    # Get sorted list of common subdirectory names
    demo_subdirs = {name for name in os.listdir(demo_path) if os.path.isdir(os.path.join(demo_path, name))}
    fault_subdirs = {name for name in os.listdir(fault_path) if os.path.isdir(os.path.join(fault_path, name))}
    
    current_case_name = os.path.basename(os.path.normpath(fault_path))
    common_names = sorted((demo_subdirs & fault_subdirs) - {current_case_name})
    if not common_names:
        raise ValueError(f"No common subdirectories found between {demo_path} and {fault_path}")
    
    # Randomly sample from common names
    selected_names = random.sample(common_names, min(sample_count, len(common_names)))
    print(f"✅ Sampled {len(selected_names)} cases from paired directories")

    icl_blocks = []
    for i, name in enumerate(selected_names, 1):
        demo_folder = os.path.join(demo_path, name)
        fault_folder = os.path.join(fault_path, name)
        print(demo_folder,fault_folder)
        try:
            case = load_case_from_folders(demo_folder, fault_folder)
            trace_str = json.dumps(case["diagnostic_trace"], ensure_ascii=False, indent=2)
            result_str = json.dumps(case["fault_result"], ensure_ascii=False, indent=2)
            block = """
# Fault Diagnosis Case {idx}:
[Diagnosis Steps]
{trace}

【Diagnosis Results】
{result}
""".format(idx=i, trace=trace_str, result=result_str)
            icl_blocks.append(block)
            print(f"✅ Loaded case: {name}")
        except Exception as e:
            print(f"❌ Failed to load case '{name}': {e}")

    icl_context = "\n".join(icl_blocks)

    agent_prompt = f"""
You are a professional Kubernetes operations engineer with extensive experience in systematic troubleshooting. 
**Your Goal:** Diagnose the root cause of the reported issue based on factual evidence collected from the system.

**Instructions:**
1. You have access to a set of diagnostic tools. You must independently decide which tools to use and the execution order based on your findings.
2. Do NOT guess or assume the system state. Every conclusion must be backed by concrete output from a tool.
3. If a tool returns no anomalies, discard that hypothesis and pivot to a different investigation path. Do not speculate without proof.
4. Provide a clear reasoning chain that connects the initial symptom to the final root cause, supported by the evidence you collected.

The similar cases below is ONLY for providing diagnostic ideas. The specific operations must be decided by YOU based on your available tools.
**Troubleshooting Guide:**
<icl_examples>
{icl_context}
</icl_examples>

**Important:**
### 1. Diagnostic Principles
- Even when all cluster services appear 'Running', it doesn't guarantee full health. You must dive deeper and collect internal failure evidence.
- Our scenario has one and only one fault. If you find multiple abnormal problems, please report only the most serious one.

### 2. Reasoning Style
- Limit your internal reasoning to few concise sentences. Then, IMMEDIATELY output the tool execution.
- Do not formulate long-term plans. Focus ONLY on the immediate next step.
- Find the root cause with the minimum number of steps.

### 3. Output Format
- Before all the diagnostic steps are completed, only the tool call format is allowed, the final answer format is absolutely prohibited.
- The final answer format is allowed only after you have clearly found the root cause of all abnormal Pods through multiple rounds of tool calls.
- The two formats cannot be nested, and the tool call results cannot be placed in Final Answer.

**CRITICAL SYNTAX RULES:**
1. **Empty Parameters:** If a tool (like `GetClusterConfiguration` or `GetAlerts`) does not require any parameters, you **MUST** provide an empty JSON dictionary as the input.
   * **CORRECT:**
     Action: GetClusterConfiguration
     Action Input: {{}}

2. The "Action Input" field is mandatory for every tool call.

IMPORTANT: When classifying the fault stage, you MUST strictly follow this definition in [List A: Valid Taxonomies]

Begin your investigation now.
""".strip()

    return agent_prompt
