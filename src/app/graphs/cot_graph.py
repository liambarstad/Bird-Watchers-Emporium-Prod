from functools import lru_cache
from langgraph.graph import END, StateGraph

from graphs.consts import AGENT_NODE, FINALIZE_NODE
from nodes.cot_nodes import agent_node, should_continue, finalize_node
from state import CoTState


@lru_cache()
def get_graph():
    return (
        StateGraph(CoTState)
        .add_node(AGENT_NODE, agent_node)
        .add_node(FINALIZE_NODE, finalize_node)
        .set_entry_point(AGENT_NODE)
        .add_conditional_edges(
            AGENT_NODE,
            should_continue,
            {
                "continue": AGENT_NODE,
                "finalize": FINALIZE_NODE,
            },
        )
        .add_edge(FINALIZE_NODE, END)
    ).compile()
