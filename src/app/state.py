from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages
from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field

from utils.neo4j_results import Neo4jResults


class BWEState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    step: int = 0
    messages: list[BaseMessage]
    reasoning_steps: Annotated[list[BaseMessage], add_messages] = []
    final_answer: str = ''
    neo4j_results: dict[str, Neo4jResults] = {}


class Neo4jState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    step: int = 0
    messages: Annotated[list[BaseMessage], add_messages]
    neo4j_results: Neo4jResults = None
