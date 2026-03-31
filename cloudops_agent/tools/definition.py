from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable, Optional, Type, Literal, List

from pydantic import BaseModel, Field

from .implement import KubernetesTools, SYSTEM_CONFIG

ClusterScopeResource = {
    "nodes",
    "node",
    "persistentvolumes",
    "pv",
    "persistentvolume",
    "storageclasses",
    "sc",
    "storageclass",
    "namespaces",
    "namespace",
    "ns",
}

NodeName = Literal["master", "worker-01", "worker-02", "worker-03"]
SystemServiceName = Literal["kube-scheduler", "kubelet", "kube-proxy", "containerd"]
YAML_SNAPSHOT_RESOURCES = {
    "deployments",
    "statefulsets",
    "services",
    "configmaps",
    "secrets",
    "ingresses",
    "networkpolicies",
    "serviceaccounts",
}


@dataclass
class SimpleTool:
    """
    Lightweight tool wrapper used by the custom single-agent runtime.

    Required interface:
    - name: tool name
    - description: tool description for prompts
    - _run(**kwargs): callable execution entrypoint

    args_schema is kept as metadata for future use (validation / docs),
    but the current runtime does not depend on it.
    """
    name: str
    description: str
    run_fn: Callable
    args_schema: Optional[Type[BaseModel]] = None

    def _run(self, **kwargs) -> str:
        return self.run_fn(**kwargs)


def create_k8s_tools(case_path: str, system: str = "boutique") -> List[SimpleTool]:
    """
    Create all Cloud-OpsBench diagnostic tools for a given case snapshot.

    Args:
        case_path: Path to the stored fault snapshot.

    Returns:
        A list of SimpleTool objects.
    """
    if not os.path.exists(case_path):
        raise FileNotFoundError(f"Snapshot file not found: {case_path}")

    system_key = system if system in SYSTEM_CONFIG else "boutique"
    system_config = SYSTEM_CONFIG[system_key]
    default_namespace = system_config["default_namespace"]
    app_services = ", ".join(system_config["app_services"])
    log_services = ", ".join(system_config["log_services"])
    connectivity_services = ", ".join(system_config["connectivity_services"])

    k8s_tools_instance = KubernetesTools(
        case_path=case_path,
        system=system_key,
        namespace=default_namespace,
    )

    # ------------------------------------------------------------------
    # Input Schemas
    # ------------------------------------------------------------------

    class GetResourcesInput(BaseModel):
        resource_type: str = Field(
            description="**REQUIRED**. The type of resource to list. (e.g., 'pods', 'services', 'deployments', 'nodes')."
        )
        namespace: Optional[str] = Field(
            default=None,
            description=(
                "The Kubernetes namespace to query. "
                "**CRITICAL**: If the `resource_type` is a namespaced resource (e.g., 'pods', 'deployments', 'services'), "
                f"you MUST provide the namespace (default is '{default_namespace}'). "
                "However, if the `resource_type` is a cluster-scoped resource (e.g., 'nodes', 'persistentvolumes'), "
                "you may omit the `namespace` parameter; the tool will automatically handle historical cache formats."
            ),
        )
        name: Optional[str] = Field(
            default=None,
            description="Optional. The specific name of the resource to retrieve a single item. If omitted, returns a list.",
        )
        show_labels: bool = Field(
            default=False,
            description="If True, adds `--show-labels`. MUTUALLY EXCLUSIVE with `output_wide`.",
        )
        output_wide: bool = Field(
            default=False,
            description="If True, adds `-o wide`. MUTUALLY EXCLUSIVE with `show_labels`.",
        )
        label_selector: Optional[str] = Field(
            default=None,
            description=(
                "Filter by label (e.g., 'app=frontend'). "
                "Can be combined with `show_labels` or `output_wide`. "
                "Only simple selectors in the form `key=value` are supported. "
                "SUPPORTED ONLY FOR: pods, services, deployments, PVCs."
            ),
        )

    class GetResourcesV2Input(BaseModel):
        resource_type: str = Field(
            description="**REQUIRED**. The type of resource to list. (e.g., 'pods', 'services', 'deployments', 'nodes')."
        )
        namespace: Optional[str] = Field(
            default=None,
            description=(
                "The Kubernetes namespace to query. "
                "**CRITICAL**: If the `resource_type` is a namespaced resource (e.g., 'pods', 'deployments', 'services'), "
                f"you MUST provide the namespace (default is '{default_namespace}'). "
                "However, if the `resource_type` is a cluster-scoped resource (e.g., 'nodes', 'persistentvolumes'), "
                "you may omit the `namespace` parameter; the tool will automatically handle historical cache formats."
            ),
        )
        name: Optional[str] = Field(
            default=None,
            description="Optional. The specific name of the resource to retrieve a single item. If omitted, returns a list.",
        )
        show_labels: bool = Field(
            default=False,
            description="If True, adds `--show-labels`. MUTUALLY EXCLUSIVE with `output_wide`.",
        )
        output_wide: bool = Field(
            default=False,
            description="If True, adds `-o wide`. MUTUALLY EXCLUSIVE with `show_labels`.",
        )
        output_yaml: bool = Field(
            default=False,
            description=(
                "If True, returns the YAML snapshot for exactly one named resource, similar to "
                "`kubectl get <resource_type> <name> -o yaml`. Supported only for: deployments, "
                "statefulsets, services, configmaps, secrets, ingresses, networkpolicies, and "
                "serviceaccounts. Not supported for list queries."
            ),
        )

    class DescribeResourceInput(BaseModel):
        resource_type: str = Field(
            description="**REQUIRED**. The type of resource to describe (e.g., 'pod', 'node', 'service', 'pvc')."
        )
        name: str = Field(
            description="**REQUIRED**. The EXACT name of the specific resource to inspect."
        )
        namespace: Optional[str] = Field(
            default=None,
            description=(
                "The Kubernetes namespace to query. "
                "If resource is namespaced, provide namespace. "
                "If cluster-scoped, you may omit namespace; the tool will automatically handle historical cache formats."
            ),
        )

    class GetAppYAMLInput(BaseModel):
        app_name: str = Field(
            description=f"**REQUIRED**. The name of the microservice to inspect. Allowed for {system_key}: {app_services}."
        )

    class GetRecentLogsInput(BaseModel):
        namespace: str = Field(description="**REQUIRED**. The Kubernetes namespace.")
        service_name: str = Field(
            description=f"**REQUIRED**. The microservice name, not the full pod name. Allowed for {system_key}: {log_services}."
        )

    class GetErrorLogsInput(BaseModel):
        namespace: str = Field(description="**REQUIRED**. The Kubernetes namespace.")
        service_name: str = Field(
            description=f"**REQUIRED**. The microservice name. Allowed for {system_key}: {log_services}."
        )

    class CheckServiceConnectivityInput(BaseModel):
        service_name: str = Field(
            description=f"**REQUIRED**. The target Service DNS name. Allowed for {system_key}: {connectivity_services}."
        )
        port: int = Field(
            description="**REQUIRED**. The target TCP port number."
        )
        namespace: str = Field(description="**REQUIRED**. The Kubernetes namespace.")

    class GetServiceDependenciesInput(BaseModel):
        service_name: str = Field(
            description=f"**REQUIRED**. The name of the service. Allowed for {system_key}: {app_services}."
        )

    class CheckNodeServiceStatusInput(BaseModel):
        node_name: NodeName = Field(
            description="**REQUIRED**. The target Node Name."
        )
        service_name: SystemServiceName = Field(
            description="**REQUIRED**. The system component name to inspect."
        )

    # ------------------------------------------------------------------
    # Tool Run Functions
    # ------------------------------------------------------------------

    def run_get_resources(
        resource_type: str,
        namespace: Optional[str] = None,
        name: Optional[str] = None,
        show_labels: bool = False,
        output_wide: bool = False,
        label_selector: Optional[str] = None,
    ) -> str:
        try:
            resource_type_key = (resource_type or "").lower()
            if resource_type_key in ClusterScopeResource:
                default_namespace = None
            else:
                default_namespace = namespace

            return k8s_tools_instance.GetResources(
                resource_type=resource_type,
                namespace=default_namespace,
                name=name,
                show_labels=show_labels,
                output_wide=output_wide,
                label_selector=label_selector,
            )
        except ValueError as e:
            return f"Error: {e}"

    def run_get_resources_v2(
        resource_type: str,
        namespace: Optional[str] = None,
        name: Optional[str] = None,
        show_labels: bool = False,
        output_wide: bool = False,
        output_yaml: bool = False,
    ) -> str:
        try:
            resource_type_key = (resource_type or "").lower()
            if resource_type_key in ClusterScopeResource:
                default_namespace = None
            else:
                default_namespace = namespace

            return k8s_tools_instance.GetResources_v2(
                resource_type=resource_type,
                namespace=default_namespace,
                name=name,
                show_labels=show_labels,
                output_wide=output_wide,
                output_yaml=output_yaml,
            )
        except ValueError as e:
            return f"Error: {e}"

    def run_describe_resource(
        resource_type: str,
        name: str,
        namespace: Optional[str] = None,
    ) -> str:
        try:
            resource_type_key = (resource_type or "").lower()
            if resource_type_key in ClusterScopeResource:
                default_namespace = None
            else:
                default_namespace = namespace

            return k8s_tools_instance.DescribeResource(
                resource_type=resource_type,
                name=name,
                namespace=default_namespace,
            )
        except ValueError as e:
            return f"Error: {e}"

    def run_get_app_yaml(app_name: str) -> str:
        try:
            validated_input = GetAppYAMLInput(app_name=app_name)
            return k8s_tools_instance.GetAppYAML(app_name=validated_input.app_name)
        except (ValueError, FileNotFoundError) as e:
            return f"Error: {e}"

    def run_get_recent_logs(namespace: str, service_name: str) -> str:
        try:
            validated_input = GetRecentLogsInput(
                namespace=namespace,
                service_name=service_name,
            )
            return k8s_tools_instance.GetRecentLogs(
                namespace=validated_input.namespace,
                service_name=validated_input.service_name,
            )
        except ValueError as e:
            return f"Error: {e}"

    def run_get_error_logs(namespace: str, service_name: str) -> str:
        try:
            validated_input = GetErrorLogsInput(
                namespace=namespace,
                service_name=service_name,
            )
            return k8s_tools_instance.GetErrorLogs(
                namespace=validated_input.namespace,
                service_name=validated_input.service_name,
            )
        except ValueError as e:
            return f"Error: {e}"

    def run_check_service_connectivity(
        service_name: str,
        port: int,
        namespace: str,
    ) -> str:
        try:
            validated_input = CheckServiceConnectivityInput(
                service_name=service_name,
                port=port,
                namespace=namespace,
            )
            return k8s_tools_instance.CheckServiceConnectivity(
                service_name=validated_input.service_name,
                port=validated_input.port,
                namespace=validated_input.namespace,
            )
        except ValueError as e:
            return f"Error: {e}"

    def run_get_service_dependencies(service_name: str) -> str:
        try:
            validated_input = GetServiceDependenciesInput(service_name=service_name)
            return k8s_tools_instance.GetServiceDependencies(validated_input.service_name)
        except ValueError as e:
            return f"Error: {e}"

    def run_get_cluster_configuration() -> str:
        try:
            return k8s_tools_instance.GetClusterConfiguration()
        except Exception as e:
            return f"Error: {e}"

    def run_get_alerts() -> str:
        try:
            return k8s_tools_instance.GetAlerts()
        except Exception as e:
            return f"Error: {e}"

    def run_check_node_service_status(node_name: str, service_name: str) -> str:
        try:
            validated_input = CheckNodeServiceStatusInput(
                node_name=node_name,
                service_name=service_name,
            )
            return k8s_tools_instance.CheckNodeServiceStatus(
                validated_input.node_name,
                validated_input.service_name,
            )
        except Exception as e:
            return f"Error: {e}"

    # ------------------------------------------------------------------
    # Tool List
    # ------------------------------------------------------------------
    use_get_resources_v2 = system_key == "train-ticket"

    tools_list: List[SimpleTool] = [
        SimpleTool(
            name="GetResources",
            description=(
                "Simulates `kubectl get` to retrieve resource lists or current status details. "
                + (
                    "It supports `output_yaml=true` only for a single named resource of these types: deployments, "
                    "statefulsets, services, configmaps, secrets, ingresses, networkpolicies, and "
                    "serviceaccounts. "
                    if use_get_resources_v2
                    else "IMPORTANT: `show_labels` and `output_wide` are mutually exclusive. `label_selector` may be combined with either of them. "
                )
                + "`show_labels` and `output_wide` are mutually exclusive."
            ),
            run_fn=run_get_resources_v2 if use_get_resources_v2 else run_get_resources,
            args_schema=GetResourcesV2Input if use_get_resources_v2 else GetResourcesInput,
        ),
        SimpleTool(
            name="DescribeResource",
            description=(
                "Simulates `kubectl describe`. Retrieves detailed state, events, and conditions "
                "for a specific Kubernetes resource."
            ),
            run_fn=run_describe_resource,
            args_schema=DescribeResourceInput,
        ),
        SimpleTool(
            name="GetAppYAML",
            description=(
                "Retrieves the raw YAML configuration file for a specific service. "
                "Returns static configuration details including resource limits, probes, env vars, and image tags."
            ),
            run_fn=run_get_app_yaml,
            args_schema=GetAppYAMLInput,
        ),
        SimpleTool(
            name="GetRecentLogs",
            description=(
                "Retrieves raw recent container logs for a specified Kubernetes service."
            ),
            run_fn=run_get_recent_logs,
            args_schema=GetRecentLogsInput,
        ),
        SimpleTool(
            name="GetErrorLogs",
            description=(
                "Retrieves a statistical summary of application error logs grouped by error patterns "
                "for a specified Kubernetes service."
            ),
            run_fn=run_get_error_logs,
            args_schema=GetErrorLogsInput,
        ),
        SimpleTool(
            name="CheckServiceConnectivity",
            description=(
                "Performs an active TCP connectivity check to the target service port from within the cluster. "
                "This tool can ONLY check internal cluster connectivity between the predefined microservices. "
                "It CANNOT check external DNS or external image registry connectivity."
            ),
            run_fn=run_check_service_connectivity,
            args_schema=CheckServiceConnectivityInput,
        ),
        SimpleTool(
            name="GetServiceDependencies",
            description=(
                "Retrieves the service network topology, showing upstream and downstream communication relationships "
                "for a given service."
            ),
            run_fn=run_get_service_dependencies,
            args_schema=GetServiceDependenciesInput,
        ),
        SimpleTool(
            name="GetClusterConfiguration",
            description=(
                "Retrieves a holistic health and configuration summary of all nodes in the cluster, "
                "including taints, conditions, allocatable resources, and labels."
            ),
            run_fn=run_get_cluster_configuration,
            args_schema=None,
        ),
        SimpleTool(
            name="GetAlerts",
            description=(
                "Retrieves active system alerts triggered by metric anomalies such as high latency, "
                "error rate spikes, or CPU/Memory saturation."
            ),
            run_fn=run_get_alerts,
            args_schema=None,
        ),
        SimpleTool(
            name="CheckNodeServiceStatus",
            description=(
                "Checks the operating status of critical Kubernetes infrastructure components "
                "on a specific node, such as kubelet, kube-proxy, and containerd."
            ),
            run_fn=run_check_node_service_status,
            args_schema=CheckNodeServiceStatusInput,
        ),
    ]

    return tools_list
