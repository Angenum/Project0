"""Компиляция StateGraph с feedback loops, HITL и checkpointing."""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from .human_in_the_loop import approve_architect, approve_builder, approve_security
from .nodes import (
    architect_node,
    builder_node,
    critic_node,
    orchestrator_node,
    prompt_engineer_node,
    researcher_node,
    security_auditor_node,
    tdd_engineer_node,
    tester_node,
)
from .persistence import create_sync_checkpointer
from .routers import (
    make_route_unless_error,
    route_after_approval,
    route_after_builder,
    route_after_critic,
    route_after_tester,
)
from .state import PipelineState


def build_pipeline(checkpointer: Any | None = None) -> CompiledStateGraph:
    """Собирает граф."""
    if checkpointer is None:
        checkpointer = create_sync_checkpointer()

    builder = StateGraph(PipelineState)

    # Узлы
    builder.add_node("orchestrator", orchestrator_node)
    builder.add_node("researcher", researcher_node)
    builder.add_node("architect", architect_node)
    builder.add_node("approve_architect", approve_architect)
    builder.add_node("tdd_engineer", tdd_engineer_node)
    builder.add_node("builder", builder_node)
    builder.add_node("approve_builder", approve_builder)
    builder.add_node("prompt_engineer", prompt_engineer_node)
    builder.add_node("tester", tester_node)
    builder.add_node("critic", critic_node)
    builder.add_node("security_auditor", security_auditor_node)
    builder.add_node("approve_security", approve_security)

    # Линейный поток с остановкой при error
    builder.add_edge(START, "orchestrator")
    builder.add_conditional_edges(
        "orchestrator",
        make_route_unless_error("researcher"),
        {"researcher": "researcher", "__end__": END},
    )
    builder.add_conditional_edges(
        "researcher",
        make_route_unless_error("architect"),
        {"architect": "architect", "__end__": END},
    )
    builder.add_conditional_edges(
        "architect",
        make_route_unless_error("approve_architect"),
        {"approve_architect": "approve_architect", "__end__": END},
    )

    builder.add_conditional_edges(
        "approve_architect",
        route_after_approval,
        {"__continue__": "tdd_engineer", "__end__": END},
    )
    builder.add_conditional_edges(
        "tdd_engineer",
        make_route_unless_error("builder"),
        {"builder": "builder", "__end__": END},
    )
    builder.add_conditional_edges(
        "builder",
        route_after_builder,
        {"builder": "builder", "approve_builder": "approve_builder", "__end__": END},
    )
    builder.add_conditional_edges(
        "approve_builder",
        route_after_approval,
        {"__continue__": "prompt_engineer", "__end__": END},
    )
    builder.add_conditional_edges(
        "prompt_engineer",
        make_route_unless_error("tester"),
        {"tester": "tester", "__end__": END},
    )

    # Feedback loops
    builder.add_conditional_edges(
        "tester",
        route_after_tester,
        {"builder": "builder", "critic": "critic", "__end__": END},
    )
    builder.add_conditional_edges(
        "critic",
        route_after_critic,
        {"builder": "builder", "security_auditor": "security_auditor", "__end__": END},
    )

    builder.add_conditional_edges(
        "security_auditor",
        make_route_unless_error("approve_security"),
        {"approve_security": "approve_security", "__end__": END},
    )
    builder.add_conditional_edges(
        "approve_security",
        route_after_approval,
        {"__continue__": END, "__end__": END},
    )

    return builder.compile(checkpointer=checkpointer)
