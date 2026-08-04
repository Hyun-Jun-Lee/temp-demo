from typing import Any


def build_report_charts(report_result: dict[str, Any]) -> list[dict[str, Any]]:
    node_results = report_result.get("node_result") or []
    summary = _find_node_result(node_results, "summary")
    global_health = _find_node_result(node_results, "global_health")
    memory = _find_node_result(node_results, "memory")
    os_result = _find_node_result(node_results, "os")
    tempspace = _find_node_result(node_results, "tempspace")
    log_write = _find_node_result(node_results, "log_write")

    charts: list[dict[str, Any]] = []

    risk_chart = _build_risk_chart(
        summary,
        global_health,
        memory,
        os_result,
        tempspace,
        log_write,
    )
    if risk_chart:
        charts.append(risk_chart)

    memory_chart = _build_metrics_chart(
        chart_id="memory_metrics",
        title="Memory 주요 지표",
        metrics=memory.get("key_metrics") if memory else None,
    )
    if memory_chart:
        charts.append(memory_chart)

    memory_trend_chart = _build_timeseries_chart(
        chart_id="memory_trends",
        title="Memory 추세",
        timeseries=memory.get("metric_timeseries") if memory else None,
        dataset_labels={
            "shared_pool_free_mb": "Shared Pool Free MB",
            "hard_parse_per_sec": "Hard Parse / Sec",
            "soft_parse_ratio": "Soft Parse Ratio",
        },
    )
    if memory_trend_chart:
        charts.append(memory_trend_chart)

    memory_breakdown_chart = _build_distribution_chart(
        chart_id="memory_breakdown",
        title="Memory 구성",
        distribution=memory.get("memory_breakdown") if memory else None,
        chart_type="doughnut",
        dataset_label="MB",
    )
    if memory_breakdown_chart:
        charts.append(memory_breakdown_chart)

    os_chart = _build_metrics_chart(
        chart_id="os_cluster_metrics",
        title="OS Cluster 지표",
        metrics=os_result.get("cluster_metrics") if os_result else None,
    )
    if os_chart:
        charts.append(os_chart)

    os_trend_chart = _build_timeseries_chart(
        chart_id="os_resource_trends",
        title="OS 리소스 추세",
        timeseries=os_result.get("resource_timeseries") if os_result else None,
        dataset_labels={
            "cpu_util_pct": "CPU %",
            "memory_util_pct": "Memory %",
            "paging_rate_per_sec": "Paging / Sec",
        },
    )
    if os_trend_chart:
        charts.append(os_trend_chart)

    bottleneck_chart = _build_distribution_chart(
        chart_id="os_bottleneck_distribution",
        title="OS 병목 분포",
        distribution=os_result.get("bottleneck_distribution") if os_result else None,
        chart_type="pie",
        dataset_label="Evidence",
    )
    if bottleneck_chart:
        charts.append(bottleneck_chart)

    instance_chart = _build_instance_chart(os_result)
    if instance_chart:
        charts.append(instance_chart)

    temp_metrics_chart = _build_metrics_chart(
        chart_id="tempspace_metrics",
        title="TEMP 주요 지표",
        metrics=tempspace.get("key_metrics") if tempspace else None,
    )
    if temp_metrics_chart:
        charts.append(temp_metrics_chart)

    temp_trend_chart = _build_timeseries_chart(
        chart_id="tempspace_trends",
        title="TEMP 사용 추세",
        timeseries=tempspace.get("temp_usage_timeseries") if tempspace else None,
        dataset_labels={
            "temp_used_pct": "TEMP Used %",
            "workarea_spill_mb": "Workarea Spill MB",
        },
    )
    if temp_trend_chart:
        charts.append(temp_trend_chart)

    temp_breakdown_chart = _build_distribution_chart(
        chart_id="tempspace_breakdown",
        title="TEMP 공간 구성",
        distribution=tempspace.get("temp_space_breakdown") if tempspace else None,
        chart_type="doughnut",
        dataset_label="MB",
    )
    if temp_breakdown_chart:
        charts.append(temp_breakdown_chart)

    log_metrics_chart = _build_metrics_chart(
        chart_id="log_write_metrics",
        title="Log Write 주요 지표",
        metrics=log_write.get("key_metrics") if log_write else None,
    )
    if log_metrics_chart:
        charts.append(log_metrics_chart)

    log_trend_chart = _build_timeseries_chart(
        chart_id="log_write_trends",
        title="Redo/Commit 추세",
        timeseries=log_write.get("redo_write_timeseries") if log_write else None,
        dataset_labels={
            "redo_mb_per_sec": "Redo MB/Sec",
            "commits_per_sec": "Commits/Sec",
            "log_file_sync_avg_ms": "Log File Sync MS",
        },
    )
    if log_trend_chart:
        charts.append(log_trend_chart)

    log_wait_chart = _build_distribution_chart(
        chart_id="log_write_wait_distribution",
        title="Log Wait 분포",
        distribution=log_write.get("wait_event_distribution") if log_write else None,
        chart_type="pie",
        dataset_label="Wait MS",
    )
    if log_wait_chart:
        charts.append(log_wait_chart)

    return charts


def _build_risk_chart(
    summary: dict[str, Any] | None,
    global_health: dict[str, Any] | None,
    memory: dict[str, Any] | None,
    os_result: dict[str, Any] | None,
    tempspace: dict[str, Any] | None,
    log_write: dict[str, Any] | None,
) -> dict[str, Any] | None:
    values = [
        ("Overall", summary.get("overall_score") if summary else None),
        (
            "Global Health",
            global_health.get("overall_health_score") if global_health else None,
        ),
        ("Memory Severity", memory.get("severity_score") if memory else None),
        ("OS Severity", os_result.get("severity_score") if os_result else None),
        ("TEMP Severity", tempspace.get("severity_score") if tempspace else None),
        ("Log Write Severity", log_write.get("severity_score") if log_write else None),
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


def _build_timeseries_chart(
    chart_id: str,
    title: str,
    timeseries: dict[str, Any] | None,
    dataset_labels: dict[str, str],
) -> dict[str, Any] | None:
    if not timeseries:
        return None

    labels = _collect_timeseries_labels(timeseries)
    if not labels:
        return None

    datasets = []
    for key, display_label in dataset_labels.items():
        rows = timeseries.get(key) or []
        values_by_time = {
            str(row.get("time")): _to_number(row.get("value"))
            for row in rows
            if row.get("time") is not None
        }
        values = [values_by_time.get(label) for label in labels]

        if any(value is not None for value in values):
            datasets.append(
                {
                    "label": display_label,
                    "values": [value if value is not None else 0 for value in values],
                }
            )

    if not datasets:
        return None

    return {
        "id": chart_id,
        "title": title,
        "type": "line",
        "labels": labels,
        "datasets": datasets,
    }


def _build_distribution_chart(
    chart_id: str,
    title: str,
    distribution: dict[str, Any] | None,
    chart_type: str,
    dataset_label: str,
) -> dict[str, Any] | None:
    if not distribution:
        return None

    points = [
        (key, _to_number(value))
        for key, value in distribution.items()
        if _to_number(value) is not None
    ]
    points = [(label, value) for label, value in points if value is not None and value > 0]

    if not points:
        return None

    return {
        "id": chart_id,
        "title": title,
        "type": chart_type,
        "labels": [label for label, _ in points],
        "datasets": [
            {
                "label": dataset_label,
                "values": [value for _, value in points],
            }
        ],
    }


def _collect_timeseries_labels(timeseries: dict[str, Any]) -> list[str]:
    labels = {
        str(row.get("time"))
        for rows in timeseries.values()
        for row in (rows or [])
        if row.get("time") is not None
    }

    return sorted(labels)


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
