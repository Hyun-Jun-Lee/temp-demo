from collections.abc import Sequence

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from src.core.state import MainState
from src.nodes.classifier_node import classifier_node
from src.nodes.global_health_node import global_health_node
from src.nodes.memory_node import memory_node
from src.nodes.os_node import os_node
from src.nodes.summary_node import summary_node
from src.nodes.validation_node import validation_node


def graph_builder():
    """Build the LangGraph workflow for database ops questions."""
    graph = StateGraph(MainState)

    register_nodes(graph)
    register_edges(graph)

    return graph.compile()


def register_nodes(graph: StateGraph) -> StateGraph:
    graph.add_node("classifier", classifier_node)
    graph.add_node("global_health", global_health_node)
    graph.add_node("memory", memory_node)
    graph.add_node("os", os_node)
    graph.add_node("summary", summary_node)
    graph.add_node("validation", validation_node)

    return graph


def register_edges(graph: StateGraph) -> StateGraph:
    graph.add_edge(START, "classifier")

    graph.add_conditional_edges(
        "classifier",
        _route_from_classifier,
        ["global_health", "memory", "os"],
    )
    graph.add_conditional_edges(
        "global_health",
        _route_to_target_nodes,
        ["memory", "os"],
    )
    graph.add_edge("memory", "summary")
    graph.add_edge("os", "summary")
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
    nodes = [node_name for node_name in target_nodes if node_name in {"memory", "os"}]

    if not nodes:
        raise ValueError("target_nodes must include at least one executable node: memory or os")

    return [Send(node_name, state) for node_name in nodes]


def _normalize_target_nodes(target_nodes: Sequence[str]) -> list[str]:
    normalized: list[str] = []

    for node_name in target_nodes:
        if node_name not in normalized:
            normalized.append(node_name)

    return normalized
