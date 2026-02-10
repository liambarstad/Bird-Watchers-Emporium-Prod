from fastapi import Depends
from langgraph.graph.state import CompiledStateGraph
from langchain_openai import ChatOpenAI

from state import BWEState, Neo4jState
from config import get_settings
from agents.neo4j_agent import build_neo4j_agent


def build_bwe_agent(
    neo4j_agent: CompiledStateGraph = Depends(build_neo4j_agent)
) -> CompiledStateGraph:
    return neo4j_agent
    '''settings = get_settings()

    llm = ChatOpenAI(
        base_url=f'http://{settings.llama_host}:{settings.llama_port}',
        model=settings.llama_model,
        temperature=0.2,
    )

    return (
        StateGraph(BWEState)
        .add_node('agent_node', create_agent_node(llm, tools))
        .add_node('tool_node', ToolNode(tools))
        .add_node('finalize_node', finalize_node)
    )'''