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
