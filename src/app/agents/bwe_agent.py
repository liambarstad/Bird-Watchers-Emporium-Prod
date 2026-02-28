from fastapi import Depends
from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode
from langchain_openai import ChatOpenAI

from state import BWEState
from config import get_settings
from agents.neo4j_agent import build_neo4j_agent
from nodes.bwe_nodes import (
    create_agent_node, 
    create_should_continue_node,
    create_finalize_node,
    create_neo4j_node,
)
from tools.bwe_tools import create_bwe_tools

settings = get_settings()


def build_bwe_agent(
    neo4j_agent: CompiledStateGraph = Depends(build_neo4j_agent)
) -> CompiledStateGraph:

    llm = ChatOpenAI(
        base_url=f'http://{settings.llama_host}:{settings.llama_port}/v1',
        api_key='local-llama',
        model=settings.llama_model,
        temperature=0.2,
        streaming=False,
    )

    tools = create_bwe_tools()

    return (
        StateGraph(BWEState)
        .add_node('agent_node', create_agent_node(llm, tools))
        .add_node('tool_node', ToolNode(tools))
        .add_node('neo4j_agent', create_neo4j_node(neo4j_agent))
        .add_node('finalize_node', create_finalize_node(llm))
        .add_conditional_edges(
            'agent_node',
            create_should_continue_node(max_steps=5),
            {
                'continue': 'tool_node',
                'lookup_bird_info': 'neo4j_agent',
                'finalize': 'finalize_node'
            }
        )
        .add_edge('tool_node', 'agent_node')
        .add_edge('neo4j_agent', 'agent_node')
        .add_edge('finalize_node', END)
        .set_entry_point('agent_node')
        .compile()
    )