from typing import (
    Callable,
)

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import SystemMessage

from state import Neo4jState


def create_agent_node(llm: BaseChatModel, tools: list[Callable]) -> Callable:
	system_message = SystemMessage(content=(
		'You are a bird specialist who\'s role is to retrieve data from a database of bird facts, images, and other information.\n'
		'Given a conversation as context and a set of tools that allow you to interact with the database, '
		'Your goal is to reason step by step and use the tools, narrowing down the results set until it contains the information you need.\n'
		'When calling a tool, you MUST provide a \'step_description\' parameter that briefly describes what you are doing in natural language for the user (e.g. \'Searching for birds in North America...\').\n'
		'The end goal is to provide a set of results that can be used to answer the user\'s question.'
	))
	llm_with_tools = llm.bind_tools(tools)

	def agent_node(state: Neo4jState) -> Neo4jState:
		messages = [system_message, *state.messages]
		ai_msg = llm_with_tools.invoke(messages)
		return Neo4jState(
			step=state.step + 1,
			messages=[ai_msg],
			neo4j_results=state.neo4j_results,
			final_answer=state.final_answer,
		)

	return agent_node


def create_should_continue_node(max_steps: int) -> Callable:
	def should_continue(state: Neo4jState) -> str:
		if state.messages[-1].tool_calls and state.step < max_steps:
			return 'continue'
		return 'finalize'
	
	return should_continue