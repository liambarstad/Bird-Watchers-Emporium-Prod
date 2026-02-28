from typing import Callable

import structlog
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph

from state import BWEState, Neo4jState
from utils.neo4j_results import Neo4jResults

logger = structlog.get_logger(__name__)


def create_agent_node(llm: BaseChatModel, tools: list[Callable]) -> Callable:
    system_message = SystemMessage(content=(
        'You are a helpful assistant for a website called "Bird Watchers\' Emporium". \n'
        'Your goal is to answer questions pertaining to birds and bird watching, \n'
        'help users find trips, hotels, and gear, '
        'plan watching trips, '
        'and suggest cool birds to watch for their adventures! \n'
        'Be helpful and enthusiastic, and provide all the details they need in order to get bird watching!'
    ))
    llm_with_tools = llm.bind_tools(tools)

    async def agent_node(state: BWEState, config: RunnableConfig) -> BWEState:
        reasoning_context = state.reasoning_steps if state.reasoning_steps else state.messages
        
        messages = [system_message, *reasoning_context]
        ai_msg = llm_with_tools.invoke(messages, config=config)
        logger.info('BWE agent node called', messages=messages, response=ai_msg.content, tool_calls=ai_msg.tool_calls, response_metadata=ai_msg.response_metadata)
		
        return BWEState(
            step=state.step + 1,
            messages=state.messages,
            reasoning_steps=[ai_msg],
            neo4j_results=state.neo4j_results
        )

    return agent_node


def create_neo4j_node(neo4j_agent: CompiledStateGraph) -> Callable:
    async def neo4j_node(state: BWEState, config: RunnableConfig) -> dict:
        last_message = state.reasoning_steps[-1]
        tool_calls = last_message.tool_calls
        neo4j_call = next((tc for tc in tool_calls if tc['name'] == 'lookup_bird_info'), None)

        query = neo4j_call['args'].get('query', '')
        
        neo4j_input = Neo4jState(
            messages=[HumanMessage(content=query)],
            neo4j_results=Neo4jResults() 
        )

        result_state = await neo4j_agent.ainvoke(neo4j_input, config=config)
        final_results = result_state['neo4j_results']
        
        tool_message = ToolMessage(
            tool_call_id=neo4j_call['id'],
            content=str({
                'num_results': final_results.num_results(),
                'sample': final_results.sample()
            })
        )

        current_results = state.neo4j_results.copy()
        current_results[query] = final_results

        return {
            'reasoning_steps': [tool_message],
            'neo4j_results': current_results
        }

    return neo4j_node


def create_should_continue_node(max_steps: int) -> Callable:
	def should_continue(state: BWEState) -> str:
		last_message = state.reasoning_steps[-1] if state.reasoning_steps else state.messages[-1]
		tool_calls = last_message.tool_calls

		if tool_calls and state.step < max_steps:
			if any(tc['name'] == 'lookup_bird_info' for tc in tool_calls):
				logger.info('BWE agent node will invoke neo4j agent', step=state.step, tool_calls=tool_calls)
				return 'lookup_bird_info'
			logger.info('BWE agent node will invoke other tools', step=state.step, tool_calls=tool_calls)
			return 'continue'
		logger.info('BWE agent node will finalize', step=state.step, tool_calls=tool_calls)
		return 'finalize'
	
	return should_continue


def create_finalize_node(llm: BaseChatModel) -> Callable:
    def finalize_node(state: BWEState) -> BWEState:
        neo4j_results_str = 'Results from queries to the bird information database: \n\n' if len(state.neo4j_results) > 0 else ''
        neo4j_results_str += '\n'.join([
            (
                f'Database Results for Query: **{query}**\n'
                f'{result.num_results()} results found.\n'
                f'Sample of results: {result.sample()}'
            )
            for query, result in state.neo4j_results.items()
        ])

        system_message = SystemMessage(content=(
            'You are a helpful assistant for a website called "Bird Watchers\' Emporium". \n'
            'Your goal is to answer questions pertaining to birds and bird watching, and help users find trips, hotels, and gear for their own bird watching adventures! \n'
            'You have finished fetching all the information that you have access to in order to answer the user\'s question. \n'
            'Use only the information that you have gathered to answer the user\'s question.\n\n'
            f'{neo4j_results_str}'
        ))

        messages = [system_message, *state.messages]
        final_answer = llm.invoke(messages)
        logger.info('BWE agent final answer', message=final_answer)

        return BWEState(
            step=state.step,
            messages=state.messages + [final_answer],
            final_answer=final_answer.content,
            neo4j_results=state.neo4j_results
        )
    
    return finalize_node