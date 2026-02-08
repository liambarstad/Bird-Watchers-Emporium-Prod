from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages
from typing import (
    TypedDict,
    Annotated,
    Sequence,
    NotRequired,
)

from utils.neo4j_results import Neo4jResults


class BWEState(TypedDict):
    messages: Annotated[Sequence[list[BaseMessage]], add_messages]
    final_answer: NotRequired[str]


class Neo4jState(TypedDict):
    step: int
    messages: Annotated[Sequence[list[BaseMessage]], add_messages]
    neo4j_results: NotRequired[Neo4jResults]
