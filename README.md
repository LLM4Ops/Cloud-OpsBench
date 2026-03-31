**Cloud-OpsBench** is a benchmark for **agentic root cause analysis (RCA)** in Kubernetes-based cloud systems. It is built around a state snapshot paradigm: instead of requiring a live cluster, each fault case stores the cluster state, alerts, logs, and tool cache needed for deterministic diagnosis and replay.

The current release covers **two microservice systems**, **49 fault types**, and **656 fault cases**:

- **Online Boutique**: 452 cases
- **Train-Ticket**: 204 cases

![Overview of Cloud-OpsBench](https://github.com/LLM4Ops/Cloud-OpsBench/blob/main/resource/overview.png)

## Key Features

- **Agentic RCA benchmark**: designed for multi-step diagnosis with tool use, not static classification.
- **Deterministic replay**: each case is stored as an immutable snapshot.
- **Full-stack fault coverage**: includes admission, scheduling, startup, runtime, service routing, performance, and infrastructure faults.
- **Trajectory supervision**: provides expert-style diagnostic trajectories in `golden-trajectory/`.

## Repository Layout

```text
Cloud-OpsBench/
├── benchmark/
│   ├── boutique/
│   └── trainticket/
├── golden-trajectory/
│   ├── boutique/
│   └── trainticket/
├── cloudops_agent/
└── resource/
```

## Dataset Statistics

### By System

| System | Categories | Cases |
| :--- | :--- | ---: |
| Online Boutique | admission, scheduling, startup, runtime, service, performance, infrastructure | 452 |
| Train-Ticket | startup, runtime, service, performance | 204 |
| Total | 49 fault types | 656 |



## Fault Taxonomy

The benchmark currently contains **49 distinct fault types** across **656 cases**.

| Fault Category | Mechanism Description | Specific Fault Types | Difficulty | Cases |
| :--- | :--- | :--- | :--- | ---: |
| Admission Control | Requests rejected by API server due to quota or permission violations. | `NamespaceCPUQuotaExceeded`, `NamespaceMemoryQuotaExceeded`, `NamespacePodQuotaExceeded`, `NamespaceServiceQuotaExceeded`, `NamespaceStorageQuotaExceeded`, `MissingServiceAccount` | Hard | 58 |
| Scheduling | Pods stay Pending due to unsatisfied node constraints or affinity rules. | `NodeCordonMismatch`, `NodeAffinityMismatch`, `NodeSelectorMismatch`, `PodAntiAffinityConflict`, `TaintTolerationMismatch`, `CPUCapacityMismatch`, `MemroyCapacityMismatch`, `PVBindingOccupied`, `PVCSelectorMismatch`, `PVCStorageClassMismatch`, `PVCCapacityMismatch`, `PVCAccessModeMismatch` | Medium | 164 |
| Startup | Pod creation fails. | `VolumeMountPermissionDenied`, `MissingSecretBinding`, `IncorrectImageReference`, `ImageRegistryDNSFailure`, `MissingImagePullSecret` | Easy | 86 |
| Runtime | Application crashes or fails health probes during execution. | `OOMKilled`, `LivenessProbeIncorrectProtocol`, `LivenessProbeIncorrectPort`, `LivenessProbeIncorrectTiming`, `ReadinessProbeIncorrectProtocol`, `ReadinessProbeIncorrectPort`, `ServiceSidecarPortConflict`, `MysqlInvalidCredentials`, `MysqlInvalidPort`, `DBReadOnly`, `DBConnectionExhaustion`, `DeploymentZeroReplicas` | Easy | 141 |
| Service Routing | Traffic routing failures between internal components. | `ServiceSelectorMismatch`, `ServicePortMappingMismatch`, `ServiceProtocolMismatch`, `ServiceEnvVarAddressMismatch`, `GatewayMisroute`, `ServiceDNSResolutionFailure` | Medium | 91 |
| Performance | Performance degradation due to saturation. | `PodCPUOverload`, `PodNetworkDelay` | Hard | 68 |
| Infrastructure | Outages in underlying cluster control plane or node components. | `ContainerdUnavailable`, `KubeletUnavailable`, `KubeProxyUnavailable`, `KubeSchedulerUnavailable`, `NodeNetworkDelay`, `NodeNetworkPacketLoss` | Hard | 48 |
| Total | - | 49 distinct fault types | - | 656 |

## Benchmark File Structure

Each fault case in `benchmark/` uses a consistent directory layout.

### Standard Case Layout

```text
benchmark/<system>/<fault_category>/<case_id>/
├── metadata.json
├── tool_cache.json
└── raw_data/
    ├── alert.json
    ├── k8s_states.json
    ├── logs.json
    └── metrics.csv
```

### What These Files Mean

- `metadata.json`: fault label, namespace, query, and ground-truth diagnosis.
- `tool_cache.json`: cached outputs used to simulate diagnostic tools deterministically.
- `raw_data/k8s_states.json`: Kubernetes object snapshots.
- `raw_data/logs.json`: service and container logs.
- `raw_data/alert.json`: alert and anomaly signals from adnormal metrics and requests.
- `raw_data/metrics.csv`: time-series metrics for performance cases only.

Not every case contains `metrics.csv`. Some faults occur in the early Pod lifecycle before the workload enters the running stage and before user traffic or load arrives, so no runtime performance metrics are generated for those cases.

## Golden Trajectory Structure

`golden-trajectory/` stores expert diagnostic trajectories aligned to benchmark cases.

Example directory:

```text
golden-trajectory/<system>/<fault_category>/<case_id>/
├── path1.json
└── path2.json
```

This means a single benchmark case may provide multiple expert reasoning paths.

### 📽️ An Easy Demo  
**Cloud-OpsBench** is easy to use, you do not need to deploy your cloud environment. We provide a demo that you can directly interact with fault cases in Cloud-OpsBench for diagnosis. We provide an [video link ▶️](https://www.youtube.com/watch?v=lVd0f-24T8o) to show.
```bash
python interact.py
```

## Running the ReAct Agent

The repository includes a lightweight ReAct-style diagnostic agent under `cloudops_agent/`.

### 1. Configure the Agent

Edit:

```text
cloudops_agent/configs/model_configs.yaml
```

Minimal fields to set:

```yaml
model:
  model: "your-model-name"
  provider: openai_compatible
  api_base: "your-api-base"
  api_key: "your-api-key"
  temperature: 0
  max_tokens: 4096
  timeout: 60

diagnosis:
  max_iterations: 20
  system: "trainticket"   # or "boutique"
  fault_category: "service"
  dataset_root: "/absolute/path/to/Cloud-OpsBench"
  save_root: "/absolute/path/to/save/results"
  prompt_strategy: "base" # ["base", "icl", "cot", "rag"]
  # case_name: "1"        # optional: run a single case
```

Notes:

- `dataset_root` should point to the root of this repository, i.e. the directory containing `benchmark/` and `golden-trajectory/`.
- `save_root` is where generated trajectories and diagnosis results will be written.
- If `case_name` is left unset, the agent will run all cases under the selected `system` and `fault_category`.

### 2. Run the Agent

```bash
cd cloudops_agent
python run.py
```

The agent will read `configs/model_configs.yaml`, load cases from `benchmark/<system>/<fault_category>/`, and save outputs under:

```text
<save_root>/<system>/<model_name>_<prompt_strategy>/<fault_category>/<case_id>/
```

### 3. Run the Evaluation

After running the agent, you can directly evaluate the generated trajectories and diagnosis results with:

```bash
cd cloudops_agent
python evaluation.py
```

`evaluation.py` reads the same `configs/model_configs.yaml`, automatically locates the corresponding benchmark cases and generated outputs, and then reports the evaluation metrics.

## Supported Diagnostic Tools

Cloud-OpsBench provides a set of diagnostic tools for interactive RCA.

| Category | Tool Name | Description |
| :--- | :--- | :--- |
| Resource Inspection | `GetResources` | Lists Kubernetes resources and current status details. |
| Resource Inspection | `DescribeResource` | Retrieves events, conditions, and detailed runtime state for one resource. |
| Resource Inspection | `GetAppYAML` | Returns the YAML configuration of an application service. |
| Service Interaction | `GetServiceDependencies` | Returns upstream and downstream service dependencies. |
| Service Interaction | `CheckServiceConnectivity` | Checks in-cluster TCP connectivity to a target service port. |
| Telemetry Analysis | `GetAlerts` | Retrieves current alert signals and abnormal metric summaries. |
| Telemetry Analysis | `GetRecentLogs` | Returns recent raw logs for a service. |
| Telemetry Analysis | `GetErrorLogs` | Returns grouped error-log summaries. |
| Infra Diagnostics | `GetClusterConfiguration` | Returns cluster-wide node and configuration state. |
| Infra Diagnostics | `CheckNodeServiceStatus` | Checks infrastructure component status on a node. |

## Experimental Results

The following tables are taken from `/root/k8srca/table3.tex` and report outcome and process metrics by system.

### Boutique

| Model | A@1 | A@3 | TCR | Exact | InO. | AnyO. | Rel. | Cov. | Steps | IAC | MTTI | RAR |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen3-235B | 0.54 | 0.70 | 0.96 | 0.13 | 0.38 | 0.41 | 0.55 | 0.67 | 5.34 | 0.03 | 32.38 | 0.06 |
| DeepSeek-V3.2 | 0.73 | 0.79 | 0.99 | 0.00 | 0.53 | 0.63 | 0.43 | 0.88 | 10.00 | 0.00 | 85.78 | 0.11 |
| GPT-5 | 0.67 | 0.75 | 0.99 | 0.16 | 0.38 | 0.48 | 0.65 | 0.77 | 5.57 | 0.00 | 73.06 | 0.05 |
| GPT-4o | 0.51 | 0.57 | 0.99 | 0.14 | 0.45 | 0.46 | 0.63 | 0.78 | 5.67 | 0.00 | 20.17 | 0.02 |
| Claude-4-Sonnet | 0.54 | 0.59 | 0.98 | 0.05 | 0.24 | 0.25 | 0.46 | 0.52 | 4.25 | 0.02 | 41.53 | 0.05 |
| Qwen3-14B | 0.34 | 0.43 | 0.82 | 0.04 | 0.31 | 0.42 | 0.63 | 0.71 | 5.82 | 0.04 | 46.42 | 0.10 |
| Qwen3-8B | 0.21 | 0.23 | 0.92 | 0.01 | 0.15 | 0.20 | 0.36 | 0.47 | 5.46 | 0.10 | 31.42 | 0.16 |

### Train-Ticket

| Model | A@1 | A@3 | TCR | Exact | InO. | AnyO. | Rel. | Cov. | Steps | IAC | MTTI | RAR |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen3-235B | 0.25 | 0.30 | 0.99 | 0.00 | 0.02 | 0.02 | 0.38 | 0.47 | 7.69 | 0.00 | 46.14 | 0.06 |
| DeepSeek-V3.2 | 0.54 | 0.58 | 0.88 | 0.00 | 0.08 | 0.14 | 0.41 | 0.68 | 11.02 | 0.00 | 85.93 | 0.07 |
| GPT-5 | 0.57 | 0.59 | 0.95 | 0.00 | 0.02 | 0.04 | 0.71 | 0.58 | 6.08 | 0.00 | 71.56 | 0.03 |
| GPT-4o | 0.43 | 0.45 | 0.94 | 0.00 | 0.01 | 0.03 | 0.68 | 0.54 | 5.88 | 0.00 | 26.48 | 0.04 |
| Claude-4-Sonnet | 0.58 | 0.60 | 0.98 | 0.00 | 0.00 | 0.00 | 0.59 | 0.57 | 6.60 | 0.00 | 58.62 | 0.06 |
| Qwen3-14B | 0.25 | 0.29 | 0.71 | 0.00 | 0.06 | 0.10 | 0.40 | 0.57 | 14.15 | 0.03 | 102.59 | 0.34 |
| Qwen3-8B | 0.26 | 0.29 | 0.89 | 0.00 | 0.02 | 0.02 | 0.45 | 0.54 | 10.61 | 0.01 | 55.50 | 0.27 |

### Metrics

- `A@1`, `A@3`: Top-1 / Top-3 diagnosis accuracy.
- `TCR`: task completion rate.
- `Exact`, `InO.`, `AnyO.`: trajectory alignment with expert reasoning.
- `Rel.`, `Cov.`: tool-use relevance and coverage.
- `Steps`, `IAC`, `MTTI`, `RAR`: efficiency and interaction quality metrics.
