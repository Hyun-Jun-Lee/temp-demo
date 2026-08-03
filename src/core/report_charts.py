from typing import Any


def build_report_charts(report_result: dict[str, Any]) -> list[dict[str, Any]]:
    node_results = report_result.get("node_result") or []
    summary = _find_node_result(node_results, "summary")
    global_health = _find_node_result(node_results, "global_health")
    memory = _find_node_result(node_results, "memory")
    os_result = _find_node_result(node_results, "os")

    charts: list[dict[str, Any]] = []

    risk_chart = _build_risk_chart(summary, global_health, memory, os_result)
    if risk_chart:
        charts.append(risk_chart)

    memory_chart = _build_metrics_chart(
        chart_id="memory_metrics",
        title="Memory 주요 지표",
        metrics=memory.get("key_metrics") if memory else None,
    )
    if memory_chart:
        charts.append(memory_chart)

    os_chart = _build_metrics_chart(
        chart_id="os_cluster_metrics",
        title="OS Cluster 지표",
        metrics=os_result.get("cluster_metrics") if os_result else None,
    )
    if os_chart:
        charts.append(os_chart)

    instance_chart = _build_instance_chart(os_result)
    if instance_chart:
        charts.append(instance_chart)

    return charts


def _build_risk_chart(
    summary: dict[str, Any] | None,
    global_health: dict[str, Any] | None,
    memory: dict[str, Any] | None,
    os_result: dict[str, Any] | None,
) -> dict[str, Any] | None:
    values = [
        ("Overall", summary.get("overall_score") if summary else None),
        (
            "Global Health",
            global_health.get("overall_health_score") if global_health else None,
        ),
        ("Memory Severity", memory.get("severity_score") if memory else None),
        ("OS Severity", os_result.get("severity_score") if os_result else None),
        ("OS CPU Pressure", os_result.get("cpu_pressure_score") if os_result else None),
        (
            "OS Memory Pressure",
            os_result.get("memory_pressure_score") if os_result else None,
        ),
        ("Imbalance", os_result.get("imbalance_score") if os_result else None),
    ]

    points = [(label, _to_number(value)) for label, value in values]
    points = [(label, value) for label, value in points if value is not None]

    if not points:
        return None

    return {
        "id": "risk_scores",
        "title": "Risk Scores",
        "type": "bar",
        "labels": [label for label, _ in points],
        "datasets": [
            {
                "label": "Score",
                "values": [value for _, value in points],
            }
        ],
    }


def _build_metrics_chart(
    chart_id: str,
    title: str,
    metrics: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not metrics:
        return None

    points = [
        (key, _to_number(value))
        for key, value in metrics.items()
        if _to_number(value) is not None
    ]

    if not points:
        return None

    return {
        "id": chart_id,
        "title": title,
        "type": "bar",
        "labels": [label for label, _ in points],
        "datasets": [
            {
                "label": "Value",
                "values": [value for _, value in points],
            }
        ],
    }


def _build_instance_chart(os_result: dict[str, Any] | None) -> dict[str, Any] | None:
    if not os_result:
        return None

    instances = os_result.get("instance_scores") or []
    if not instances:
        return None

    labels = [
        str(item.get("HOST_NAME") or item.get("host_name") or item.get("INST_ID") or index + 1)
        for index, item in enumerate(instances)
    ]
    metric_keys = [
        ("severity_score", "Severity"),
        ("cpu_util_pct", "CPU %"),
        ("memory_util_pct", "Memory %"),
        ("workload_share_pct", "Workload %"),
    ]
    datasets = []

    for key, label in metric_keys:
        values = [_to_number(item.get(key)) for item in instances]
        if any(value is not None for value in values):
            datasets.append(
                {
                    "label": label,
                    "values": [value if value is not None else 0 for value in values],
                }
            )

    if not datasets:
        return None

    return {
        "id": "os_instance_scores",
        "title": "OS Instance Scores",
        "type": "bar",
        "labels": labels,
        "datasets": datasets,
    }


def _find_node_result(
    node_results: list[dict[str, Any]],
    node_name: str,
) -> dict[str, Any] | None:
    for item in node_results:
        if item.get("node") == node_name:
            result = item.get("result")
            return result if isinstance(result, dict) else None

    return None


def _to_number(value: Any) -> int | float | None:
    if isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        return value

    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None

    return None
