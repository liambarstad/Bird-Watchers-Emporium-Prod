import json
from typing import Callable

import structlog
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import SystemMessage

from state import Neo4jState

logger = structlog.get_logger(__name__)


def create_agent_node(llm: BaseChatModel, tools: list[Callable]) -> Callable:
    system_message = SystemMessage(content=(
        'You are a bird specialist who\'s role is to retrieve data from a database of bird facts, images, and other information.\n'
        'Given a conversation as context and a set of tools that allow you to interact with the database, '
        'Your goal is to reason step by step and use the tools, narrowing down the results set until it contains the information you need.\n'
        'When calling a tool, you MUST provide a \'step_description\' parameter that briefly describes what you are doing in natural language for the user (e.g. \'Searching for birds in North America...\').\n'
        'The end goal is to provide a set of results that can be used to answer the user\'s question.'
    ))

    async def agent_node(state: Neo4jState, config: RunnableConfig) -> Neo4jState:

        llm_with_tools = llm.bind_tools(tools, tool_choice=('any' if state.step == 0 else 'required'))

        messages = [system_message, *state.messages]
        ai_msg = await llm_with_tools.ainvoke(messages, config=config)

        logger.info('Neo4j agent node called', message=ai_msg.content, tool_calls=ai_msg.tool_calls, response_metadata=ai_msg.response_metadata)

        return Neo4jState(
            step=state.step + 1,
            messages=[ai_msg],
            neo4j_results=state.neo4j_results,
        )

    return agent_node


def create_should_continue_node(max_steps: int) -> Callable:
	def should_continue(state: Neo4jState) -> str:
		tool_calls = state.messages[-1].tool_calls
		if tool_calls and state.step < max_steps:
			logger.info('Neo4j agent node will execute tools', step=state.step, tool_calls=tool_calls)
			return 'continue'
		else:
			logger.info('Neo4j agent node will finalize', step=state.step)
			return 'finalize'
	
	return should_continue

