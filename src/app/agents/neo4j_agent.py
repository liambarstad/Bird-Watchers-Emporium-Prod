from functools import lru_cache

from neo4j import GraphDatabase
from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode
from langchain_openai import ChatOpenAI

from state import BWEState
from config import get_settings
from nodes.neo4j_nodes import (
    create_agent_node, 
    create_should_continue_node,
    finalize_node
)
from tools.neo4j_tools import create_neo4j_tools
from utils.embedding_client import EmbeddingClient


@lru_cache()
def build_neo4j_agent() -> CompiledStateGraph:
    settings = get_settings()

    llm = ChatOpenAI(
        base_url=f'http://{settings.llama_host}:{settings.llama_port}',
        model='qwen3:30b',
        temperature=0.2,
    )

    neo4j_driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_pwd)
    )
    db_name = settings.neo4j_database

    embedding_client = EmbeddingClient(
		base_url=f'http://{settings.embedding_host}:{settings.embedding_port}'
	)

    tools = create_neo4j_tools(
        neo4j_driver=neo4j_driver, 
        db_name=db_name,
        embedding_client=embedding_client
    )

    return (
        StateGraph(BWEState)
        .add_node('agent_node', create_agent_node(llm, tools))
        .add_node('tool_node', ToolNode(tools))
        .add_node('finalize_node', finalize_node)
        .set_entry_point('agent_node')
        .add_conditional_edges(
            'agent_node',
            create_should_continue_node(max_steps=5),
            {
                'continue': 'tool_node',
                'finalize': 'finalize_node'
            }
        ) 
        .add_edge('tool_node', 'agent_node')
        .add_edge('finalize_node', END)
    ).compile()