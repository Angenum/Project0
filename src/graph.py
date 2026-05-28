"""Компиляция StateGraph с feedback loops, HITL и checkpointing."""
from __future__ import annotations

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from .state import PipelineState
from .nodes import (
    orchestrator_node,
    researcher_node,
    architect_node,
    tdd_engineer_node,
    builder_node,
    prompt_engineer_node,
    tester_node,
    critic_node,
    security_auditor_node,
)
from .human_in_the_loop import approve_architect, approve_builder, approve_security
from .routers import route_after_tester, route_after_critic, route_after_approval
from .persistence import get_checkpointer


def build_pipeline(checkpointer=None):
    """Собирает граф."""
    if checkpointer is None:
        checkpointer = get_checkpointer()

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

    # Линейный поток
    builder.add_edge(START, "orchestrator")
    builder.add_edge("orchestrator", "researcher")
    builder.add_edge("researcher", "architect")
    builder.add_edge("architect", "approve_architect")

    builder.add_conditional_edges(
        "approve_architect",
        route_after_approval,
        {"__continue__": "tdd_engineer", "__end__": END},
    )
    builder.add_edge("tdd_engineer", "builder")
    builder.add_edge("builder", "approve_builder")
    builder.add_conditional_edges(
        "approve_builder",
        route_after_approval,
        {"__continue__": "prompt_engineer", "__end__": END},
    )
    builder.add_edge("prompt_engineer", "tester")

    # Feedback loops
    builder.add_conditional_edges(
        "tester",
        route_after_tester,
        {"builder": "builder", "critic": "critic"},
    )
    builder.add_conditional_edges(
        "critic",
        route_after_critic,
        {"builder": "builder", "security_auditor": "security_auditor"},
    )

    builder.add_edge("security_auditor", "approve_security")
    builder.add_conditional_edges(
        "approve_security",
        route_after_approval,
        {"__continue__": END, "__end__": END},
    )

    return builder.compile(checkpointer=checkpointer)


# Глобальный инстанс для локальной разработки
pipeline_graph = build_pipeline()
