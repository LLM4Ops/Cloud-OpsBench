import os
import json
from typing import Optional

BOUTIQUE = [
    "adservice",
    "cartservice",
    "checkoutservice",
    "currencyservice",
    "emailservice",
    "frontend",
    "paymentservice",
    "productcatalogservice",
    "recommendationservice",
    "redis-cart",
    "shippingservice",
]

TRAINTICKET = [
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
]

BOUTIQUE_LOG_SERVICES = BOUTIQUE
TRAINTICKET_LOG_SERVICES = TRAINTICKET + [
    "nacos",
    "nacosdb-mysql",
    "rabbitmq",
    "tsdb-mysql",
]

BOUTIQUE_CONNECTIVITY_SERVICES = BOUTIQUE
TRAINTICKET_CONNECTIVITY_SERVICES = TRAINTICKET + [
    "nacos",
    "nacosdb-mysql-leader",
    "nacosdb-mysql-follower",
    "rabbitmq",
    "tsdb-mysql-leader",
    "tsdb-mysql-follower",
]

SYSTEM_CONFIG = {
    "boutique": {
        "default_namespace": "boutique",
        "app_services": BOUTIQUE,
        "log_services": BOUTIQUE_LOG_SERVICES,
        "connectivity_services": BOUTIQUE_CONNECTIVITY_SERVICES,
    },
    "train-ticket": {
        "default_namespace": "train-ticket",
        "app_services": TRAINTICKET,
        "log_services": TRAINTICKET_LOG_SERVICES,
        "connectivity_services": TRAINTICKET_CONNECTIVITY_SERVICES,
    },
}

RESOURCE_ALIASES_DB = {
    "pod": "pods", "pods": "pods", "po": "pods",
    "service": "services", "services": "services", "svc": "services",
    "deployment": "deployments", "deployments": "deployments", "deploy": "deployments",
    "statefulset": "statefulsets", "statefulsets": "statefulsets", "sts": "statefulsets",
    "daemonset": "daemonsets", "daemonsets": "daemonsets", "ds": "daemonsets",
    "configmap": "configmaps", "configmaps": "configmaps", "cm": "configmaps",
    "secret": "secrets", "secrets": "secrets",
    "persistentvolumeclaim": "persistentvolumeclaims", "persistentvolumeclaims": "persistentvolumeclaims", "pvc": "persistentvolumeclaims",
    "replicaset": "replicasets", "replicasets": "replicasets", "rs": "replicasets",
    "ingress": "ingresses", "ingresses": "ingresses", "ing": "ingresses",
    "networkpolicy": "networkpolicies", "networkpolicies": "networkpolicies", "netpol": "networkpolicies",
    "serviceaccount": "serviceaccounts", "serviceaccounts": "serviceaccounts", "sa": "serviceaccounts",
    "job": "jobs", "jobs": "jobs",
    "endpoint": "endpoints", "endpoints": "endpoints", "ep": "endpoints",
    "persistentvolume": "persistentvolumes", "persistentvolumes": "persistentvolumes", "pv": "persistentvolumes",
    "namespace": "namespaces", "namespaces": "namespaces", "ns": "namespaces",
    "node": "nodes", "nodes": "nodes", "no": "nodes",
    "storageclass": "storageclasses", "storageclasses": "storageclasses", "sc": "storageclasses",
    "event": "events", "events": "events",
    "resourcequota": "resourcequota","resourcequotas":"resourcequota"
}

LABEL_SELECTOR_SUPPORTED_TYPES = {
    "pods",
    "services",
    "deployments",
    "persistentvolumeclaims",
}

CLUSTER_SCOPED_RESOURCE_TYPES = {
    "nodes",
    "persistentvolumes",
    "storageclasses",
    "namespaces",
}

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

def normalize_resource_type(resource_type):
    if not resource_type:
        return None
    key = resource_type.lower()
    return RESOURCE_ALIASES_DB.get(key)


def _build_cache_key(prefix: str, params: dict) -> str:
    return f"{prefix}:{json.dumps(params, ensure_ascii=False, separators=(',', ':'))}"


def _is_empty_result(result) -> bool:
    return result in ("", None, [], {})


def _normalize_log_entries(raw_value) -> list[str]:
    if raw_value in (None, "", []):
        return []
    if isinstance(raw_value, list):
        return [str(item) for item in raw_value if str(item).strip()]
    if isinstance(raw_value, str):
        return [line for line in raw_value.splitlines() if line.strip()]
    return [str(raw_value)]


def _collect_service_log_entries(raw_logs: dict, service_name: str, lines: int) -> list[str]:
    service_sources = [
        (service_name, f"From {service_name} logs:"),
        (f"{service_name}.previous", "From previous container logs:"),
        (f"{service_name}.istio-proxy", "From istio-proxy logs:"),
    ]

    collected = []
    for key, header in service_sources:
        entries = _normalize_log_entries(raw_logs.get(key))
        if not entries:
            continue

        if collected:
            collected.append("")
        collected.append(header)
        collected.extend(entries[-lines:])
    return collected


def _parse_simple_label_selector(label_selector: Optional[str]) -> Optional[tuple[str, str]]:
    if label_selector is None:
        return None

    selector = label_selector.strip()
    if not selector:
        return None

    if selector.count("=") != 1:
        raise ValueError(
            "Error: Only simple label selectors in the form 'key=value' are supported."
        )

    key, value = selector.split("=", 1)
    key = key.strip()
    value = value.strip()
    if not key or not value:
        raise ValueError(
            "Error: Only simple label selectors in the form 'key=value' are supported."
        )
    return key, value


def _extract_resource_names(table_output: str) -> list[str]:
    lines = [line for line in str(table_output).splitlines() if line.strip()]
    if len(lines) <= 1:
        return []

    names = []
    for line in lines[1:]:
        parts = line.split()
        if parts:
            names.append(parts[0])
    return names


def _filter_table_by_names(table_output: str, matched_names: set[str]) -> str:
    lines = [line for line in str(table_output).splitlines() if line.strip()]
    if len(lines) <= 1:
        return table_output

    filtered_lines = [lines[0]]
    for line in lines[1:]:
        parts = line.split()
        if parts and parts[0] in matched_names:
            filtered_lines.append(line)
    return "\n".join(filtered_lines)


def _filter_show_labels_table(table_output: str, selector_key: str, selector_value: str) -> str:
    lines = [line for line in str(table_output).splitlines() if line.strip()]
    if len(lines) <= 1:
        return table_output

    expected = f"{selector_key}={selector_value}"
    filtered_lines = [lines[0]]
    for line in lines[1:]:
        if expected in line:
            filtered_lines.append(line)
    return "\n".join(filtered_lines)


def _filter_selector_column_table(table_output: str, selector_key: str, selector_value: str) -> str:
    lines = [line for line in str(table_output).splitlines() if line.strip()]
    if len(lines) <= 1:
        return table_output

    expected = f"{selector_key}={selector_value}"
    filtered_lines = [lines[0]]
    for line in lines[1:]:
        parts = line.split()
        if parts and parts[-1] == expected:
            filtered_lines.append(line)
    return "\n".join(filtered_lines)


class KubernetesTools:
    def __init__(self, case_path, system: str = "boutique", namespace: Optional[str] = None):
        system_key = system if system in SYSTEM_CONFIG else "boutique"
        system_config = SYSTEM_CONFIG[system_key]

        self.system = system_key
        self.default_namespace = namespace or system_config["default_namespace"]
        self.app_services = set(system_config["app_services"])
        self.log_services = set(system_config["log_services"])
        self.connectivity_services = set(system_config["connectivity_services"])

        tool_cache_path = os.path.join(case_path, "tool_cache.json")
        raw_log_path = os.path.join(case_path, "raw_data", "logs.json")
        with open(tool_cache_path, 'r', encoding='utf-8') as f:
            self.tool_cache = json.load(f)
        if os.path.exists(raw_log_path):
            with open(raw_log_path, 'r', encoding='utf-8') as f:
                self.raw_logs = json.load(f)
        else:
            self.raw_logs = {}

    def _lookup_cache_value(self, candidate_keys: list[str]):
        for key in candidate_keys:
            if key in self.tool_cache:
                return self.tool_cache[key], key
        return None, None

    def _cluster_scope_namespaces(self, namespace: Optional[str]) -> list[Optional[str]]:
        candidates = [None, ""]
        if namespace:
            candidates.append(namespace)
        candidates.append(self.default_namespace)

        ordered = []
        for item in candidates:
            if item not in ordered:
                ordered.append(item)
        return ordered

    def _build_get_resources_params(
        self,
        resource_type_norm: str,
        namespace: Optional[str],
        name: Optional[str],
        show_labels: bool = False,
        output_wide: bool = False,
        output_yaml: bool = False,
        label_selector: Optional[str] = None,
    ) -> dict:
        params = {
            "resource_type": resource_type_norm,
            "name": name if name is not None else "",
        }
        if namespace is not None:
            params["namespace"] = namespace
        if output_wide:
            params["output_wide"] = True
        if show_labels:
            params["show_labels"] = True
        if output_yaml:
            params["output_yaml"] = True
        if label_selector:
            params["label_selector"] = label_selector
        return params

    def _get_resources_candidate_keys(
        self,
        resource_type_norm: str,
        namespace: Optional[str],
        name: Optional[str],
        show_labels: bool = False,
        output_wide: bool = False,
        output_yaml: bool = False,
        label_selector: Optional[str] = None,
    ) -> list[str]:
        namespaces = (
            self._cluster_scope_namespaces(namespace)
            if resource_type_norm in CLUSTER_SCOPED_RESOURCE_TYPES
            else [namespace]
        )
        keys = []
        for ns in namespaces:
            params = self._build_get_resources_params(
                resource_type_norm=resource_type_norm,
                namespace=ns,
                name=name,
                show_labels=show_labels,
                output_wide=output_wide,
                output_yaml=output_yaml,
                label_selector=label_selector,
            )
            keys.append(_build_cache_key("GetResources", params))
        return keys

    def _describe_resource_candidate_keys(
        self,
        resource_type_norm: str,
        name: str,
        namespace: Optional[str],
    ) -> list[str]:
        namespaces = (
            self._cluster_scope_namespaces(namespace)
            if resource_type_norm in CLUSTER_SCOPED_RESOURCE_TYPES
            else [namespace]
        )
        keys = []
        for ns in namespaces:
            params = {
                "resource_type": resource_type_norm,
                "name": name,
            }
            if ns is not None:
                params["namespace"] = ns
            keys.append(_build_cache_key("DescribeResource", params))
        return keys

    def _resolve_selector_matched_names(
        self,
        resource_type_norm: str,
        namespace: Optional[str],
        name: Optional[str],
        selector_key: str,
        selector_value: str,
        raw_label_selector: str,
    ) -> set[str]:
        selector_result, _ = self._lookup_cache_value(
            self._get_resources_candidate_keys(
                resource_type_norm=resource_type_norm,
                namespace=namespace,
                name=name,
                label_selector=raw_label_selector,
            )
        )
        if selector_result and not _is_empty_result(selector_result):
            names = _extract_resource_names(selector_result)
            if names:
                return set(names)

        show_labels_result, _ = self._lookup_cache_value(
            self._get_resources_candidate_keys(
                resource_type_norm=resource_type_norm,
                namespace=namespace,
                name=name,
                show_labels=True,
            )
        )
        if show_labels_result and not _is_empty_result(show_labels_result):
            filtered = _filter_show_labels_table(
                show_labels_result, selector_key, selector_value
            )
            names = _extract_resource_names(filtered)
            if names:
                return set(names)

        output_wide_result, _ = self._lookup_cache_value(
            self._get_resources_candidate_keys(
                resource_type_norm=resource_type_norm,
                namespace=namespace,
                name=name,
                output_wide=True,
            )
        )
        if output_wide_result and not _is_empty_result(output_wide_result):
            filtered = _filter_selector_column_table(
                output_wide_result, selector_key, selector_value
            )
            names = _extract_resource_names(filtered)
            if names:
                return set(names)

        return set()

   
    def GetResources(
        self,
        resource_type: str,
        namespace: Optional[str] = None,
        name: str = None,
        show_labels: bool = False,
        output_wide: bool = False,
        label_selector: str = None
    ) -> str:
        resource_type_norm=normalize_resource_type(resource_type)
        if not resource_type_norm:
            return f"Error: Unknown resource type '{resource_type}'"

        is_cluster_scoped = resource_type_norm in CLUSTER_SCOPED_RESOURCE_TYPES
        if not is_cluster_scoped and not namespace:
            raise ValueError("Error: 'GetResources' command requires a specific 'namespace'.")

        raw_label_selector = (label_selector or "").strip()
        parsed_label_selector = None
        if raw_label_selector:
            if resource_type_norm not in LABEL_SELECTOR_SUPPORTED_TYPES:
                return (
                    f"Error: label_selector is not supported for {resource_type_norm} "
                    f"in this benchmark. Please query all {resource_type_norm} in the "
                    f"namespace and manually inspect."
                )
            parsed_label_selector = _parse_simple_label_selector(raw_label_selector)

        if show_labels and output_wide:
            raise ValueError(
                "Error: Only one of '--show-labels' or '-o wide' can be specified at a time for kubectl get."
            )

        ideal_namespace = None if is_cluster_scoped else namespace

        try:
            primary_result, primary_key = self._lookup_cache_value(
                self._get_resources_candidate_keys(
                    resource_type_norm=resource_type_norm,
                    namespace=ideal_namespace,
                    name=name,
                    show_labels=show_labels,
                    output_wide=output_wide,
                    label_selector=raw_label_selector or None,
                )
            )
            if primary_result is not None and not _is_empty_result(primary_result):
                return primary_result

            if parsed_label_selector:
                selector_key, selector_value = parsed_label_selector
                matched_names = self._resolve_selector_matched_names(
                    resource_type_norm=resource_type_norm,
                    namespace=ideal_namespace,
                    name=name,
                    selector_key=selector_key,
                    selector_value=selector_value,
                    raw_label_selector=raw_label_selector,
                )

                formatted_result = None
                if output_wide or show_labels:
                    formatted_result, _ = self._lookup_cache_value(
                        self._get_resources_candidate_keys(
                            resource_type_norm=resource_type_norm,
                            namespace=ideal_namespace,
                            name=name,
                            show_labels=show_labels,
                            output_wide=output_wide,
                        )
                    )
                else:
                    formatted_result, _ = self._lookup_cache_value(
                        self._get_resources_candidate_keys(
                            resource_type_norm=resource_type_norm,
                            namespace=ideal_namespace,
                            name=name,
                        )
                    )

                if matched_names and formatted_result and not _is_empty_result(formatted_result):
                    filtered_result = _filter_table_by_names(formatted_result, matched_names)
                    if len(_extract_resource_names(filtered_result)) > 0:
                        return filtered_result

                if matched_names:
                    selector_result, _ = self._lookup_cache_value(
                        self._get_resources_candidate_keys(
                            resource_type_norm=resource_type_norm,
                            namespace=ideal_namespace,
                            name=name,
                            label_selector=raw_label_selector,
                        )
                    )
                    if selector_result and not _is_empty_result(selector_result):
                        return selector_result

                if primary_result is not None and _is_empty_result(primary_result):
                    return f'No matching {resource_type_norm} found for selector "{raw_label_selector}".'

                return f'No matching {resource_type_norm} found for selector "{raw_label_selector}".'

            if primary_result is not None and _is_empty_result(primary_result):
                if is_cluster_scoped:
                    return f"No {resource_type_norm} found."
                return f"No resources found in {namespace} namespace."

            if name:
                if is_cluster_scoped:
                    return f"Error from server (NotFound): {resource_type_norm} \"{name}\" not found"
                return f"Error from server (NotFound): {resource_type_norm} \"{name}\" not found in namespace \"{namespace}\""

            if is_cluster_scoped:
                return f"No {resource_type_norm} found."
            return f"No resources found in {namespace} namespace."
        except Exception as e:
            failed_key = primary_key if 'primary_key' in locals() else "GetResources lookup"
            return f"An unexpected error occurred during snapshot lookup for '{failed_key}': {e}"


    def GetResources_v2(
        self,
        resource_type: str,
        namespace: Optional[str] = None,
        name: str = None,
        show_labels: bool = False,
        output_wide: bool = False,
        output_yaml: bool = False,
    ) -> str:
        resource_type_norm = normalize_resource_type(resource_type)
        if not resource_type_norm:
            return f"Error: Unknown resource type '{resource_type}'"

        is_cluster_scoped = resource_type_norm in CLUSTER_SCOPED_RESOURCE_TYPES
        if not is_cluster_scoped and not namespace:
            raise ValueError("Error: 'GetResources_v2' command requires a specific 'namespace'.")

        if show_labels and output_wide:
            raise ValueError(
                "Error: Only one of '--show-labels' or '-o wide' can be specified at a time for kubectl get."
            )
        if output_yaml and (show_labels or output_wide):
            raise ValueError(
                "Error: 'output_yaml' cannot be combined with 'show_labels' or 'output_wide'."
            )
        if output_yaml and resource_type_norm not in YAML_SNAPSHOT_RESOURCES:
            return (
                f"Error: output_yaml is only supported for single named resources of types "
                f"{sorted(YAML_SNAPSHOT_RESOURCES)}."
            )
        if output_yaml and not name:
            raise ValueError(
                "Error: 'output_yaml' requires a specific resource 'name'; list queries are not supported."
            )

        ideal_namespace = None if is_cluster_scoped else namespace

        try:
            primary_result, primary_key = self._lookup_cache_value(
                self._get_resources_candidate_keys(
                    resource_type_norm=resource_type_norm,
                    namespace=ideal_namespace,
                    name=name,
                    show_labels=show_labels,
                    output_wide=output_wide,
                    output_yaml=output_yaml,
                )
            )

            if primary_result is not None and not _is_empty_result(primary_result):
                return primary_result

            if output_yaml:
                if primary_result is not None and _is_empty_result(primary_result):
                    return (
                        f"Error: YAML snapshot for {resource_type_norm} \"{name}\" is empty or not available."
                    )
                if is_cluster_scoped:
                    return (
                        f"Error: YAML snapshot for {resource_type_norm} \"{name}\" is not recorded."
                    )
                return (
                    f"Error: YAML snapshot for {resource_type_norm} \"{name}\" is not recorded in "
                    f"namespace \"{namespace}\"."
                )

            if primary_result is not None and _is_empty_result(primary_result):
                if is_cluster_scoped:
                    return f"No {resource_type_norm} found."
                return f"No resources found in {namespace} namespace."

            if name:
                if is_cluster_scoped:
                    return f"Error from server (NotFound): {resource_type_norm} \"{name}\" not found"
                return f"Error from server (NotFound): {resource_type_norm} \"{name}\" not found in namespace \"{namespace}\""

            if is_cluster_scoped:
                return f"No {resource_type_norm} found."
            return f"No resources found in {namespace} namespace."
        except Exception as e:
            failed_key = primary_key if 'primary_key' in locals() else "GetResources_v2 lookup"
            return f"An unexpected error occurred during snapshot lookup for '{failed_key}': {e}"
    
 
    def DescribeResource(
        self,
        resource_type: str,
        name: str,
        namespace: Optional[str]
    ) -> str:
        if not resource_type:
            raise ValueError("Error: 'DescribeResource' command requires a specific 'resource_type'.")
        if not name:
            raise ValueError("Error: 'DescribeResource' command requires a specific 'name'.")

        resource_type_norm=normalize_resource_type(resource_type)
        if not resource_type_norm:
            return f"Error: Unknown resource type '{resource_type}'"
        if resource_type_norm == "namespaces":
            return "Error: Describing namespaces is not supported in this benchmark. Use `GetResources(resource_type=\"namespaces\")` instead."

        is_cluster_scoped = resource_type_norm in CLUSTER_SCOPED_RESOURCE_TYPES
        if not is_cluster_scoped and not namespace:
            raise ValueError("Error: 'DescribeResource' command requires a specific 'namespace'.")

        command_keys = self._describe_resource_candidate_keys(
            resource_type_norm=resource_type_norm,
            name=name,
            namespace=None if is_cluster_scoped else namespace,
        )
        try:
            result, _ = self._lookup_cache_value(command_keys)
            if result is not None:
                return result
            if is_cluster_scoped:
                return f"Error from server (NotFound): {resource_type_norm} \"{name}\" not found"
            return f"Error from server (NotFound): {resource_type} \"{name}\" not found in namespace \"{namespace}\""
        except Exception as e:
            return f"An unexpected error occurred during snapshot lookup for '{command_keys[0]}': {e}"
    
 
    def GetAppYAML(
        self, app_name: str,
        ) -> str:
        if not app_name:
            raise ValueError("Error: 'GetAppYAML' command requires a specific 'app_name'.")

        if app_name not in self.app_services:
            allowed = sorted(self.app_services)
            raise ValueError(f"Error: Resource '{app_name}' is not in the allowed list of services for {self.system}. Allowed: {allowed}")
        
        params = {"app_name": app_name}
        command_key = f"GetAppYAML:{json.dumps(params,separators=(',', ':'))}"
        print(command_key)
      
        try:
            return self.tool_cache[command_key]
        except KeyError:
            
            error_msg = f"Error: YAML configuration for '{app_name}' is not recorded."
            return error_msg
        except Exception as e:
            return f"An unexpected error occurred during snapshot lookup for '{command_key}': {e}"
    

    def GetServiceDependencies(
        self, service_name: str
    ) -> str:
        if not service_name:
            raise ValueError("Error: 'GetServiceDependencies' command requires a specific 'service_name'.")
  
        if service_name not in self.app_services:
            allowed = sorted(self.app_services)
            raise ValueError(f"Error: Resource '{service_name}' is not in the allowed list services for {self.system}. Allowed: {allowed}")
        
        params = {"service_name": service_name}
        command_key = f"GetServiceDependencies:{json.dumps(params,separators=(',', ':'))}"
        print(command_key)
        try:
            return self.tool_cache[command_key]
        except KeyError:
            error_msg = f" Error: Dependencies for '{service_name}' not recorded in trace data."
            return error_msg
        except Exception as e:
            return f"An unexpected error occurred during snapshot lookup for '{command_key}': {e}"


    def GetRecentLogs(
        self,
        namespace: str,
        service_name: str,
        lines: int = 50
    ) -> str:
        if not service_name:
            raise ValueError("Error: GetRecentLogs requires a specific 'service_name'.")
        if not namespace:
            raise ValueError("Error: GetRecentLogs requires a specific 'namespace'.")
        if service_name not in self.log_services:
            allowed = sorted(self.log_services)
            return f"Error: GetRecentLogs does not support service '{service_name}' for {self.system}. Allowed: {allowed}"
        if namespace != self.default_namespace:
            return (
                f"Error: GetRecentLogs expected namespace '{self.default_namespace}' "
                f"for system '{self.system}', got '{namespace}'."
            )

        try:
            recent_logs = _collect_service_log_entries(self.raw_logs, service_name, lines)
            if not recent_logs:
                return f"No recent logs found for {service_name} in {namespace} namespace."
            return recent_logs
        except KeyError:
            error_msg = f" Error: The query result of GetRecentLogs was not found in records. Please check whether the parameters are correct (such as whether the resource type, name, namespace exist or are misspelled) to avoid invalid function calls."
            return error_msg
        except Exception as e:
            return f"An unexpected error occurred during snapshot lookup for GetRecentLogs:{service_name}: {e}"

    
    def CheckServiceConnectivity(
        self,
        service_name: str,
        port: int,
        namespace: str
    ) -> str:
        if not service_name:
            raise ValueError("Error: 'service_name' is required for connectivity check.")
        if port is None:
            raise ValueError("Error: 'port' is required for connectivity check.")
        if not namespace:
            raise ValueError("Error: 'namespace' is required for connectivity check.")
        if service_name not in self.connectivity_services:
            allowed = sorted(self.connectivity_services)
            raise ValueError(
                f"Error: service '{service_name}' is not supported for connectivity checks in {self.system}. "
                f"Allowed: {allowed}"
            )

        try:
            port = int(port)
        except (ValueError, TypeError):
            raise ValueError(f"Error: 'port' must be an integer, got {type(port).__name__}")
        
        params = {
            "namespace": namespace,
            "service_name": service_name,
            "port": port
        }
        command_key = f"CheckServiceConnectivity:{json.dumps(params,separators=(',', ':'))}"
        print(command_key)

        try:
            return self.tool_cache[command_key]
        except KeyError:
            return f"Connection failed"
        except Exception as e:
            return f"An unexpected error occurred during snapshot lookup for '{command_key}': {e}"

    def GetClusterConfiguration(self) -> str:
   
        command_keys = ["GetClusterConfiguration:{}", "GetClusterConfiguration"]
        print(command_keys[0])
        try:
            result, _ = self._lookup_cache_value(command_keys)
            if result is not None:
                return result
            error_msg = f"Error: Cluster configuration snapshot is not available in the dataset."
            return error_msg
        except Exception as e:
            return f"An unexpected error occurred during snapshot lookup for '{command_keys[0]}': {e}"
        

    def GetAlerts(self) -> str:
        command_key = "GetAlerts:{}"

        print(command_key)
        try:
            alerts_data = self.tool_cache[command_key]
            if alerts_data in ("", None, [], {}):
                return "No active metric anomalies detected at this time."
            return alerts_data
        except KeyError:
            error_msg = f"Error: Cluster alerts is not available in the dataset."
            return error_msg
        except Exception as e:
            return f"An unexpected error occurred during snapshot lookup for '{command_key}': {e}"

    def GetErrorLogs(
            self,
            namespace: str,
            service_name: str
        )-> str:
        if not service_name:
            raise ValueError("Error: 'service_name' is required.")
        if not namespace:
            raise ValueError("Error: 'namespace' is required.")
        if service_name not in self.log_services:
            allowed = sorted(self.log_services)
            raise ValueError(
                f"Error: GetErrorLogs does not support service '{service_name}' for {self.system}. "
                f"Allowed: {allowed}"
            )
        params = {
            "namespace": namespace,
            "service_name": service_name
            }
        command_key = f"GetErrorLogs:{json.dumps(params,separators=(',', ':'))}"
        print(command_key)
        try:
            log_summary_data = self.tool_cache[command_key]
            if log_summary_data in ("", None, [], {}):
                return f"No error logs found for {service_name} in {namespace} namespace."
            if isinstance(log_summary_data, dict):
                if log_summary_data.get("total_errors") == 0:
                    return f"No error logs found for {service_name} in {namespace} namespace."
                if "patterns" in log_summary_data and not log_summary_data.get("patterns"):
                    return f"No error logs found for {service_name} in {namespace} namespace."

            return json.dumps(log_summary_data, indent=2, ensure_ascii=False)
        except KeyError:
            error_msg = f"Error: Error logs for the specified service are not available."
            return error_msg
        except Exception as e:
            return f"An unexpected error occurred during snapshot lookup for '{command_key}': {e}"

    def CheckNodeServiceStatus(self, node_name: str, service_name: str) -> str:

        if not node_name:
            raise ValueError("Error: 'node_name' is required for checking node service status.")
        if not service_name:
            raise ValueError("Error: 'service_name' is required for checking node service status.")
        
     
        params = {
            "node_name": node_name,
            "service_name": service_name
        }

        if service_name == "kube-scheduler" and node_name != "master":
            return (
                f"Error: '{service_name}' is not expected to run on node '{node_name}' "
                "in this benchmark setup. Query the 'master' node instead."
            )

        command_key = f"CheckNodeServiceStatus:{json.dumps(params,separators=(',', ':'))}"
        print(command_key)

        try:
            return self.tool_cache[command_key]
        except KeyError:

            error_msg = f"Error: Status information for cluster control plane components is not available in the dataset"
            return error_msg
        except Exception as e:
            return f"An unexpected error occurred during snapshot lookup for '{command_key}': {e}"
        
