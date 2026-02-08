from typing import (
    Callable,
)

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import SystemMessage

from state import BWEState


def create_agent_node(llm: BaseChatModel, tools: list[Callable]) -> Callable:
	system_message = SystemMessage(content=(
		''
	))
	llm_with_tools = llm.bind_tools(tools)

	def agent_node(state: BWEState) -> BWEState:
		ai_msg = llm_with_tools.invoke(system_message + state['messages'])
		return { 'messages': [ai_msg] }

	return agent_node


def create_should_continue_node(max_steps: int) -> Callable:
	def should_continue(state: BWEState) -> str:
		if state['messages'].tool_calls and state['step'] < max_steps:
			return 'continue'
		return 'finalize'
	
	return should_continue


def create_finalize_node(llm: BaseChatModel) -> Callable:
	system_message = SystemMessage(content=(
		''
	))

	def finalize_node(state: BWEState) -> BWEState:
		summary = llm.invoke(system_message + state['messages']).content
		return {
			'summary': summary,
			'steps_taken': state['neo4j_results'].step_descriptions(),
			'num_results': state['neo4j_results'].num_results(),
			'sample': state['neo4j_results'].sample()
		}

	return finalize_node