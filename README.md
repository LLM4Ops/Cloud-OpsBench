**Cloud-OpsBench** is a benchmark for **agentic root cause analysis (RCA)** in Kubernetes-based cloud systems. It is built around a state snapshot paradigm: instead of requiring a live cluster, each fault case stores the cluster state, alerts, logs, and tool cache needed for deterministic diagnosis and replay.

The current release covers **two microservice systems**, **57 fault types**, and **754 fault cases**:

- **Online Boutique**: 550 cases
- **Train-Ticket**: 204 cases

![Overview of Cloud-OpsBench](https://github.com/LLM4Ops/Cloud-OpsBench/blob/main/resource/overview_new.png)

## Key Features

- **Agentic RCA benchmark**: designed for multi-step diagnosis with tool use, not static classification.
- **No live cluster required**: benchmark cases can be run directly from the released artifacts without deploying Kubernetes clusters or microservice systems.
- **Deterministic replay**: each case is stored as an immutable snapshot, avoiding runtime system noise and preserving faithful diagnostic results across repeated runs.
- **Full-stack fault coverage**: includes admission, scheduling, startup, runtime, service routing, performance, and infrastructure faults.
- **Milestone-based process evaluation**: evaluates whether an agent acquires the required diagnostic evidence through `process-label/` annotations.

## Ecosystem Adoption & Recognition

- **[OpenSRE](https://www.opensre.com/docs/cloudopsbench)** — Officially integrates Cloud-OpsBench for reproducible SRE-agent evaluation and publishes benchmark results in its [showcase](https://www.opensre.com/docs/showcase#put-it-through-cloudopsbench).
- **[Alibaba Cloud STAROps](https://sls.aliyun.com/doc/starops/benchmark/rca/rca_benchmark_dataset.html)** — References Cloud-OpsBench as a representative benchmark for Agentic RCA.
- **[Jaeger](https://github.com/jaegertracing/jaeger/issues/9135)** — References Cloud-OpsBench as an academic RCA benchmark informing evaluation of the Jaeger AI Assistant.

## Repository Layout

```text
Cloud-OpsBench/
├── benchmark/
│   ├── boutique/
│   └── trainticket/
├── process-label/
│   ├── boutique/
│   └── trainticket/
├── golden-trajectory/
│   ├── boutique/
│   └── trainticket/
├── cloudops_agent/
│   └── evaluation_utils/
└── resource/
```

## Dataset Statistics

### By System

| System | Categories | Cases |
| :--- | :--- | ---: |
| Online Boutique | admission, scheduling, startup, runtime, service, performance, infrastructure, code defect | 550 |
| Train-Ticket | startup, runtime, service, performance | 204 |
| Total | 57 fault types | 754 |

## Updates

Cloud-OpsBench is actively maintained, and we will continue adding new fault scenarios and updating released cases.

- **2026-07-16**: Released milestone-based process annotations and updated the evaluation metrics for diagnostic process quality.
- **2026-05-22**: Added 8 application code defect faults with 98 new cases for Online Boutique.

## Fault Taxonomy

The benchmark currently contains **57 distinct fault types** across **754 cases**.

| Fault Category | Mechanism Description | Specific Fault Types | Difficulty | Cases |
| :--- | :--- | :--- | :--- | ---: |
| Admission Control | Requests rejected by API server due to quota or permission violations. | `NamespaceCPUQuotaExceeded`, `NamespaceMemoryQuotaExceeded`, `NamespacePodQuotaExceeded`, `NamespaceServiceQuotaExceeded`, `NamespaceStorageQuotaExceeded`, `MissingServiceAccount` | Medium | 58 |
| Scheduling | Pods stay Pending due to unsatisfied node constraints or affinity rules. | `NodeCordonMismatch`, `NodeAffinityMismatch`, `NodeSelectorMismatch`, `PodAntiAffinityConflict`, `TaintTolerationMismatch`, `CPUCapacityMismatch`, `MemoryCapacityMismatch`, `PVBindingOccupied`, `PVCSelectorMismatch`, `PVCStorageClassMismatch`, `PVCCapacityMismatch`, `PVCAccessModeMismatch` | Easy | 164 |
| Startup | Pod creation fails. | `VolumeMountPermissionDenied`, `MissingSecretBinding`, `IncorrectImageReference`, `ImageRegistryDNSFailure`, `MissingImagePullSecret` | Easy | 86 |
| Runtime | Application crashes or fails health probes during execution. | `ContainerMemoryLimitTooLow`, `LivenessProbeIncorrectProtocol`, `LivenessProbeIncorrectPort`, `LivenessProbeIncorrectTiming`, `ReadinessProbeIncorrectProtocol`, `ReadinessProbeIncorrectPort`, `ServiceSidecarPortConflict`, `MysqlInvalidCredentials`, `MysqlInvalidPort`, `DBReadOnly`, `DBConnectionExhaustion`, `DeploymentZeroReplicas` | Easy | 141 |
| Service Routing | Traffic routing failures between internal components. | `ServiceSelectorMismatch`, `ServicePortMappingMismatch`, `ServiceProtocolMismatch`, `ServiceEnvVarAddressMismatch`, `GatewayMisroute`, `ServiceDNSResolutionFailure` | Medium | 91 |
| Performance | Performance degradation due to saturation or network drops. | `PodCPUOverload`, `PodNetworkDelay`, `NodeNetworkDelay`, `NodeNetworkPacketLoss` | Hard | 76 |
| Infrastructure | Outages in underlying cluster control plane or components. | `ContainerdUnavailable`, `KubeletUnavailable`, `KubeProxyUnavailable`, `KubeSchedulerUnavailable` | Medium | 40 |
| Application Code Defect | Application-level code defects in key business logic. | `CodeMissingParameter`, `CodeBusyLoop`, `CodeExcessiveFileReads`, `CodeWrongReturn`, `CodeExcessiveFileWrites`, `CodeWrongArgumentOrder`, `CodeArtificialDelay`, `CodeMemoryLeak` | Hard | 98 |
| Total | - | 57 distinct fault types | - | 754 |

## Benchmark File Structure

Each fault case in `benchmark/` uses a consistent directory layout.

### Standard Case Layout

```text
benchmark/<system>/<fault_category>/<case_id>/
├── metadata.json
├── tool_cache.json
├── code/
└── raw_data/
    ├── alert.json
    ├── k8s_states.json
    ├── logs.json
    └── metrics.csv
```

### What These Files Mean

- `metadata.json`: fault label, namespace, query, difficulty, and ground-truth diagnosis.
- `tool_cache.json`: cached outputs used to simulate diagnostic tools deterministically.
- `code/`: trimmed core business source files for code-level diagnosis. This is implemented for Online Boutique, while Train-Ticket cases do not currently include this field.
- `raw_data/k8s_states.json`: Kubernetes object snapshots.
- `raw_data/logs.json`: service and container logs.
- `raw_data/alert.json`: alert and anomaly signals from adnormal metrics and requests.
- `raw_data/metrics.csv`: time-series metrics.

Not every case contains `metrics.csv`. Some faults occur in the early Pod lifecycle before the workload enters the running stage and before user traffic or load arrives, so no runtime performance metrics are generated for those cases.

## Process Label Structure

`process-label/` stores the milestone-based process annotations used by the current evaluation protocol.

Example directory:

```text
process-label/<system>/<fault_category>/<case_id>/
└── milestone.json
```

Each file specifies the diagnostic milestones, admissible supporting evidence, and any required ordering between milestones. An agent receives process credit by establishing the corresponding milestones during its diagnostic trajectory.

The matching and process-scoring implementation is provided in `cloudops_agent/evaluation_utils/`.

## Auxiliary Expert Trajectories

`golden-trajectory/` contains two golden diagnostic trajectories for each benchmark case:

```text
golden-trajectory/<system>/<fault_category>/<case_id>/
├── path1.json
└── path2.json
```

These trajectories are not used by the current milestone-based process evaluation. We retain them as an auxiliary research resource for applications such as supervised fine-tuning(SFT) and diagnostic trajectory analysis.

### 📽️ An Easy Demo  
We provide a demo that you can directly interact with fault cases in Cloud-OpsBench for diagnosis. We provide an [video link ▶️](https://www.youtube.com/watch?v=lVd0f-24T8o) to show.
```bash
python interact.py
```

## Running the ReAct Agent

The repository includes a lightweight ReAct-style diagnostic agent under `cloudops_agent/`. It provides a single base prompt; researchers can define and integrate their own prompting methods as needed.

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
  # case_name: "1"        # optional: run a single case
```

Notes:

- `dataset_root` should point to the root of this repository. `benchmark/` contains the fault cases, `process-label/` contains the current process-evaluation annotations, and `golden-trajectory/` is retained as an optional research resource.
- `save_root` is where generated trajectories and diagnosis results will be written.
- If `case_name` is left unset, the agent will run all cases under the selected `system` and `fault_category`.

### 2. Run the Agent

```bash
cd cloudops_agent
python run.py
```

The agent will read `configs/model_configs.yaml`, load cases from `benchmark/<system>/<fault_category>/`, and save outputs under:

```text
<save_root>/<system>/<model_name>/<fault_category>/<case_id>/
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
| Code Inspection | `ListCodeFiles` | Lists available source files for an application service and their brief descriptions. |
| Code Inspection | `GetSourceCode` | Returns source code for a specific application file. |
| Infra Diagnostics | `GetClusterConfiguration` | Returns cluster-wide node and configuration state. |
| Infra Diagnostics | `CheckNodeServiceStatus` | Checks infrastructure component status on a node. |

## Experimental Results

The following tables report outcome correctness, process grounding, and diagnostic efficiency by system. Higher is better for `CA`, `FA`, `JRA`, `MC`, `EOC`, `ECR`, and `EE`; lower is better for `Steps` and `RAR`.

### OnlineBoutique

| Model | CA | FA | JRA | MC | EOC | ECR | EE | Steps | RAR |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| GPT-5 | 0.86 | 0.69 | 0.68 | 0.64 | 0.55 | 0.21 | 0.64 | 5.56 | 0.00 |
| Claude-Sonnet-4 | 0.71 | 0.56 | 0.52 | 0.61 | 0.54 | 0.44 | 0.44 | 6.04 | 0.00 |
| Gemini-2.5-Pro | 0.81 | 0.69 | 0.67 | 0.74 | 0.68 | 0.46 | 0.63 | 6.21 | 0.00 |
| Qwen3.5-Plus | 0.80 | 0.68 | 0.64 | 0.70 | 0.64 | 0.34 | 0.65 | 5.92 | 0.00 |
| Qwen3-235B-A22B | 0.61 | 0.46 | 0.40 | 0.56 | 0.48 | 0.34 | 0.36 | 7.03 | 0.01 |
| DeepSeek-V4-Flash | 0.88 | 0.77 | 0.76 | 0.74 | 0.64 | 0.38 | 0.62 | 6.45 | 0.00 |
| Gemini-2.5-Flash | 0.82 | 0.67 | 0.65 | 0.71 | 0.67 | 0.37 | 0.58 | 6.49 | 0.01 |
| Qwen3.5-27B | 0.85 | 0.71 | 0.70 | 0.75 | 0.70 | 0.43 | 0.54 | 6.87 | 0.01 |
| Qwen3-14B | 0.61 | 0.42 | 0.41 | 0.70 | 0.57 | 0.45 | 0.32 | 14.58 | 0.28 |
| Qwen3-8B | 0.35 | 0.19 | 0.19 | 0.58 | 0.40 | 0.16 | 0.37 | 16.01 | 0.46 |

### TrainTicket

| Model | CA | FA | JRA | MC | EOC | ECR | EE | Steps | RAR |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| GPT-5 | 0.70 | 0.71 | 0.68 | 0.61 | 0.53 | 0.15 | 0.64 | 7.03 | 0.00 |
| Claude-Sonnet-4 | 0.60 | 0.62 | 0.59 | 0.61 | 0.52 | 0.15 | 0.52 | 7.42 | 0.00 |
| Gemini-2.5-Pro | 0.62 | 0.61 | 0.58 | 0.58 | 0.51 | 0.14 | 0.51 | 7.13 | 0.00 |
| Qwen3.5-Plus | 0.67 | 0.79 | 0.64 | 0.64 | 0.58 | 0.25 | 0.63 | 5.90 | 0.00 |
| Qwen3-235B-A22B | 0.42 | 0.23 | 0.21 | 0.53 | 0.50 | 0.19 | 0.34 | 8.70 | 0.03 |
| DeepSeek-V4-Flash | 0.69 | 0.71 | 0.63 | 0.62 | 0.56 | 0.24 | 0.53 | 7.68 | 0.00 |
| Gemini-2.5-Flash | 0.60 | 0.55 | 0.53 | 0.45 | 0.42 | 0.12 | 0.48 | 4.91 | 0.00 |
| Qwen3.5-27B | 0.62 | 0.64 | 0.58 | 0.59 | 0.55 | 0.18 | 0.55 | 7.05 | 0.01 |
| Qwen3-14B | 0.41 | 0.25 | 0.24 | 0.60 | 0.52 | 0.20 | 0.37 | 14.53 | 0.31 |
| Qwen3-8B | 0.38 | 0.26 | 0.22 | 0.53 | 0.45 | 0.06 | 0.45 | 11.55 | 0.22 |

### Metrics

Cloud-OpsBench evaluates agents along three complementary dimensions:

- `CA` (Component Accuracy): whether the agent localizes the faulty component correctly.
- `FA` (Fault-Type Accuracy): whether the agent identifies the fault type correctly.
- `JRA` (Joint RCA Accuracy): whether both the faulty component and fault type are correct.
- `MC` (Milestone Coverage): the fraction of diagnostic milestone groups completed by the trajectory.
- `EOC` (Evidence-Order Consistency): the fraction of required milestone groups established in an admissible causal order.
- `ECR` (Evidence Closure Rate): a binary completeness indicator that equals 1 only when every required milestone group is completed.
- `EE` (Evidence Efficiency): the fraction of tool calls that contribute to admissible, dependency-grounded evidence.
- `Steps`: the total number of tool invocations.
- `RAR` (Redundant Action Rate): the fraction of repeated tool-and-argument calls that do not contribute new evidence or advance a new milestone group.
