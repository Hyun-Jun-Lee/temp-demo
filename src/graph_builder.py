from collections.abc import Sequence
from typing import Any, Callable

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from src.core.run_repository import save_node_status
from src.core.state import MainState
from src.nodes.classifier_node import classifier_node
from src.nodes.global_health_node import global_health_node
from src.nodes.log_write_node import log_write_node
from src.nodes.memory_node import memory_node
from src.nodes.os_node import os_node
from src.nodes.summary_node import summary_node
from src.nodes.tempspace_node import tempspace_node
from src.nodes.validation_node import validation_node


EXECUTABLE_NODES = {"memory", "os", "tempspace", "log_write"}


def graph_builder():
    """Build the LangGraph workflow for database ops questions."""
    graph = StateGraph(MainState)

    register_nodes(graph)
    register_edges(graph)

    return graph.compile()


def register_nodes(graph: StateGraph) -> StateGraph:
    graph.add_node("classifier", _with_node_tracking("classifier", classifier_node))
    graph.add_node(
        "global_health",
        _with_node_tracking("global_health", global_health_node),
    )
    graph.add_node("memory", _with_node_tracking("memory", memory_node))
    graph.add_node("os", _with_node_tracking("os", os_node))
    graph.add_node("tempspace", _with_node_tracking("tempspace", tempspace_node))
    graph.add_node("log_write", _with_node_tracking("log_write", log_write_node))
    graph.add_node("summary", _with_node_tracking("summary", summary_node))
    graph.add_node("validation", _with_node_tracking("validation", validation_node))

    return graph


def register_edges(graph: StateGraph) -> StateGraph:
    graph.add_edge(START, "classifier")

    graph.add_conditional_edges(
        "classifier",
        _route_from_classifier,
        ["global_health", "memory", "os", "tempspace", "log_write"],
    )
    graph.add_conditional_edges(
        "global_health",
        _route_to_target_nodes,
        ["memory", "os", "tempspace", "log_write"],
    )
    graph.add_edge("memory", "summary")
    graph.add_edge("os", "summary")
    graph.add_edge("tempspace", "summary")
    graph.add_edge("log_write", "summary")
    graph.add_edge("summary", "validation")
    graph.add_edge("validation", END)

    return graph


def _route_from_classifier(state: MainState) -> list[Send]:
    target_nodes = _normalize_target_nodes(state.get("target_nodes", []))

    if "global_health" in target_nodes:
        return [Send("global_health", state)]

    return _send_to_target_nodes(state, target_nodes)


def _route_to_target_nodes(state: MainState) -> list[Send]:
    target_nodes = _normalize_target_nodes(state.get("target_nodes", []))
    return _send_to_target_nodes(state, target_nodes)


def _send_to_target_nodes(state: MainState, target_nodes: Sequence[str]) -> list[Send]:
    nodes = [node_name for node_name in target_nodes if node_name in EXECUTABLE_NODES]

    if not nodes:
        raise ValueError(
            "target_nodes must include at least one executable node: "
            f"{', '.join(sorted(EXECUTABLE_NODES))}"
        )

    return [Send(node_name, state) for node_name in nodes]


def _normalize_target_nodes(target_nodes: Sequence[str]) -> list[str]:
    normalized: list[str] = []

    for node_name in target_nodes:
        if node_name not in normalized:
            normalized.append(node_name)

    return normalized


def _with_node_tracking(
    node_name: str,
    node_func: Callable[[MainState], dict[str, Any]],
) -> Callable[[MainState], dict[str, Any]]:
    def _tracked_node(state: MainState) -> dict[str, Any]:
        run_id = state.get("run_id")

        if run_id:
            save_node_status(run_id, node_name, "QUEUED")
            save_node_status(run_id, node_name, "RUNNING")

        try:
            result = node_func(state)
        except Exception as exc:
            if run_id:
                save_node_status(
                    run_id,
                    node_name,
                    "FAILED",
                    {"error": str(exc)},
                )
            raise

        if run_id:
            save_node_status(run_id, node_name, "COMPLETE", result)

        return result

    return _tracked_node
